"""
ReSpeaker Multi-Board Service

A TCP-based service that handles multiple ReSpeaker Lite boards (ESP32) simultaneously.
Each board connects via TCP, sends its MAC address as a handshake, and then streams audio.
The service publishes audio segments to MQTT with board/environment metadata.

Usage:
    python respeaker_service.py

Environment variables:
    MONGO_URL: MongoDB connection URL (default: mongodb://mongodb:27017)
    MQTT_HOST: MQTT broker hostname (default: mqtt)
    MQTT_PORT: MQTT broker port (default: 1883)
    BASE_PORT: Starting port for board connections (default: 8010)
    MONGO_MOCK: Set to "true" to use mongomock (default: false)
"""

import socket
import threading
import json
import time
import uuid
from typing import Dict, Optional
from datetime import datetime
from collections import deque
import os

from pymongo import MongoClient
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import numpy as np

# Mocking for environments without MongoDB
try:
    from mongomock import MongoClient as MockMongoClient
except ImportError:
    MockMongoClient = None

from framework.payloads.AudioPayload import AudioPayload
from framework.audio_utils import encode_audio_to_base64, calculate_audio_metrics, int2float
from framework.mqtt_auth import apply_mqtt_auth
import torch

# Configuration
MONGO_URL = "mongodb://mongodb:27017"
MQTT_HOST = "mqtt"
MQTT_PORT = 1883
BASE_PORT = 8010
MAX_BOARDS = 50
SAMPLE_RATE = 16000
CHUNK_DURATION_SECONDS = 5  # Publish audio every 5 seconds


class BoardConfig:
    """Configuration for a registered board."""

    def __init__(
        self,
        board_id: str,
        user_id: str,  # UUID string or "unassigned"
        mac_address: str,
        name: str,
        environment_id: str,
        environment_name: str = "",
        port: int = 0,
    ):
        self.board_id = board_id
        self.user_id = user_id
        self.mac_address = mac_address
        self.name = name
        self.environment_id = environment_id
        self.environment_name = environment_name
        self.port = port


