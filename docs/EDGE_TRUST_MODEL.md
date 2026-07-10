# Edge trust model — per-node MQTT credentials + broker ACLs

Closes the spoofing gaps the shared-MQTT-credential design left open (a node could publish to
another node's topics or attribute audio to another user). Two credential classes:

| Class | Who | MQTT scope (ACL) |
|---|---|---|
| **Service account** | backend services (voice_metrics, node_registry, quality, respeaker, dashboard, dataset injector) | `topic readwrite #` (full access) |
| **Per-node account** | each ESP32 edge node, username = `node_id` | publish `voice/{its_user}/{node_id}/#` + `nodes/{node_id}/{capabilities,status}`; subscribe `nodes/{node_id}/config` |

The service account is `MQTT_USER`/`MQTT_PASS` from `.env`. Per-node accounts are created at
enrollment. Both live in `mosquitto.passwd` + `mosquitto.acl` (gitignored, mounted read-only).

## Setup
```bash
scripts/setup_mqtt_auth.sh         # service account in passwd + base ACL (run once)
scripts/enroll_node.sh respeaker-aabbccddeeff 7   # per-node cred for node -> user_id 7
```
`enroll_node.sh` prints `MQTT_USER`/`MQTT_PASS` to enter into the node's provisioning portal
(firmware `provisioning.h`), and reloads the broker (SIGHUP) so it takes effect immediately.

## Why it's secure
- The broker **enforces** the ACL: a per-node cred can only publish under its own
  `nodes/{id}/#` and `voice/{its_user}/{id}/#`. Publishes elsewhere are silently dropped
  (verified: a node publishing `nodes/evil/...` or `voice/999/...` is rejected).
- Because of that, the **topic segments are authenticated identity**. The server therefore
  takes `user_id` + `board_id` from the *topic*, not the payload
  (`ComputeMetricsHandler._ids_from_voice_topic`), so a node can't attribute fabricated data to
  another user even within its own connection. The node registry likewise trusts the *topic*
  `node_id` (a node can't overwrite another's registry entry / retained config).
- Combined with the data-plane `provided_features` allow-list (sanitization), an edge node is
  now constrained to: its own user/board, its own registry entry, and only the 4 trusted
  offloadable features (range-checked, provenance-tagged).

## Notes
- The `system_mode` field is still payload-supplied (the trusted service-account dataset
  injector legitimately sets `dataset`). For live nodes, bind mode at enrollment if needed
  (the ACL already pins their user/board); a future option is a per-node `mode` recorded in
  the registry and enforced server-side.
- TLS (8883) + a separate mongo-express basic-auth credential are recommended hardening on
  untrusted LANs (see `.env.example` / `docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md`).
