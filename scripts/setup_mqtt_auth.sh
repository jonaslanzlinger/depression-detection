#!/usr/bin/env bash
# Generate the mosquitto password file + base ACL for the backend SERVICE account
# (MQTT_USER/MQTT_PASS in .env). Run once, and again whenever the service creds change.
# Per-node accounts are added separately by scripts/enroll_node.sh (which appends to both
# files). Uses the mosquitto image so no local mosquitto_passwd is needed.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
: "${MQTT_USER:?set MQTT_USER in .env}"; : "${MQTT_PASS:?set MQTT_PASS in .env}"

# (Re)create the password file with the service account (-c overwrites; enroll_node.sh appends).
docker run --rm -v "$PWD:/work" -w /work eclipse-mosquitto \
  mosquitto_passwd -b -c mosquitto.passwd "$MQTT_USER" "$MQTT_PASS"
echo "Wrote mosquitto.passwd for service user '$MQTT_USER'."

# (Re)create the ACL. The service account has full access (backend consumers subscribe to
# voice/# and nodes/+/capabilities and publish nodes/{id}/config). Per-node restricted blocks
# are appended below the marker by enroll_node.sh.
cat > mosquitto.acl <<EOF
# Backend service account -- full access.
user ${MQTT_USER}
topic readwrite #

# === per-node entries (appended by scripts/enroll_node.sh) ===
EOF
echo "Wrote mosquitto.acl base (service user '${MQTT_USER}' = full access)."
