#!/usr/bin/env bash
# Advertise the MQTT broker on the LAN as _iotsensing-mqtt._tcp so plug-and-play edge nodes
# (firmware net/discovery.c) find it without a compiled-in IP.
#
# PREREQUISITES (deliberately NOT auto-applied -- both are deployment/security decisions):
#   1. avahi-daemon installed + running:
#        sudo apt-get install -y avahi-daemon && sudo systemctl enable --now avahi-daemon
#   2. the MQTT broker reachable on the LAN (NOT only 127.0.0.1). The compose binds it to
#        127.0.0.1:1883 for PHI safety; exposing it to the LAN means changing that to
#        "1883:1883". Auth is required (PR #81) and broker ACLs are recommended before doing so.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
sudo install -m 644 "$HERE/iotsensing-mqtt.service" /etc/avahi/services/iotsensing-mqtt.service
sudo systemctl reload avahi-daemon 2>/dev/null || sudo systemctl restart avahi-daemon
echo "Advertised _iotsensing-mqtt._tcp on the LAN."
echo "Verify from another host:  avahi-browse -rt _iotsensing-mqtt._tcp"
