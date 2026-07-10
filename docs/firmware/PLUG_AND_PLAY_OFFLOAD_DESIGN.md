# ReSpeaker Lite (ESP32-S3 + XVF3800) — Plug-and-Play Edge-Offload Firmware Design

Status: **design sketch**. Extends the existing ESP-IDF firmware in
`data_ingestion_layer/firmware/` to (a) be **plug-and-play** — flash once, power on anywhere,
and it onboards itself — and (b) speak the **capability-negotiation + edge-offload protocol**
already implemented server-side (PRs #82/#83/#84). Skeletons for the new components live under
`main/{provisioning,net,protocol,features}/`.

---

## 1. Goals

1. **Plug-and-play.** No per-deployment recompile. Flash the same binary to every node; on
   first boot it provisions Wi-Fi, **discovers the backend sink on the LAN**, connects, and
   starts streaming. Re-positioning a mic = unplug, move, plug back in.
2. **Privacy-preserving edge offload.** The node advertises what it can compute on-device;
   the server negotiates an assignment; the node sends **features** (no raw audio) when it
   can, **VAD-gated segments** otherwise, **raw** as last resort.
3. **Zero-touch recovery.** Lose Wi-Fi / broker / power → reconnect and resume without a human.
4. **Build on what exists.** Keep the working I2S capture → energy-VAD → speech-gating path;
   add MQTT transport, discovery, provisioning, the protocol, and on-node features alongside.

---

## 2. Plug-and-play boot flow (the core state machine)

```
        ┌─────────────┐  creds in NVS?  ┌──────────────┐  joined   ┌───────────────┐
 power→ │  BOOT/INIT  │ ───── no ─────▶ │ PROVISIONING │ ────────▶ │  WIFI_CONNECT │
        └─────────────┘                 │ (SoftAP/BLE) │           └───────┬───────┘
              │ yes                      └──────────────┘                   │ got IP
              └──────────────────────────────────────────────────────────▶ │
                                                                            ▼
   ┌──────────┐ assigned ┌───────────┐ broker ┌───────────┐  found  ┌───────────────┐
   │ STREAMING│◀──config─│ NEGOTIATE │◀───────│ MQTT_CONN │◀────────│ DISCOVER_SINK │
   └────┬─────┘          │(advertise)│  conn   └───────────┘  mDNS   └───────────────┘
        │ link/broker lost                                     (fallback: NVS / Kconfig host)
        └──────────────────────────────▶ back-off + reconnect ──────────────▶ (re-enter)
```

States (implemented as a small FreeRTOS state-machine task; see `app/offload_app.h`):

| State | What happens | Exit |
|---|---|---|
| `BOOT` | NVS init, HAL/XVF3800 init, read stored creds + broker | creds present → WIFI_CONNECT; else PROVISIONING |
| `PROVISIONING` | Bring up SoftAP `IHearYou-Setup-XXXX` (or BLE) using ESP-IDF `wifi_provisioning`; user submits Wi-Fi creds once (phone/captive portal). Persist to NVS. LED = slow blue blink | creds saved → WIFI_CONNECT |
| `WIFI_CONNECT` | STA connect via existing `wifi_manager`; ret/backoff | got IP → DISCOVER_SINK |
| `DISCOVER_SINK` | **mDNS** query for `_iotsensing-mqtt._tcp` → broker host:port. Fallbacks: last-good broker in NVS, then compiled `CONFIG_SERVER_HOST`. LED = cyan | resolved → MQTT_CONN |
| `MQTT_CONN` | Connect to broker (TLS optional), auth (user/pass from provisioning or NVS) | CONNACK → NEGOTIATE |
| `NEGOTIATE` | Publish **capabilities** (retained) to `nodes/{id}/capabilities`; subscribe `nodes/{id}/config`; wait for assignment | assignment received → STREAMING |
| `STREAMING` | Run the audio pipeline in the assigned **mode** (raw / segments / features); periodic heartbeat. LED = green | broker/link lost → reconnect; new config → re-apply live |

**Onboarding UX target:** flash → power → (one-time phone Wi-Fi setup) → green LED within ~10 s
of seeing the network. After the first setup, power-cycles go straight BOOT→…→STREAMING.

---

## 3. Identity & discovery

- **node_id** = stable per-board id = the eFuse MAC (`esp_efuse_mac_get_default`) formatted
  `respeaker-aabbccddeeff`. Used as the MQTT client-id, the `nodes/{id}/…` topic segment, and
  the registry key (matches `node_registry_service` keying on `node_id`).
- **Sink discovery (mDNS).** The backend advertises the broker as a service the node resolves
  at runtime, so the server IP is **never compiled in**:
  - Service: `_iotsensing-mqtt._tcp` (port 1883), TXT `user=…` optional, `tls=0/1`.
  - Server side: add an mDNS/Avahi advertisement next to the `mqtt` container (a tiny
    `avahi-publish` sidecar or host Avahi service file) — documented in §11.
  - Node: `mdns_query_ptr("_iotsensing-mqtt", "_tcp", …)` → first/strongest responder.
  - **Fallbacks** (in order): mDNS → `broker_host` saved in NVS from last good session →
    compiled `CONFIG_SERVER_HOST`. This keeps it working on networks without mDNS.

---

## 4. Protocol contracts (must match the server exactly)

These mirror `framework/node_capabilities.py` + `framework/payloads/AudioPayload.py`. The
firmware builds/parses these as JSON (cJSON, already available in ESP-IDF).

### 4.1 Advertise — publish to `nodes/{id}/capabilities` (retained, QoS1)
```json
{
  "node_id": "respeaker-aabbccddeeff",
  "firmware": "ihearyou-fw/2.0.0",
  "hardware": "esp32-s3+xvf3800",
  "psram_mb": 8,
  "provides": {
    "vad": true, "aec": true, "doa": true, "beamforming": true, "speaker_gate": false,
    "features": ["snr", "spectral_flatness", "temporal_modulation", "spectral_modulation"]
  },
  "sample_rate": 16000, "frame_ms": 20, "max_payload_bytes": 8192
}
```
`provides` is derived from the board feature flags (`board_config.h`: `HAS_DOA_DETECTION`,
`HAS_BEAMFORMING`, …) + which `features` the firmware build actually computes. **Only advertise
features in the server's `OFFLOADABLE_FEATURES` allow-list** — anything else is ignored by
`negotiate_assignment()`.

### 4.2 Assignment — receive on `nodes/{id}/config` (retained)
```json
{ "mode": "features", "vad_gated": true,
  "features": ["snr", "spectral_flatness"], "raw_on_uncertain": true,
  "report_interval_ms": 1000 }
```
`mode ∈ {raw, segments, features}`. The node applies it **live** (no reflash).

### 4.3 Data — publish to `voice/{user_id}/{board_id}/{env}`
Same `AudioPayload` the server already parses (`ComputeMetricsHandler`). Mode-dependent:

- **raw / segments:** `data` = base64 WAV/PCM (segments = VAD-gated only). No `provided_features`.
- **features:** `data` = "" (or a tiny preview), `provided_features` = the node-computed
  metrics. The server gap-filler (`core/gap_filler.select_tasks`) skips those extractors.
```json
{ "type": "audio", "timestamp": 1719400000.0, "sample_rate": 16000,
  "board_id": "respeaker-aabbccddeeff", "user_id": 1, "environment_name": "livingroom",
  "system_mode": "live",
  "provided_features": { "snr": 12.4, "spectral_flatness": 0.18 },
  "node_capabilities_version": "ihearyou-fw/2.0.0" }
```
`user_id`: until on-node speaker-id exists, send the node's configured occupant id (from
provisioning) or omit and let the server recognize. DoA (read from XVF3800, currently dropped)
rides along in metadata for scene analysis.