class ReSpeakerService:
    """
    Multi-board TCP receiver that publishes to MQTT with metadata.

    Workflow:
    1. Boards connect to the discovery port (BASE_PORT)
    2. Board sends MAC address as first message (handshake)
    3. Service looks up board config from MongoDB
    4. If unknown board, auto-registers with default settings
    5. Handler thread receives audio and publishes to MQTT
    """

    def __init__(
        self,
        mongo_url: str = MONGO_URL,
        mqtt_host: str = MQTT_HOST,
        mqtt_port: int = MQTT_PORT,
        base_port: int = BASE_PORT,
        max_boards: int = MAX_BOARDS,
    ):
        # Load Silero VAD model
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", force_reload=False
        )
        (_, _, _, self.VADIterator, _) = utils
        self.vad_model = model

        # MongoDB connection
        if os.environ.get("MONGO_MOCK", "false").lower() == "true":
            if MockMongoClient is None:
                raise ImportError("mongomock is required for mock mode but not installed.")
            print("Using Mock MongoDB (mongomock)")
            self.mongo = MockMongoClient(mongo_url)
        else:
            self.mongo = MongoClient(mongo_url)

        self.db = self.mongo["iotsensing_live"]
        self.boards_collection = self.db["boards"]
        self.environments_collection = self.db["environments"]

        # Reset all boards to inactive on startup to clear zombie states
        # This prevents boards from remaining "online" if the service was restarted ungracefully
        print("Resetting all boards to inactive state...")
        self.boards_collection.update_many(
            {},
            {"$set": {"is_active": False}}
        )

        # MQTT connection
        self.mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.mqtt_client)
        self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
        self.mqtt_client.loop_start()

        # Configuration
        self.base_port = base_port
        self.max_boards = max_boards

        # Board management
        self.board_configs: Dict[str, BoardConfig] = {}  # mac_address -> config
        self.active_connections: Dict[str, dict] = {}  # board_id -> connection info
        self.noise_floors: Dict[str, dict] = {}  # board_id -> {"rms_history": deque, "noise_floor": float}
        self.lock = threading.Lock()

        # Load initial configurations
        self.refresh_configs()

        print(f"ReSpeaker Service initialized")
        print(f"  MongoDB: {mongo_url}")
        print(f"  MQTT: {mqtt_host}:{mqtt_port}")
        print(f"  Listening on port: {base_port}")

    def refresh_configs(self):
        """Reload board configurations from MongoDB."""
        boards = list(self.boards_collection.find({}))
        environments = {
            e["environment_id"]: e["name"]
            for e in self.environments_collection.find({})
        }

        with self.lock:
            self.board_configs.clear()
            for b in boards:
                env_name = environments.get(b.get("environment_id", ""), "unknown")
                config = BoardConfig(
                    board_id=b["board_id"],
                    user_id=b["user_id"],
                    mac_address=b["mac_address"],
                    name=b["name"],
                    environment_id=b.get("environment_id", ""),
                    environment_name=env_name,
                    port=b.get("port", 0),
                )
                self.board_configs[b["mac_address"]] = config

        print(f"Loaded {len(self.board_configs)} board configurations")

    def get_mqtt_topic(self, config: BoardConfig) -> str:
        """Generate MQTT topic for a board."""
        env_name = config.environment_name.lower().replace(" ", "_") or "unknown"
        return f"voice/{config.user_id}/{config.board_id}/{env_name}"

    def register_unknown_board(self, mac_address: str, default_user_id: str = "unassigned") -> BoardConfig:
        """Auto-register a board that's not in the database."""
        board_id = str(uuid.uuid4())
        now = datetime.utcnow()

        board_doc = {
            "board_id": board_id,
            "user_id": default_user_id,  # String UUID or "unassigned"
            "mac_address": mac_address,
            "name": f"Auto-registered ({mac_address[-8:]})",
            "environment_id": "default",
            "port": 0,
            "is_active": True,
            "created_at": now,
            "last_seen": now,
        }
        self.boards_collection.insert_one(board_doc)

        config = BoardConfig(
            board_id=board_id,
            user_id=default_user_id,
            mac_address=mac_address,
            name=board_doc["name"],
            environment_id="default",
            environment_name="unknown",
        )

        with self.lock:
            self.board_configs[mac_address] = config

        print(f"Auto-registered new board: {mac_address} -> {board_id}")
        return config

    def update_board_status(self, board_id: str, is_active: bool):
        """Update board active status and last_seen in MongoDB."""
        print(f"Updating board {board_id} status to is_active={is_active}")
        self.boards_collection.update_one(
            {"board_id": board_id},
            {"$set": {"is_active": is_active, "last_seen": datetime.utcnow()}},
        )

    def update_noise_floor(self, board_id: str, rms: float):
        """
        Update noise floor tracking for a board.
        Keeps track of RMS values over the last 60 seconds (12 chunks of 5s each).
        The noise floor is the minimum RMS seen in this window.
        """
        with self.lock:
            if board_id not in self.noise_floors:
                self.noise_floors[board_id] = {
                    "rms_history": deque(maxlen=12),  # 60 seconds / 5 seconds per chunk
                    "noise_floor": None
                }
            
            # Add current RMS to history
            self.noise_floors[board_id]["rms_history"].append(rms)
            
            # Calculate noise floor as minimum RMS in history (excluding zeros)
            # We exclude zeros because they represent complete silence, not ambient noise
            history = self.noise_floors[board_id]["rms_history"]
            non_zero_rms = [r for r in history if r > 0]
            if non_zero_rms:
                self.noise_floors[board_id]["noise_floor"] = min(non_zero_rms)
            else:
                self.noise_floors[board_id]["noise_floor"] = None

    def get_noise_floor(self, board_id: str) -> Optional[float]:
        """Get the current noise floor for a board."""
        with self.lock:
            if board_id in self.noise_floors:
                return self.noise_floors[board_id]["noise_floor"]
            return None

    def handle_board_connection(self, conn: socket.socket, addr: tuple, config: BoardConfig):
        """Handle audio streaming from a single board."""
        topic = self.get_mqtt_topic(config)
        buffer = b""
        chunk_size = SAMPLE_RATE * 2 * CHUNK_DURATION_SECONDS  # 16-bit mono audio
        speech_buffer = []

        print(f"Board {config.name} ({config.mac_address}) connected from {addr}")
        print(f"  Publishing to topic: {topic}")

        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    print(f"Board {config.name} disconnected (no data)")
                    break

                buffer += data

                # Process buffer in 512-sample frames for VAD
                # 512 samples * 2 bytes/sample = 1024 bytes
                FRAME_SIZE = 512
                FRAME_BYTES = FRAME_SIZE * 2

                while len(buffer) >= FRAME_BYTES:
                    frame_bytes = buffer[:FRAME_BYTES]
                    buffer = buffer[FRAME_BYTES:]

                    audio_int16 = np.frombuffer(frame_bytes, dtype=np.int16)
                    audio_float32 = int2float(audio_int16)

                    # Use direct model call instead of VADIterator to avoid state shape errors
                    # This matches the implementation in VoiceFromFile.py
                    confidence = self.vad_model(
                        torch.from_numpy(audio_float32), 16000
                    ).item()

                    if confidence > 0.5:
                        speech_buffer.append(frame_bytes)

                    # Check if we have enough speech for a chunk
                    current_speech_bytes = sum(len(b) for b in speech_buffer)
                    if current_speech_bytes >= chunk_size:
                        # Construct the audio chunk from speech frames
                        audio_bytes = b"".join(speech_buffer)
                        # Clear buffer (or handle overlap if needed, but here we just take the chunk)
                        speech_buffer = [] # Reset buffer

                        # Convert raw bytes to numpy array (16-bit PCM)
                        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

                        # Calculate RMS first for noise floor tracking
                        audio_float = audio_np.astype(np.float32) / 32768.0
                        rms = np.sqrt(np.mean(audio_float**2))

                        # Update noise floor tracking
                        self.update_noise_floor(config.board_id, float(rms))

                        # Get current noise floor for SNR calculation
                        noise_floor = self.get_noise_floor(config.board_id)

                        # Encode to base64 WAV
                        audio_b64 = encode_audio_to_base64(audio_np, SAMPLE_RATE)

                        # Calculate quality metrics with noise floor
                        metrics = calculate_audio_metrics(audio_np, SAMPLE_RATE, noise_floor)

                        # Create payload with metadata
                        payload = AudioPayload(
                            data=audio_b64,
                            timestamp=time.time(),
                            sample_rate=SAMPLE_RATE,
                            board_id=config.board_id,
                            user_id=config.user_id,
                            environment_id=config.environment_id,
                            environment_name=config.environment_name,
                            quality_metrics=metrics,
                            system_mode="live",  # Physical boards always use live mode
                        )

                        # Publish to MQTT
                        self.mqtt_client.publish(topic, json.dumps(payload.to_dict()))
                        print(f"Published {len(audio_np)} samples to {topic}")

        except socket.timeout:
            print(f"Board {config.name} connection timed out (no data received within timeout window)")
        except ConnectionResetError:
            print(f"Board {config.name} connection reset")
        except Exception as e:
            print(f"Error handling board {config.name}: {e}")
        finally:
            conn.close()
            self.update_board_status(config.board_id, is_active=False)
            with self.lock:
                if config.board_id in self.active_connections:
                    del self.active_connections[config.board_id]
                # Clean up noise floor tracking
                if config.board_id in self.noise_floors:
                    del self.noise_floors[config.board_id]
            print(f"Board {config.name} handler terminated")

    def handle_new_connection(self, conn: socket.socket, addr: tuple):
        """Handle a new incoming connection - perform handshake and start handler."""
        try:
            # Set timeout for handshake
            conn.settimeout(10.0)

            # Receive MAC address as handshake (17 chars: AA:BB:CC:DD:EE:FF)
            mac_data = b""
            # Loop to ensure we get exactly 17 bytes
            while len(mac_data) < 17:
                chunk = conn.recv(17 - len(mac_data))
                if not chunk:
                    break
                mac_data += chunk

            if len(mac_data) < 17:
                print(f"Connection from {addr} closed before complete handshake (got {len(mac_data)} bytes)")
                conn.close()
                return

            mac_address = mac_data.decode().strip().upper()
            print(f"Handshake received from {addr}: MAC={mac_address}")

            # Send acknowledgement
            conn.sendall(b"READY\n")

            # Set timeout for zombie connection detection
            # Since we expect audio chunks every 5 seconds, we set timeout to 15 seconds
            # to allow for network delays while still detecting dead connections
            conn.settimeout(15.0)

            # Look up or register board
            with self.lock:
                config = self.board_configs.get(mac_address)

            if not config:
                print(f"Unknown board {mac_address}, auto-registering...")
                config = self.register_unknown_board(mac_address)

            # Update status
            self.update_board_status(config.board_id, is_active=True)

            with self.lock:
                self.active_connections[config.board_id] = {
                    "addr": addr,
                    "connected_at": time.time(),
                }

            # Start handler thread
            handler_thread = threading.Thread(
                target=self.handle_board_connection,
                args=(conn, addr, config),
                daemon=True,
            )
            handler_thread.start()

        except socket.timeout:
            print(f"Handshake timeout from {addr}")
            conn.close()
        except Exception as e:
            print(f"Error during handshake from {addr}: {e}")
            conn.close()

    def run(self):
        """Main run loop - listen for board connections."""
        # Start config refresh thread
        def refresh_loop():
            while True:
                time.sleep(60)
                try:
                    self.refresh_configs()
                except Exception as e:
                    print(f"Error refreshing configs: {e}")

        refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        refresh_thread.start()

        # Create server socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.base_port))
        server.listen(self.max_boards)

        print(f"ReSpeaker Service listening on port {self.base_port}")
        print("Waiting for board connections...")

        try:
            while True:
                conn, addr = server.accept()
                print(f"New connection from {addr}")

                # Handle connection in separate thread
                thread = threading.Thread(
                    target=self.handle_new_connection,
                    args=(conn, addr),
                    daemon=True,
                )
                thread.start()

        except KeyboardInterrupt:
            print("\nShutting down ReSpeaker Service...")
        finally:
            server.close()
            self.mqtt_client.loop_stop()
            self.mongo.close()


if __name__ == "__main__":
    import os

    service = ReSpeakerService(
        mongo_url=os.environ.get("MONGO_URL", MONGO_URL),
        mqtt_host=os.environ.get("MQTT_HOST", MQTT_HOST),
        mqtt_port=int(os.environ.get("MQTT_PORT", MQTT_PORT)),
        base_port=int(os.environ.get("BASE_PORT", BASE_PORT)),
    )
    service.run()
