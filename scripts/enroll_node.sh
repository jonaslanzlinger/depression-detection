#!/usr/bin/env bash
# Enroll an edge node: create a per-node MQTT credential that the broker ACL restricts to the
# node's OWN topics, so it can publish only its own data and cannot spoof another node or user.
#
# Usage: scripts/enroll_node.sh <node_id> <user_id> [system_mode]
#   node_id      the board's id, e.g. respeaker-aabbccddeeff (also the MQTT username)
#   user_id      the occupant this node captures for (int for dataset, uuid for live)
#   system_mode  live|dataset|demo, default live -- PINNED server-side so the node's records
#                always route to this DB regardless of what its payload claims.
#
# Enter the printed MQTT_USER/MQTT_PASS into the node's provisioning portal. Re-running for the
# same node_id rotates the password (and keeps the existing ACL).
set -euo pipefail
cd "$(dirname "$0")/.."

NODE_ID="${1:?usage: enroll_node.sh <node_id> <user_id> [system_mode]}"
USER_ID="${2:?usage: enroll_node.sh <node_id> <user_id> [system_mode]}"
MODE="${3:-live}"

# node_id becomes an MQTT username AND a topic segment -> restrict its charset.
[[ "$NODE_ID" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "node_id must match [A-Za-z0-9_-]+"; exit 1; }
case "$MODE" in live|dataset|demo) ;; *) echo "system_mode must be live|dataset|demo"; exit 1;; esac
[ -f mosquitto.passwd ] || { echo "run scripts/setup_mqtt_auth.sh first"; exit 1; }

PASS="$(openssl rand -hex 16)"

# Add (or update) the node user in the password file (append; no -c so the service user stays).
docker run --rm -v "$PWD:/work" -w /work eclipse-mosquitto \
  mosquitto_passwd -b mosquitto.passwd "$NODE_ID" "$PASS"

# Append the restricted ACL block once.
if grep -q "^user ${NODE_ID}\$" mosquitto.acl 2>/dev/null; then
  echo "ACL for ${NODE_ID} already present; leaving it (edit mosquitto.acl to change scope)."
else
  cat >> mosquitto.acl <<EOF

user ${NODE_ID}
topic write voice/${USER_ID}/${NODE_ID}/#
topic write nodes/${NODE_ID}/capabilities
topic write nodes/${NODE_ID}/status
topic read nodes/${NODE_ID}/config
EOF
fi

# Reload mosquitto (SIGHUP re-reads passwd + acl without dropping the broker).
MQTT_CTR="$(docker ps --format '{{.Names}}' | grep -E 'mqtt' | head -1 || true)"
if [ -n "$MQTT_CTR" ]; then
  docker exec "$MQTT_CTR" kill -HUP 1 2>/dev/null || true
fi

# Pin the node's system_mode in iotsensing.node_enrollments so voice_metrics routes its records
# to this DB regardless of the payload (creds passed via env, never string-interpolated).
set -a; [ -f .env ] && . ./.env; set +a
if docker ps --format '{{.Names}}' | grep -q '^mongodb$'; then
  docker exec -e N="$NODE_ID" -e U="$USER_ID" -e M="$MODE" mongodb mongosh --quiet \
    ${MONGO_USER:+-u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin} iotsensing --eval '
      db.node_enrollments.updateOne({node_id: process.env.N},
        {$set: {node_id: process.env.N, user_id: process.env.U, system_mode: process.env.M}},
        {upsert: true});
      print("enrollment pinned: " + process.env.N + " -> system_mode=" + process.env.M);
    ' || echo "WARN: could not write node_enrollments (is mongodb up + creds in .env?)"
else
  echo "WARN: mongodb container not running; system_mode binding NOT written. Re-run with the stack up."
fi

echo "Enrolled node '${NODE_ID}' for user_id '${USER_ID}' (system_mode=${MODE}). Credentials (enter in provisioning):"
echo "  MQTT_USER=${NODE_ID}"
echo "  MQTT_PASS=${PASS}"
echo "Scope: publish voice/${USER_ID}/${NODE_ID}/# + nodes/${NODE_ID}/{capabilities,status}; subscribe nodes/${NODE_ID}/config."