### 4.4 Heartbeat — `nodes/{id}/status` (retained): uptime, RSSI, heap, mode, last-DoA.
Drives the dashboard online/stale indicator (Edge Nodes page reads `last_seen`).

---

## 5. Component architecture (new modules in **bold**)

```
main/
  app/offload_app.{c,h}        ** the boot state machine + task wiring (§2)
  provisioning/provisioning.{c,h}  ** SoftAP/BLE Wi-Fi provisioning + NVS creds
  net/discovery.{c,h}          ** mDNS sink discovery (+ NVS/Kconfig fallback)
  net/mqtt_client.{c,h}        ** esp-mqtt wrapper: auth, pub/sub, reconnect, the topics
  protocol/node_protocol.{c,h} ** build capabilities/payload JSON, parse assignment (cJSON)
  features/edge_features.{c,h} ** on-node feature extraction (esp-dsp): snr, flatness, modulations
  audio/   (exists)            -- I2S capture, ring buffer, energy VAD, quality  [reuse]
  drivers/xvf3800/ (exists)    -- I2C control + DoA  [needs real packet protocol, §9]
  network/wifi_manager.* (exists) -- STA connect/reconnect  [reuse]
  network/tcp_client.*  (exists) -- legacy raw-TCP path  [keep as a transport fallback]
  config, hal, system          -- [reuse]
```

Transport is selected by the assignment: a **transport router** sits where `tcp_sender` is
today, fanning the speech queue to the MQTT publisher (raw/segments/features) or the legacy TCP
sender. The VAD decision (already centralized in the VAD task) stays the single speech gate.

---

## 6. Task layout (extends the current 5-task design)

| Task | Core | Prio | Role |
|---|---|---|---|
| `i2s_capture` | 1 | 24 | unchanged — I2S DMA → ring buffer |
| `vad_proc` | 1 | 20 | unchanged — energy VAD gates speech into chunks |
| **`feature_proc`** | 1 | 12 | when mode=features: compute edge features per chunk (esp-dsp) |
| **`mqtt_pub`** | 0 | 10 | dequeue chunks → build AudioPayload (per mode) → publish |
| **`offload_app`** | 0 | 9 | the state machine: provision/discover/connect/negotiate, apply config |
| `dsp_ctrl` (XVF) | 0 | 8 | read DoA every 100 ms → shared `latest_doa` (now actually stored) |
| **`heartbeat`** | 0 | 3 | replaces telemetry log: publish `nodes/{id}/status` |

