"""Shared MQTT auth helper: set username/password from env if configured (no-op otherwise),
so enabling broker auth doesn't require touching every client's connect logic."""
import os


def apply_mqtt_auth(client):
    user = os.getenv("MQTT_USER")
    if user:
        client.username_pw_set(user, os.getenv("MQTT_PASS"))
