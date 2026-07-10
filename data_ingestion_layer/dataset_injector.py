"""
Dataset Injector

Injects audio files from a directory into the system with system_mode="dataset".
This is used for research data that should be stored separately from live patient data.

Usage:
    python dataset_injector.py --dir ../datasets --user-id 1
    python dataset_injector.py --file audio.wav --user-id 1 --board-id test-board

Environment variables:
    MQTT_HOST: MQTT broker hostname (default: mqtt)
    MQTT_PORT: MQTT broker port (default: 1883)
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import librosa
import torch
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from pymongo import MongoClient
from datetime import datetime

from framework.payloads.AudioPayload import AudioPayload
from framework.audio_utils import encode_audio_to_base64, calculate_audio_metrics, int2float
from framework.mqtt_auth import apply_mqtt_auth


class DatasetInjector:
    """Injects WAV files into the system with system_mode='dataset'."""

    def __init__(
        self,
        mqtt_host: str = "mqtt",
        mqtt_port: int = 1883,
        mongo_url: str = "mongodb://mongodb:27017",
        user_id: int = 1,
        board_id: str = "dataset-injector",
        environment_name: str = "research",
        use_vad: bool = True,
        sample_rate: int = 16000,
    ):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mongo_url = mongo_url
        self.user_id = user_id
        self.board_id = board_id
        self.environment_name = environment_name
        self.use_vad = use_vad
        self.sample_rate = sample_rate

        # MongoDB connection for board registration
        try:
            self.mongo_client = MongoClient(self.mongo_url)
            self.db = self.mongo_client["iotsensing_dataset"]
            self._register_virtual_board()
        except Exception as e:
            print(f"Warning: Could not connect to MongoDB to register board: {e}")

        # MQTT client
        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.client)
        self.client.connect(mqtt_host, mqtt_port, 60)
        self.client.loop_start()

        # VAD model (optional)
        self.vad_model = None
        if use_vad:
            try:
                model, utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                )
                self.vad_model = model
                print("VAD model loaded successfully")
            except Exception as e:
                print(f"Warning: Could not load VAD model: {e}")
                print("Proceeding without VAD filtering")

        # Topic for publishing
        env_normalized = self.environment_name.lower().replace(" ", "_")
        self.topic = f"voice/{self.user_id}/{self.board_id}/{env_normalized}"

        print(f"Dataset Injector initialized")
        print(f"  MQTT: {mqtt_host}:{mqtt_port}")
        print(f"  MongoDB: {mongo_url}")
        print(f"  Topic: {self.topic}")
        print(f"  System Mode: dataset")
        print(f"  VAD: {'enabled' if use_vad and self.vad_model else 'disabled'}")

    def _register_virtual_board(self):
        """Register a virtual board and environment in iotsensing_dataset."""
        try:
            # 1. Ensure Environment
            env_id = f"env_{self.environment_name.lower().replace(' ', '_')}"
            existing_env = self.db["environments"].find_one({"environment_id": env_id})
            
            if not existing_env:
                self.db["environments"].insert_one({
                    "environment_id": env_id,
                    "user_id": self.user_id,
                    "name": self.environment_name,
                    "description": "Virtual environment for dataset injection",
                    "created_at": datetime.utcnow(),
                    "system_mode": "dataset"
                })
                print(f"  Registered environment: {self.environment_name}")

            # 2. Ensure Board
            existing_board = self.db["boards"].find_one({"board_id": self.board_id})
            
            # Always update last_seen to make it appear active
            board_doc = {
                "board_id": self.board_id,
                "user_id": self.user_id,
                "mac_address": "00:00:00:00:00:00",
                "name": "Dataset Injector",
                "environment_id": env_id,
                "port": 0,
                "is_active": True,
                "last_seen": datetime.utcnow(),
                "created_at": datetime.utcnow() if not existing_board else existing_board.get("created_at"),
                "system_mode": "dataset"
            }
            
            self.db["boards"].replace_one(
                {"board_id": self.board_id},
                board_doc,
                upsert=True
            )
            print(f"  Registered virtual board: {self.board_id}")
            
        except Exception as e:
            print(f"Error registering virtual board: {e}")

    def load_audio(self, filepath: str) -> np.ndarray:
        """Load and normalize audio file to 16kHz mono int16."""
        audio_np, sr = sf.read(filepath)

        # Convert to mono
        if audio_np.ndim > 1:
            audio_np = np.mean(audio_np, axis=1)

        # Resample to 16kHz
        if sr != self.sample_rate:
            audio_np = librosa.resample(
                audio_np.astype(np.float32),
                orig_sr=sr,
                target_sr=self.sample_rate,
            )

        # Normalize
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = (audio_np / max_val) * 0.9

        # Convert to int16
        audio_np = (audio_np * 32767).astype(np.int16)

        return audio_np

    def apply_vad(self, audio_np: np.ndarray, min_speech_frames: int = 160) -> list:
        """Apply Voice Activity Detection and return speech segments."""
        if self.vad_model is None:
            # No VAD, return as single segment
            return [audio_np]

        frame_size = 512
        buffer = []
        segments = []

        for i in range(0, len(audio_np), frame_size):
            chunk = audio_np[i:i + frame_size]
            if len(chunk) < frame_size:
                continue

            audio_float32 = int2float(chunk)
            confidence = self.vad_model(
                torch.from_numpy(audio_float32),
                self.sample_rate,
            ).item()

            if confidence > 0.5:
                buffer.append(chunk)
            else:
                if len(buffer) >= min_speech_frames:
                    segments.append(np.concatenate(buffer))
                buffer.clear()

        # Handle remaining buffer
        if len(buffer) >= min_speech_frames:
            segments.append(np.concatenate(buffer))

        return segments

    def publish_segment(self, audio_np: np.ndarray, timestamp: Optional[float] = None):
        """Publish a single audio segment to MQTT."""
        if timestamp is None:
            timestamp = time.time()

        # Encode audio
        audio_b64 = encode_audio_to_base64(audio_np, self.sample_rate)

        # Calculate quality metrics
        metrics = calculate_audio_metrics(audio_np, self.sample_rate)

        # Create payload with system_mode="dataset"
        payload = AudioPayload(
            data=audio_b64,
            timestamp=timestamp,
            sample_rate=self.sample_rate,
            board_id=self.board_id,
            user_id=self.user_id,
            environment_id=self.environment_name,
            environment_name=self.environment_name,
            quality_metrics=metrics,
            system_mode="dataset",  # Key difference from live data
        )

        # Publish
        result = self.client.publish(self.topic, json.dumps(payload.to_dict()))
        result.wait_for_publish()

        duration = len(audio_np) / self.sample_rate
        print(f"  Published segment: {duration:.2f}s, RMS: {metrics.get('rms', 0):.4f}")

    def inject_file(self, filepath: str, delay_between_segments: float = 0.5):
        """Inject a single audio file."""
        print(f"\nProcessing: {filepath}")

        # Load audio
        audio_np = self.load_audio(filepath)
        duration = len(audio_np) / self.sample_rate
        print(f"  Loaded: {duration:.2f}s of audio")

        # Apply VAD
        if self.use_vad:
            segments = self.apply_vad(audio_np)
            print(f"  VAD extracted {len(segments)} speech segments")
        else:
            # Split into 5-second chunks without VAD
            chunk_size = self.sample_rate * 5
            segments = [audio_np[i:i + chunk_size] for i in range(0, len(audio_np), chunk_size)]
            segments = [s for s in segments if len(s) >= self.sample_rate]  # Filter out tiny chunks
            print(f"  Split into {len(segments)} chunks")

        # Publish each segment
        base_timestamp = time.time()
        for i, segment in enumerate(segments):
            segment_timestamp = base_timestamp + (i * 5)  # Simulate 5-second intervals
            self.publish_segment(segment, segment_timestamp)

            if delay_between_segments > 0 and i < len(segments) - 1:
                time.sleep(delay_between_segments)

        return len(segments)

    def inject_directory(self, directory: str, delay_between_files: float = 1.0):
        """Inject all WAV files from a directory."""
        dir_path = Path(directory)
        wav_files = sorted(dir_path.glob("*.wav"))

        if not wav_files:
            print(f"No WAV files found in {directory}")
            return 0

        print(f"\nFound {len(wav_files)} WAV files in {directory}")

        total_segments = 0
        for i, filepath in enumerate(wav_files, 1):
            print(f"\n[{i}/{len(wav_files)}] ", end="")
            segments = self.inject_file(str(filepath))
            total_segments += segments

            if delay_between_files > 0 and i < len(wav_files):
                time.sleep(delay_between_files)

        return total_segments

    def close(self):
        """Clean up MQTT connection."""
        self.client.loop_stop()
        self.client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="Inject audio files into the system with system_mode='dataset'"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", help="Path to a single WAV file")
    group.add_argument("--dir", "-d", help="Path to a directory of WAV files")

    parser.add_argument("--user-id", "-u", type=int, default=1, help="User ID (default: 1)")
    parser.add_argument("--board-id", "-b", default="dataset-injector", help="Board ID")
    parser.add_argument("--environment", "-e", default="research", help="Environment name")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD filtering")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between segments (seconds)")
    parser.add_argument("--mqtt-host", default=None, help="MQTT host (default: from env or 'mqtt')")
    parser.add_argument("--mqtt-port", type=int, default=None, help="MQTT port (default: from env or 1883)")
    parser.add_argument("--mongo-url", default=None, help="MongoDB URL (default: from env or 'mongodb://mongodb:27017')")

    args = parser.parse_args()

    # Get settings from environment or arguments
    mqtt_host = args.mqtt_host or os.environ.get("MQTT_HOST", "mqtt")
    mqtt_port = args.mqtt_port or int(os.environ.get("MQTT_PORT", 1883))
    mongo_url = args.mongo_url or os.environ.get("MONGO_URL", "mongodb://mongodb:27017")

    # Create injector
    injector = DatasetInjector(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mongo_url=mongo_url,
        user_id=args.user_id,
        board_id=args.board_id,
        environment_name=args.environment,
        use_vad=not args.no_vad,
    )

    try:
        if args.file:
            segments = injector.inject_file(args.file, delay_between_segments=args.delay)
        else:
            segments = injector.inject_directory(args.dir, delay_between_files=args.delay)

        print(f"\n{'='*50}")
        print(f"Injection complete: {segments} segments published")
        print(f"System mode: dataset")
        print(f"Data will be stored in: iotsensing_dataset")

    except KeyboardInterrupt:
        print("\nInjection interrupted by user")
    finally:
        injector.close()


if __name__ == "__main__":
    main()