Core-1 stays the real-time audio core; networking/protocol on Core-0. `feature_proc` at prio
12 yields to VAD (20) so capture is never starved; budget ~5–10 ms/chunk for the cheap features.

---

## 7. On-node feature extraction (`features/edge_features`)

Compute **only** the server's `OFFLOADABLE_FEATURES` (cheap, FFT/energy-based, S3-feasible):

| Feature | Method on S3 | Notes |
|---|---|---|
| `snr` | speech-frame energy vs noise-floor (the VAD already tracks both) | nearly free — reuse `vad` state |
| `spectral_flatness` | geomean/aritmean of `esp_dsp` FFT power spectrum | one `dsps_fft2r` per frame |
| `temporal_modulation` | 2–8 Hz band energy of the log-mel envelope | needs a small mel bank + IIR band-pass |
| `spectral_modulation` | FFT along the mel axis at ~2 cyc/oct | reuse the mel frames |

Use `esp-dsp` (`dsps_fft2r_fc32`, windowing, mel). **Validate on-device values against the
server extractors before trusting them** (publish both for a calibration period; compare).
Heavier markers (jitter/shimmer/HNR/formants/pyin-F0, speaker embeddings) **stay server-side** —
the node never claims them, so the gap-filler keeps computing them from segments.

---

## 8. Security

- **Wi-Fi creds**: entered once via provisioning, stored in **NVS** (encrypted-flash recommended).
- **MQTT auth**: username/password — matches the broker auth from PR #81. Provisioned alongside
  Wi-Fi (the setup portal collects broker user/pass) or carried in the mDNS TXT + a per-site
  shared secret. Stored in NVS.
- **TLS** (recommended for non-trusted LANs): `esp-mqtt` over 8883 with the broker CA pinned in
  flash; mDNS TXT `tls=1` flips transport. Mosquitto side: add a `listener 8883` + certs.
- **Topic ACLs** (broker): restrict each node to `nodes/{id}/#` and `voice/#` publish — a
  mosquitto ACL file keyed by username. Prevents a rogue node impersonating others.
- **Factory reset**: long-press BOOT (GPIO0) ≥5 s → wipe NVS creds → re-enter PROVISIONING.

---

## 9. The hard dependency: real XVF3800 control protocol

The current driver uses a **fabricated flat register map** (`xvf3800.h` `0x00–0x72`) that will
not work on silicon. The real XVF3800 uses a **packetized resource-id / command-id I2C protocol**
(correctly described in `UNIFIED_FIRMWARE_DESIGN.md:451-491`). Before any on-hardware bring-up:
- Reimplement `xvf3800_i2c` as `xvf_read_control(resource, cmd, *buf, len)` /
  `xvf_write_control(...)` per XMOS's control protocol + the ReSpeaker control map.
- Wire real ops: AEC enable/freeze/reset (currently missing), beamforming mode/direction, DoA
  read (`xvf3800_get_doa` exists but against fake regs), hardware-VAD read (unused).
- I2S stays 16 kHz mono (32-bit on the wire → 16-bit) — that part is sound.

This is the single biggest correctness gap and is **hardware-gated** (needs the board + a logic
analyzer). Everything in §2–§8 can be developed/CI-built without it; mark XVF calls behind
`HAS_XVF3800` so the Lite (codec-only) build runs the full plug-n-play + offload path today.

---

## 10. Phased implementation plan

1. **P1 — Plug-and-play transport (no XVF needed):** add `provisioning`, `discovery`,
   `mqtt_client`, `node_protocol`; route the existing speech-gated chunks to MQTT in
   `segments` mode; advertise capabilities (vad only). Outcome: flash a **Lite** board, set
   Wi-Fi once, it auto-finds the broker and appears on the Edge Nodes dashboard, streaming
   VAD-gated segments. *Fully testable on current hardware.*
2. **P2 — Features mode:** add `edge_features` (snr, spectral_flatness first), advertise them,
   honor `mode=features`, run the calibration cross-check vs server extractors.
3. **P3 — XVF3800 real protocol:** reimplement the control layer (§9); advertise aec/doa/
   beamforming; feed DoA + AEC reference; flip to the XVF board build.
4. **P4 — Hardening:** TLS, broker ACLs, encrypted NVS, OTA (partitions already support it),
   factory-reset button, watchdog coverage of the new tasks.

---

## 11. Server-side companions (small, separate work)

- **mDNS advertisement** for the broker so nodes can discover it (host Avahi `.service` file or
  a sidecar container advertising `_iotsensing-mqtt._tcp` on 1883).
- **Provisioning occupant mapping** (optional): a way to bind a node_id → user_id/environment
  at setup time (the Edge Nodes dashboard page is the natural home for this).
- Broker **ACL file** keyed by node username (security §8).

---

## 12. What this buys

Flash-and-forget nodes that self-onboard, send **features instead of raw audio** wherever the
S3 can compute them (raw PHI never leaves the room), fall back gracefully on weaker nodes, and
show up live on the dashboard — all negotiated, no per-node configuration.
