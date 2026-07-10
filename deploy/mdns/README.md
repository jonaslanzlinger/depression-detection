# Broker mDNS advertisement (plug-and-play sink discovery)

Edge nodes (firmware `net/discovery.c`) resolve the backend MQTT broker at runtime via mDNS
(`_iotsensing-mqtt._tcp`) so the **server IP is never compiled into the firmware** — flash a
node anywhere and it finds the sink. Fallbacks if mDNS is unavailable: a broker host saved in
the node's NVS, then the compiled `CONFIG_SERVER_HOST`.

## Install (on the broker host)
```bash
deploy/mdns/setup_mdns.sh
```

## Two prerequisites (not auto-applied — your call)
1. **Avahi running** — `sudo apt-get install -y avahi-daemon && sudo systemctl enable --now avahi-daemon`.
2. **Broker reachable on the LAN** — `docker-compose.yml` binds MQTT to `127.0.0.1:1883`
   (PHI safety). Nodes are on the LAN, so for them to connect you must change that to
   `1883:1883`. Authentication is already enforced (PR #81); add broker ACLs (per-node
   username → `nodes/{id}/#` + `voice/#`) before exposing, and consider TLS (8883).

## How it ties together
node boots → joins Wi-Fi → mDNS query `_iotsensing-mqtt._tcp` → broker host:port → MQTT
connect (auth) → advertise capabilities → receive assignment → stream. See
`docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md`.
