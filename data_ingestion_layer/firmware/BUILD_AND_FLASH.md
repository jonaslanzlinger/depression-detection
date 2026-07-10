# Build & Flash Guide — IHearYou Node Firmware (ESP32-S3)

Target readers: a developer (or Claude instance) with physical access to the boards.
Covers: toolchain setup → configure → build → flash → first boot → server-side
prerequisites → verification → troubleshooting.

**State of this code:** compiled, flashed and **verified end-to-end on a ReSpeaker
Lite** at first hardware bring-up (2026-07-09, ESP-IDF v5.5.2, Windows bench): zero-touch
Wi-Fi join → mDNS broker discovery → authenticated MQTT → capability negotiation →
VAD-gated speech segments (complete WAV files) arriving on `voice/#`. The first-build
errors this banner used to predict were found and fixed — see the §4 friction list for
what they actually were. The XVF3800 variant's **audio plane is also verified on real
silicon** (same date: control plane + I2S capture + segments on `voice/#`); only its
I2C DSP control (DoA/beam/AGC) still uses the fabricated register protocol — the probe
times out and the firmware degrades gracefully, so audio is unaffected.

---

## 1. Hardware

| Variant | Board | Notes |
|---|---|---|
| `BOARD_RESPEAKER_LITE` | ReSpeaker Lite (XMOS XU316 + ESP32-S3), 2-mic | **Start here.** No XVF3800 dependency. |
| `BOARD_RESPEAKER_XVF3800` | ReSpeaker XVF3800 (ESP32-S3), 4-mic | **Audio verified on silicon 2026-07-09** (ESP32 is I2S *master* here — opposite of the Lite; build with `-B build_xvf -D SDKCONFIG=sdkconfig.xvf`). I2C DSP control (DoA/beam/AGC) still uses a **fabricated register map** — probe times out, gracefully degraded; real XMOS resource-command protocol is future work. |

All units have an attached speaker (I2S TX is initialized in `hal/hal_audio.c` but
playback is not implemented yet).

### 1a. Buttons — identify the user-button GPIO at bring-up

Physical buttons on the actual units:
- **ReSpeaker Lite:** `Usr` (user button) and `Mute`. The `Mute` button is a
  **hardware mic mute at the XU316 codec** (own red LED) — it works with zero firmware
  involvement and is invisible to the ESP32 unless queried over I2C. Treat it as the
  participant's hard-privacy control; the firmware's software mute (below) is the
  *observable* one (dashboard sees it).
- **ReSpeaker XVF3800:** `BUT_A` (user button) and `RST` (reset).

The firmware's gesture handler (short = privacy mute toggle / attest, double = event
marker, long ≥5 s = factory reset) listens on **`CONFIG_BUTTON_GPIO`**
(menuconfig → Plug-and-play Provisioning). Default is 0 (the ESP32-S3 module BOOT
button — always present but may be unreachable inside the case).

**Do NOT guess the Usr/BUT_A GPIO — measure it** (1 minute, board flashed with any
firmware that boots):
```c
// drop into app_main temporarily, or use the monitor + a scratch build:
for (int g of interest in {1,2,3,4,5,6,7,21,38,39,40,41,42,47,48}) ... // or simpler:
```
Simplest: `idf.py monitor`, then in a scratch loop log all input levels once per
second (`gpio_get_level`) across candidate pins while pressing the button — the pin
that toggles is your GPIO. Check the Seeed schematic first (search
"reSpeaker Lite SCH" / "reSpeaker XVF3800 SCH"); if the schematic shows `Usr`/`BUT_A`
wired to the XU316/XVF3800 instead of the ESP32-S3, the button is only reachable over
I2C — fall back to `BUTTON_GPIO=0` (BOOT) or wire the gesture to the DSP-side GPIO
via the driver (XVF3800 GPIO reads are part of its I2C protocol).
Then set `CONFIG_BUTTON_GPIO` accordingly and rebuild.

