# IHearYou ESP-IDF Firmware

Unified ESP-IDF firmware for ReSpeaker audio capture boards supporting depression detection research.

> ## ⚠️ READ THIS FIRST — two transports, one is default
>
> **The authoritative bring-up document is [`BUILD_AND_FLASH.md`](BUILD_AND_FLASH.md).**
> This README predates the plug-and-play work and much of what follows describes the
> **legacy TCP transport only**.
>
> The firmware has a Kconfig **Transport** choice (`menuconfig → IHearYou Firmware
> Configuration → Transport`):
>
> | Transport | Default? | Wi-Fi config | Server address | Server counterpart |
> |---|---|---|---|---|
> | **`TRANSPORT_MQTT_OFFLOAD`** (plug-and-play) | **YES** | **None at build time** — runtime provisioning: NVS creds → `DEFAULT_SITE_SSID` → SoftAP captive portal | **None** — mDNS discovery of `_iotsensing-mqtt._tcp` (NVS / `SERVER_HOST` only as fallbacks) | MQTT broker + `node_registry_service` |
> | `TRANSPORT_LEGACY_TCP` | no | `WIFI_SSID`/`WIFI_PASSWORD` baked via menuconfig | `SERVER_HOST:SERVER_PORT` baked (respeaker_service.py :8010) | `respeaker_service.py` |
>
> **The only build-time settings that matter for a first MQTT-offload flash:**
> 1. `Plug-and-play Provisioning → Bootstrap MQTT username/password` — the defaults
>    (`node-bootstrap` / empty) will be **rejected** by the authenticated broker; set the
>    service-account creds from the VM's `.env` (see BUILD_AND_FLASH.md §5).
> 2. *(Recommended)* `Network Configuration → Server IP Address` = `192.168.1.16` — the
>    default is `192.168.1.100` (wrong host); it is only the last-resort fallback when
>    mDNS yields nothing.
> 3. *(Optional)* `BUTTON_GPIO` — see BUILD_AND_FLASH.md §1a.
>
> Everything else (Wi-Fi, broker discovery, capability negotiation, mode assignment) is
> provisioned **at runtime**. The `WIFI_SSID`/`WIFI_PASSWORD` options below are dead
> config in offload mode.

## Supported Boards

| Board | DSP | Microphones | Features |
|-------|-----|-------------|----------|
| ReSpeaker Lite | XMOS XU316 | 2-mic linear array | IC, AEC, NS, AGC |
| ReSpeaker XVF3800 | XMOS XVF3800 | 4-mic circular array | AEC, Beamforming, De-reverb, DNN-NS, DoA, VAD |

## Prerequisites

### ESP-IDF Installation

This firmware requires ESP-IDF v5.0 or later.

```bash
# Install ESP-IDF (if not already installed)
mkdir -p ~/esp
cd ~/esp
git clone -b v5.2 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3

# Set up environment (run in each terminal session)
. ~/esp/esp-idf/export.sh
```

### Hardware Requirements

- ESP32-S3 DevKit or compatible board
- ReSpeaker Lite or ReSpeaker XVF3800 audio board
- USB cable for programming and debugging

## Building

### ReSpeaker Lite

```bash
cd data_ingestion_layer/firmware
export BOARD_TYPE=lite
idf.py set-target esp32s3
idf.py build
```

### ReSpeaker XVF3800

```bash
cd data_ingestion_layer/firmware
export BOARD_TYPE=xvf3800
idf.py set-target esp32s3
idf.py build
```

## Configuration

### WiFi and Server Settings

Configure network settings using menuconfig:

```bash
idf.py menuconfig
```

Navigate to `IHearYou Firmware Configuration > Network Configuration`:

- **WiFi SSID**: Your WiFi network name
- **WiFi Password**: Your WiFi password
- **Server IP Address**: IP of the machine running `respeaker_service.py`
- **Server Port**: TCP port (default: 8010)

### Audio Settings

Navigate to `IHearYou Firmware Configuration > Audio Configuration`:

- **VAD Energy Threshold**: Voice activity detection sensitivity
- **VAD Hangover Time**: Time to continue streaming after speech ends
- **Audio Chunk Duration**: Duration of audio chunks (default: 5 seconds)
- **Ring Buffer Size**: PSRAM buffer size (default: 512KB)

