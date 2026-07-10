"""
Quality Metrics Subscriber Service

Subscribes to MQTT audio messages and stores quality metrics (dBFS, RMS, Peak, 
Clipping Count, Dynamic Range, SNR) to MongoDB for dashboard analytics.

Usage:
    python quality_metrics_service.py

Environment variables:
    MONGO_URL: MongoDB connection URL (default: mongodb://mongodb:27017)
    MQTT_HOST: MQTT broker hostname (default: mqtt)
    MQTT_PORT: MQTT broker port (default: 1883)
"""

import json
import os
from datetime import datetime
from pymongo import MongoClient
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from framework.mqtt_auth import apply_mqtt_auth

# Configuration
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

# Database routing based on system_mode
DB_MAP = {
    "live": "iotsensing_live",
    "dataset": "iotsensing_dataset",
    "demo": "iotsensing_demo",
}


class QualityMetricsService:
    """
    Service that subscribes to audio MQTT topics and stores quality metrics.
    """

    def __init__(self, mongo_url: str = MONGO_URL, mqtt_host: str = MQTT_HOST, mqtt_port: int = MQTT_PORT):
        # MongoDB connection
        self.mongo_client = MongoClient(mongo_url)
        
        # MQTT connection
        self.mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.mqtt_client)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_host, mqtt_port, 60)

        print(f"Quality Metrics Service initialized")
        print(f"  MongoDB: {mongo_url}")
        print(f"  MQTT: {mqtt_host}:{mqtt_port}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to MQTT broker."""
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to all voice topics
        client.subscribe("voice/#")
        print("Subscribed to topic: voice/#")

    def on_message(self, client, userdata, msg):
        """Callback when a message is received."""
        try:
            # Parse the JSON payload
            payload = json.loads(msg.payload.decode())
            
            # Extract quality metrics
            quality_metrics = payload.get("quality_metrics")
            if not quality_metrics:
                return  # Skip if no quality metrics
            
            # Extract metadata
            board_id = payload.get("board_id")
            user_id = payload.get("user_id")
            environment_id = payload.get("environment_id")
            environment_name = payload.get("environment_name")
            system_mode = payload.get("system_mode", "live")
            timestamp = payload.get("timestamp")
            
            # Convert timestamp to datetime if it's a float
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.utcfromtimestamp(timestamp)
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.utcnow()
            
            # Create quality metrics record
            record = {
                "board_id": board_id,
                "user_id": user_id,
                "environment_id": environment_id,
                "environment_name": environment_name,
                "timestamp": timestamp,
                "rms": quality_metrics.get("rms"),
                "peak_amplitude": quality_metrics.get("peak_amplitude"),
                "clipping_count": quality_metrics.get("clipping_count"),
                "db_fs": quality_metrics.get("db_fs"),
                "dynamic_range": quality_metrics.get("dynamic_range"),
                "snr": quality_metrics.get("snr"),
            }
            
            # Get appropriate database based on system_mode
            db_name = DB_MAP.get(system_mode, "iotsensing_live")
            db = self.mongo_client[db_name]
            collection = db["audio_quality_metrics"]
            
            # Insert the record
            collection.insert_one(record)
            
            # Log only if there's something interesting
            if quality_metrics.get("clipping_count", 0) > 0 or quality_metrics.get("snr") is not None:
                snr_str = f"{quality_metrics.get('snr'):.2f}" if quality_metrics.get("snr") is not None else "N/A"
                print(f"Saved quality metrics for {board_id}: dBFS={quality_metrics.get('db_fs', 0):.2f}, "
                      f"Clipping={quality_metrics.get('clipping_count', 0)}, "
                      f"SNR={snr_str}")
                
        except Exception as e:
            print(f"Error processing message from {msg.topic}: {e}")

    def run(self):
        """Start the service."""
        print("Quality Metrics Service running...")
        print("Waiting for audio messages...")
        try:
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            print("\nShutting down Quality Metrics Service...")
        finally:
            self.mqtt_client.loop_stop()
            self.mongo_client.close()


if __name__ == "__main__":
    service = QualityMetricsService()
    service.run()