Connect the board via USB-C. It enumerates as `/dev/ttyACM0` (or `/dev/ttyUSB0`).
If flashing fails to start: hold BOOT, tap RST, release BOOT (manual download mode).

## 2. Toolchain (ESP-IDF v5.1+)

### Windows 11 (PowerShell) — the actual bring-up machine

Use the official **ESP-IDF Windows Installer** (simplest; bundles Python, Git, toolchain,
drivers): download `esp-idf-tools-setup` from
https://dl.espressif.com/dl/esp-idf/ — pick **ESP-IDF v5.2.x**, select the **esp32s3**
target when asked. It creates an **"ESP-IDF 5.2 PowerShell"** shortcut — do ALL work in
that shell (it runs the equivalent of `export.sh` automatically).

```powershell
# in the "ESP-IDF PowerShell" window:
cd C:\work
git clone https://github.com/brunobastosrodrigues/audio-depression-detection.git
cd audio-depression-detection\data_ingestion_layerirmware
idf.py set-target esp32s3
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.lite" reconfigure
idf.py menuconfig          # renders fine in Windows Terminal
idf.py build
idf.py -p COM5 flash monitor   # find the port in Device Manager -> Ports (COM & LPT)
```

Windows specifics:
- **Serial port** is `COMx`, not `/dev/ttyACM0`. Plug the board in, check Device
  Manager; if no port appears install the **CP210x** or **CH34x** VCP driver (depends on
  the board's USB bridge; the installer offers both) — the ESP32-S3 native USB usually
  enumerates as "USB Serial Device" with no extra driver.
- Long-path errors during clone/build: `git config --system core.longpaths true` and
  enable Windows long paths (`gpedit`/registry), or clone to a short path like `C:\w`.
- Antivirus can slow/lock ninja builds — exclude the ESP-IDF and project folders.
- The captive-portal test (§6) works from any phone; no Windows involvement.

### Linux

```bash
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
    cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
mkdir -p ~/esp && cd ~/esp
git clone -b v5.2.2 --recursive --depth 1 --shallow-submodules \
    https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
. ./export.sh          # run in every new shell (or add an alias)
```

The `mdns` dependency is a **managed component** declared in
`main/idf_component.yml`; the IDF component manager fetches it automatically during
the first build (needs internet).

## 3. Configure

```bash
cd <repo>/data_ingestion_layer/firmware
idf.py set-target esp32s3
# Board-variant defaults (pick one):
cp sdkconfig.defaults sdkconfig.defaults.bak   # only if you need to inspect
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.lite" reconfigure
idf.py menuconfig
```

In `menuconfig → IHearYou Firmware Configuration`:

| Setting | Value for the home (bbr) deployment |
|---|---|
| Target Board | ReSpeaker Lite |
| **Transport** | **Plug-and-play MQTT offload** (default) |
| Plug-and-play Provisioning → Default site SSID | leave `IHearYou-Net` (not present at home → portal is used) — or set it to the home SSID to skip the portal entirely |
| Default site password | (matching) |
| **Bootstrap MQTT username/password** | see §5 — for first bring-up use the service account from the VM's `.env` (`MQTT_USER` / `MQTT_PASS`) |
| Network Configuration → Server IP Address | `192.168.1.16` (VM; used only as last-resort fallback when mDNS fails) |

PSRAM: the ESP32-S3 module needs `CONFIG_SPIRAM=y` + `CONFIG_SPIRAM_USE_MALLOC=y`
(should come from `sdkconfig.defaults`; verify — `transport/mqtt_sender.c` and the
MQTT out-buffer allocate from PSRAM).

## 4. Build, flash, monitor

```bash
idf.py build                       # first build: fix errors as they surface, they are expected
idf.py -p /dev/ttyACM0 flash monitor   # Ctrl+] to exit monitor
```

First-build friction — found and **fixed** at first hardware bring-up (2026-07-09,
IDF v5.5.2). Already in the tree; listed so future IDF bumps know what to re-check:
- `mqtt_client.h` name collision — resolved by **renaming ours to `net/mqtt_wrapper.h`**.
  The old advice (angle-include or reorder dirs) does not work: a quoted
  `#include "mqtt_client.h"` inside `net/` always resolves to the sibling header
  (quoted includes search the includer's directory first), and `main/net` is on the
  `-I` path ahead of esp-mqtt anyway. Diverging the basenames is the only robust fix.
- Missing includes (hard errors on 5.5): `<stdbool.h>` in `hal/hal_audio.h`;
  `freertos/FreeRTOS.h` + `freertos/task.h` in `hal/hal_audio.c`;
  `freertos/FreeRTOS.h` in `audio/audio_buffer.h`.
- `-Werror=format-truncation`: the LWT JSON is 69 bytes worst-case vs
  `lwt_payload[64]` — widened to 96 in `net/mqtt_wrapper.h`.
- Telemetry task stack: hardcoded 2048 overflowed at the first telemetry tick
  (boot crash-loop) → `TASK_STACK_TELEMETRY` 4096 (commit 764ff23).
- Partition table refit to the real 8 MB flash; OTA-ready layout (commit 2f5bbe9).
- **I2S framing — the audio-plane bug:** the XU316 I2S firmware transmits
  16 kHz / 32-bit / **stereo Philips** frames (confirmed against
  respeaker/ReSpeaker_Lite's official examples). Reading them as mono/MSB slices
  samples across slot boundaries → speech-invariant full-scale noise while clocks
  and pins (BCK 8 / WS 7 / DIN 44) are all fine. Slave config must be Philips +
  stereo, keeping slot 0 (the processed mic) — see `I2S_SLOT_STRIDE` in
  `config/board_config.h` and the deinterleave in `main.c`. Diagnosed with the
  `CONFIG_ENABLE_AUDIO_DEBUG`-gated raw-sample stats in the capture loop — flip
  that on for any future board/DSP bring-up before theorizing.

Still-relevant version-drift watch items (unchanged):
- esp-mqtt config struct field names differ slightly across IDF minor versions
  (`broker.address.uri`, `credentials.authentication.password` are v5.x names).
- mDNS API: `esp_ipaddr_ntoa` / result-struct field names per the managed component version.
- Provisioning portal: `esp_netif_create_default_wifi_ap()` must be called once —
  if `wifi_manager` already created the STA netif, AP creation is additive (APSTA);
  set `WIFI_MODE_APSTA` if plain `WIFI_MODE_AP` conflicts.
- `-Werror` is on: unused-variable warnings in `#if`-gated paths are build errors.

## 5. Server-side prerequisites (on the VM, 192.168.1.16)

> **STATUS 2026-07-09: ALL DONE — the server side is live and verified.** MQTT is
> LAN-exposed on `192.168.1.16:1883` (auth enforced, anonymous rejected), the stack
> (mqtt, mongodb, node_registry_service, voice_metrics, temporal, analysis) is up,
> and avahi advertises `_iotsensing-mqtt._tcp` -> 192.168.1.16:1883 (IPv4, LAN
> interface only). The full negotiate loop was verified end-to-end with a simulated
> node: capabilities advert -> retained assignment `{"mode":"segments","vad_gated":true,...}`.
> **For menuconfig, set Bootstrap MQTT username/password to `MQTT_USER`/`MQTT_PASS`
> from `~/audio-depression-detection/.env` on the VM** (ssh rodrigues@192.168.1.16,
> pw semsenha). Remaining human step: voice enrollment (item 5) once the dashboard runs.

The stack lives in `~/audio-depression-detection` (docker compose). What was done:

1. **Broker reachable from the LAN.** `docker-compose.yml` currently binds MQTT to
   `127.0.0.1:1883` (hardening PR #81). For node bring-up change the mosquitto port
   mapping to `1883:1883` (LAN-exposed, auth still required) and `docker compose up -d mqtt`.
2. **Credentials for the node.** Two options:
   - *Quick bring-up:* use the service account (`MQTT_USER`/`MQTT_PASS` from `.env`)
     as the firmware's Bootstrap MQTT user — it has `readwrite #` ACL, so
     capabilities/status/voice all work immediately.
   - *Proper (per-node ACL, do after first success):* `scripts/enroll_node.sh
     respeaker-<mac12> <user_id> live` mints a per-node account restricted to its own
     topics; put those creds in the firmware Bootstrap fields (or wait for the
     `nodes/{id}/provision` push flow, which is designed but not yet implemented
     server-side).
3. **node_registry_service running** (compose service) — it answers the capability
   advert with the retained `nodes/{id}/config` assignment. Without it the node stays
   in "waiting for dashboard approval" (it still connects and publishes status).
4. **mDNS advertisement** (`deploy/mdns/`, PR #86) so the node discovers the broker:
   needs avahi on the VM host advertising `_iotsensing-mqtt._tcp` port 1883.
   Fallback if you skip this: the firmware uses its stored/Kconfig `SERVER_HOST`.
5. **Speaker/voice enrollment for live mode:** the scene gatekeeper fail-closes without
   a voice profile — enroll the target speaker via the dashboard (Live mode) before
   expecting `raw_metrics` to appear.

## 6. First boot — what you should see

```
IHEARYOU: Starting IHearYou firmware...
offload_app: unprovisioned; trying default site SSID 'IHearYou-Net'
prov: portal AP up: IHearYou-Setup-XXXX          # if no default network
```
1. Join `IHearYou-Setup-XXXX` from a phone → captive portal opens → enter Wi-Fi +
   room name → node reboots and joins.
2. `discovery: mDNS sink 192.168.1.16:1883` (or the fallback warning).
3. `mqtt: connected` → capabilities published (retained) → assignment received:
   `offload_app: assignment: mode=1 vad_gated=1`.
4. Speak near the node → `mqtt_sender` publishes AudioPayload JSON to
   `voice/{user}/{node_id}/{room}` → server `ComputeMetricsHandler` ingests it.

Verify end-to-end on the VM:
```bash
mosquitto_sub -h localhost -u "$MQTT_USER" -P "$MQTT_PASS" -t 'nodes/#' -v   # status/capabilities
mosquitto_sub -h localhost -u "$MQTT_USER" -P "$MQTT_PASS" -t 'voice/#' -v | head -c 400
# then check Mongo raw_metrics for new records (metrics_computation logs too)
```

Button checks: short press → status shows `"muted":true` (and voice/# goes quiet);
double press → one message on `nodes/{id}/marker`; hold 5 s → reboots into the portal.

## 6b. XVF VAD calibration (MANDATORY before any deployment — field-test blocker)

Symptom found in the 2026-07-10 overnight pilot: XVF3800 boards published ~1200 false
"speech" segments/hour around the clock (bedroom board at 3 AM while the occupant slept;
27k noise segments in 18h fleet-wide). Cause: the VAD energy threshold (80) was tuned for
the pre-gain-fix silicon; after the digital-gain fix (0→16) the amplified noise floor sits
above it, so the energy VAD triggers on silence.

Procedure (per board variant, once):
1. Build with the new default (`VAD_THRESHOLD=400` for XVF) and flash one XVF board.
2. Put it in a QUIET room, nobody speaking, 15 minutes. Watch the broker:
   `mosquitto_sub -t 'voice/#'` filtered to that board — **acceptance: ~0 segments in
   15 min** (occasional one on a door slam is fine).
3. Speak at 2–3 m at normal volume — segments MUST appear within a sentence. If not,
   the threshold overshot: halve it and repeat. If silence still streams, raise by 50%.
4. The RAWDBG serial prints (if still compiled in) show per-chunk energy — the ideal
   threshold is ≈3× the observed silent-room energy.
5. Record the final value in this file. Lite boards (threshold 150, no gain change) were
   NOT affected — do not touch them.

Server-side note: the server now also runs a speech gate before recognition (voice_metrics
`VAD_GATE` log lines), so miscalibrated nodes can no longer poison the pipeline — but they
still waste radio/power and undermine the behavioral traces, so node calibration remains
mandatory.

## 6c. XVF ROOT CAUSE (supersedes 6b): over-gain saturation, not VAD threshold

Spectral analysis of live XVF segments (2026-07-10, coordinator) overturned the initial
"raise VAD threshold" hypothesis. The captured "noise" is NOT broadband room noise — it is
**loud, near-clipping tonal content**:
- peak amplitudes 28,957-30,478 of int16 max 32,767 -> the front end is **saturating**;
- dominant tones ~50 Hz + harmonics (60/71/109 Hz) = **mains hum**, plus a 640 Hz device
  tone and near-Nyquist artifacts;
- 11-23% of spectral energy below 120 Hz.

Cause: `board_config.h DIGITAL_GAIN_SHIFT 16` right-shifts the 32-bit I2S sample keeping the
TOP 16 bits, where strongly-coupled mains hum dominates -> the int16 result clips ~30k and
the energy VAD triggers continuously. The 2026-07-09 gain 0->16 change over-corrected: 0
saturated at the LSB end (deaf VAD), 16 saturates at the MSB end (loud hum). Raising the
VAD threshold (6b) cannot fix a signal clipping at 30,000 — it is necessary but not
sufficient. **Do the following at the bench instead:**

1. **Sweep DIGITAL_GAIN_SHIFT** (try 12, 13, 14) while watching silent-room peak amplitude
   via the RAWDBG serial print: target silent-room peak well under clipping (< ~5,000) and
   speech at 2-3 m reaching a healthy 5,000-15,000. Set the value that achieves both.
2. **Add a high-pass filter (~80-100 Hz)** in the capture path (main.c, after the gain
   shift, before VAD). Human speech energy is > 100 Hz; mains hum is 50 Hz + harmonics, so
   an 80 Hz high-pass removes the dominant offender regardless of gain. This is the robust
   fix; do it even if the gain sweep helps.
3. Then apply the VAD-threshold calibration (6b) and the silent-room acceptance test.

Server-side, the gate now rejects saturated/hum/tonal segments explicitly (peak>28k,
sub-120Hz energy fraction, near-pure-tone), so un-reflashed nodes no longer poison the
pipeline — but they still waste power/bandwidth and their behavioral traces are garbage,
so the gain+high-pass fix remains required before the field test.

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| No `IHearYou-Setup` AP | Board booted? Monitor output? GPIO0 held low accidentally (case button pressing BOOT)? |
| Portal loads but save does nothing | Phone kept mobile data on (captive portal detection) — disable data, retry |
| `no broker found` | mDNS advert not running → set Server IP in menuconfig as fallback; broker port bound to 127.0.0.1 (see §5.1) |
| `broker refused connection` | Wrong bootstrap creds / ACL — test the same creds with `mosquitto_sub` from another host |
| Connects, no assignment | `node_registry_service` not running, or its account lacks `nodes/#` read ACL |
| Voice published, no metrics | Scene gatekeeper fail-closed (no speaker enrollment, §5.5) or `voice_metrics` service down |
| Random reboots under load | PSRAM not enabled → the 384 KB MQTT out-buffer landed in internal RAM |

## 8. Deliberately out of scope (for now)

- Speaker playback (`hal_audio_play`, `nodes/{id}/play`) — HIL replay rig, next phase.
- XVF3800 board variant — real register protocol needed.
- `nodes/{id}/provision` per-node credential push — server side not implemented.
- Dashboard "Pending → Approve" flow — registry currently auto-assigns any
  advertising node; the button attest messages are published but not yet consumed.