### XVF3800-Specific Settings

Available only for XVF3800 builds under `IHearYou Firmware Configuration > XVF3800 Configuration`:

- **Enable XVF3800 AGC**: Automatic Gain Control (disabled for depression detection)
- **Enable De-reverberation**: Recommended for cleaner formant extraction
- **Beamforming Mode**: Fixed (0) or Adaptive (1)
- **Include Direction of Arrival**: Include DoA in metadata

## Flashing

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

Replace `/dev/ttyUSB0` with your serial port (e.g., `COM3` on Windows).

## Testing

### Prerequisites

1. Start the respeaker service on your server:
   ```bash
   cd data_ingestion_layer
   python respeaker_service.py
   ```

2. Ensure the ESP32-S3 is connected to the same network as the server.

### Verification Steps

1. **Serial Monitor**: Check boot messages for successful initialization
   ```
   I (xxx) IHEARYOU: Starting IHearYou firmware...
   I (xxx) IHEARYOU: Board: ReSpeaker Lite
   I (xxx) IHEARYOU: Audio: 16000 Hz, 16-bit, 1 ch
   I (xxx) WIFI: Connected to AP, RSSI: -xx
   I (xxx) TCP_CLIENT: Connected! Performing handshake...
   I (xxx) TCP_CLIENT: Handshake successful!
   ```

2. **Server Logs**: Verify connection and audio reception
   ```
   New connection from MAC: xx:xx:xx:xx:xx:xx
   Receiving audio chunks...
   ```

3. **Audio Quality Check**: Use the debug output (enable `ENABLE_AUDIO_DEBUG` in menuconfig)
   ```
   D (xxx) IHEARYOU: Sent 160000 bytes, RMS=1234.5, dBFS=-25.3
   ```

### Telemetry

Enable telemetry in menuconfig to receive periodic status updates:

```
I (xxx) IHEARYOU: Telemetry: uptime=60s, chunks_sent=12, overflows=0, heap=123456, rssi=-55
```

## Architecture

### Task Structure

| Task | Core | Priority | Stack | Description |
|------|------|----------|-------|-------------|
| i2s_capture | 1 | 24 | 8KB | Real-time I2S audio capture |
| vad_proc | 1 | 20 | 4KB | Voice activity detection |
| tcp_sender | 0 | 10 | 8KB | Network transmission |
| dsp_ctrl | 0 | 8 | 4KB | XVF3800 control (XVF3800 only) |
| telemetry | 0 | 3 | 2KB | Status reporting |

### Memory Layout

- **Internal RAM**: Task stacks, DMA buffers
- **PSRAM**: Ring buffer (512KB), speech accumulation buffer

### Data Flow

```
I2S → Soft Limiter → DC Block → Ring Buffer → VAD → Quality Check → Speech Queue → TCP Send
```

## Troubleshooting

### No Audio Received

1. Check I2S connections match pin definitions in `board_config.h`
2. Verify DSP board is powered and running
3. Check serial logs for I2S read errors

### WiFi Connection Issues

1. Verify SSID and password in menuconfig
2. Check signal strength (RSSI > -70 dBm recommended)
3. Ensure 2.4GHz network (ESP32-S3 doesn't support 5GHz)

### TCP Connection Failures

1. Verify server is running and reachable
2. Check firewall settings on server
3. Confirm server IP and port in menuconfig

### Buffer Overflows

1. Increase `RING_BUFFER_SIZE_KB` in menuconfig
2. Check network latency
3. Reduce `AUDIO_CHUNK_DURATION_S` for faster transmission

### Watchdog Resets

1. Check for blocked tasks (network timeouts)
2. Increase watchdog timeout if legitimate long operations
3. Review serial logs before reset for stuck task indication

## Protocol

The firmware communicates with `respeaker_service.py` using a simple TCP protocol:

1. **Handshake**: Send MAC address, receive "READY\n"
2. **Streaming**: Send raw 16-bit PCM audio in 5-second chunks

## License

Copyright IHearYou Research Project. For research use only.
