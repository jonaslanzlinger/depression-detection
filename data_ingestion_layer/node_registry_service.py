"""Node registry service: the server side of the edge capability handshake.

Subscribes to `nodes/+/capabilities` (retained advertisements from ESP32-S3 nodes),
validates + negotiates an assignment, persists both to the `iotsensing.nodes` registry, and
replies on `nodes/{id}/config` (retained) with what the node should compute and send.

Env: MONGO_URL, MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS.
"""
import os
import json
from datetime import datetime, timezone

from pymongo import MongoClient
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from framework.mqtt_auth import apply_mqtt_auth
from framework.node_registry import NodeRegistry, process_capabilities

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

CAPABILITIES_TOPIC = "nodes/+/capabilities"
STATUS_TOPIC = "nodes/+/status"
MARKER_TOPIC = "nodes/+/marker"

# Mode-isolated DBs (mirrors the pipeline's routing map).
DB_MAP = {"live": "iotsensing_live", "dataset": "iotsensing_dataset", "demo": "iotsensing_demo"}

STATUS_HISTORY_TTL_SECONDS = 90 * 24 * 3600  # 90 days


def node_id_from_topic(topic: str):
    parts = topic.split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == "nodes" else None


class NodeRegistryService:
    def __init__(self, mongo_url=MONGO_URL, mqtt_host=MQTT_HOST, mqtt_port=MQTT_PORT):
        self.mongo_client = MongoClient(mongo_url)
        # Global (non mode-isolated) registry, like board/system settings.
        self.registry = NodeRegistry(self.mongo_client["iotsensing"]["nodes"])

        # Fleet-health history: append-only, global, TTL-capped. Indexes are idempotent
        # (create_index is a no-op if the index already matches) so it is safe to call on
        # every boot rather than gating it behind a migration step.
        self.status_history = self.mongo_client["iotsensing"]["node_status_history"]
        self.status_history.create_index([("node_id", 1), ("ts", -1)])
        self.status_history.create_index("ts", expireAfterSeconds=STATUS_HISTORY_TTL_SECONDS)

        # Event markers (participant button double-press): precious ground-truth
        # annotations for the study -- kept forever, no TTL.
        self.markers = self.mongo_client["iotsensing"]["node_markers"]
        self.markers.create_index([("node_id", 1), ("ts", -1)])

        self.mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        apply_mqtt_auth(self.mqtt_client)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
        print(f"Node Registry Service initialized (mongo={mongo_url}, mqtt={mqtt_host}:{mqtt_port})")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(CAPABILITIES_TOPIC)
        client.subscribe(STATUS_TOPIC)
        client.subscribe(MARKER_TOPIC)
        print(f"Subscribed to {CAPABILITIES_TOPIC}, {STATUS_TOPIC}, {MARKER_TOPIC}")

    def handle_status(self, topic_id: str, data: dict):
        """Heartbeat: refresh last_seen/telemetry and mirror into the legacy `boards`
        collection so the user-facing Boards page sees MQTT nodes.

        The boards bridge only fires for ENROLLED nodes (iotsensing.node_enrollments,
        written by scripts/enroll_node.sh) because boards are keyed by user_id -- an
        unenrolled node has no user and remains visible on the Edge Nodes page only."""
        now = datetime.now(timezone.utc)
        online = bool(data.get("online", True))  # LWT publishes {"online": false}
        telemetry = {
            "online": online,
            "rssi": data.get("rssi"),
            "free_heap": data.get("free_heap"),
            "uptime_s": data.get("uptime_s"),
            "muted": data.get("muted"),
            "mode": data.get("mode"),
        }
        self.registry.touch(topic_id, telemetry=telemetry, last_seen=now)

        # History write is best-effort: a failure here must never break the existing
        # touch/boards-bridge behavior above (which is depended on by the Boards page
        # and the Edge Nodes online indicator).
        try:
            self.status_history.insert_one({
                "node_id": topic_id,
                "ts": now,
                "online": online,
                "rssi": data.get("rssi"),
                "free_heap": data.get("free_heap"),
                "uptime_s": data.get("uptime_s"),
                "muted": data.get("muted"),
                "mode": data.get("mode"),
            })
        except Exception as e:
            print(f"Failed to write status history for '{topic_id}':", e)

        enrollment = self.mongo_client["iotsensing"]["node_enrollments"].find_one(
            {"node_id": topic_id}
        )
        if not enrollment or not enrollment.get("user_id"):
            return
        user_id = enrollment["user_id"]
        # dataset user ids are ints; keep the stored type consistent with the pipeline
        if isinstance(user_id, str) and user_id.lstrip("-").isdigit():
            user_id = int(user_id)
        db_name = DB_MAP.get(enrollment.get("system_mode", "live"), "iotsensing_live")
        self.mongo_client[db_name]["boards"].update_one(
            {"board_id": topic_id},
            {
                "$set": {
                    "user_id": user_id,
                    "is_active": online,
                    "last_seen": now,
                    "muted": bool(data.get("muted", False)),
                },
                "$setOnInsert": {
                    "board_id": topic_id,
                    # respeaker-<mac12> -> aa:bb:cc:dd:ee:ff
                    "mac_address": ":".join(
                        topic_id.split("-")[-1][i:i+2] for i in range(0, 12, 2)
                    ) if len(topic_id.split("-")[-1]) == 12 else None,
                    "name": topic_id,          # renameable in the dashboard later
                    "environment_id": None,    # assigned via the Boards page
                },
            },
            upsert=True,
        )

    def handle_marker(self, topic_id: str, data: dict):
        """Event marker (participant button double-press): the participant flagging 'this
        moment' for ground-truth annotation. Stored verbatim under `payload` (defensive --
        the firmware's marker shape is out of scope for this service to validate) plus the
        two fields we know are always present for querying without unpacking payload."""
        now = datetime.now(timezone.utc)
        try:
            self.markers.insert_one({
                "node_id": topic_id,
                "ts": now,
                "uptime_s": data.get("uptime_s"),
                "muted": data.get("muted"),
                "payload": data,
            })
            print(f"Marker recorded for '{topic_id}'")
        except Exception as e:
            print(f"Failed to write marker for '{topic_id}':", e)

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            # SECURITY: the TOPIC segment is the authoritative node identity (a node may only
            # publish to its own nodes/{id}/... under broker ACLs). Always use it and ignore any
            # node_id in the payload, so a node can't spoof another node's id to overwrite its
            # registry entry or publish a (retained) config to its topic.
            topic_id = node_id_from_topic(msg.topic)
            if not topic_id:
                print(f"Ignoring advert on non-node topic {msg.topic}")
                return
            if msg.topic.endswith("/status"):
                self.handle_status(topic_id, data)
                return
            if msg.topic.endswith("/marker"):
                self.handle_marker(topic_id, data)
                return
            if data.get("node_id") and data["node_id"] != topic_id:
                print(f"node_id mismatch: payload '{data['node_id']}' != topic '{topic_id}'; using topic")
            data["node_id"] = topic_id

            caps, assignment, problems = process_capabilities(data)
            if problems:
                print(f"Capability advert from '{data.get('node_id', topic_id)}' has issues: {problems}")
            if caps is None:
                print(f"Ignoring invalid capability advert on {msg.topic}")
                return

            self.registry.register(caps, assignment, last_seen=datetime.now(timezone.utc))
            client.publish(
                f"nodes/{caps.node_id}/config",
                json.dumps(assignment.to_dict()),
                retain=True,
            )
            print(f"Registered node '{caps.node_id}' -> assignment mode={assignment.mode} "
                  f"features={assignment.features}")
        except Exception as e:
            print(f"Error handling capability advert on '{msg.topic}':", e)

    def run(self):
        self.mqtt_client.loop_forever()


if __name__ == "__main__":
    NodeRegistryService().run()
