# GitHub Issue: Phase 1 Integration Review

**Title:** Phase 1 Integration Review: ESP-IDF Unified Firmware
**Label:** Jules

---

## Summary

The Phase 1 implementation of the ESP-IDF unified firmware for ReSpeaker boards is complete and ready for review.

## Implementation Overview

A complete ESP-IDF 5.x firmware has been implemented supporting both ReSpeaker Lite (XMOS XU316) and ReSpeaker XVF3800 boards through a unified codebase with board-specific configuration.

## Files Created

### Project Structure
- `data_ingestion_layer/firmware/CMakeLists.txt` - Main project CMake with board type selection
- `data_ingestion_layer/firmware/sdkconfig.defaults` - Common SDK configuration
- `data_ingestion_layer/firmware/sdkconfig.defaults.lite` - ReSpeaker Lite specific config
- `data_ingestion_layer/firmware/sdkconfig.defaults.xvf3800` - XVF3800 specific config
- `data_ingestion_layer/firmware/partitions.csv` - Partition table (with OTA support)
- `data_ingestion_layer/firmware/main/Kconfig.projbuild` - Board selection menu
- `data_ingestion_layer/firmware/main/CMakeLists.txt` - Component CMakeLists

### Configuration
- `main/config/board_config.h` - Board-specific defines (I2S pins, gain, features)
- `main/config/audio_config.h` - Audio processing configuration

### Hardware Abstraction Layer
- `main/hal/hal_audio.h` / `hal_audio.c` - I2S capture with ESP-IDF 5.x API
  - Soft-knee limiter (not hard clipping)
  - DC offset removal via high-pass filter

### Audio Processing
- `main/audio/audio_buffer.h` / `audio_buffer.c` - PSRAM ring buffer (512KB)
- `main/audio/vad.h` / `vad.c` - Energy-based VAD with adaptive calibration
- `main/audio/audio_quality.h` / `audio_quality.c` - Quality metrics (RMS, dBFS, clipping detection)

### Network
- `main/network/wifi_manager.h` / `wifi_manager.c` - WiFi with reconnection handling
- `main/network/tcp_client.h` / `tcp_client.c` - TCP client with MAC handshake protocol

### System
- `main/system/watchdog.h` / `watchdog.c` - Watchdog manager with task tracking

### XVF3800 Driver (Phase 2 Preview)
- `main/drivers/xvf3800/xvf3800.h` / `xvf3800.c` - XVF3800 DSP control
- `main/drivers/xvf3800/xvf3800_i2c.h` / `xvf3800_i2c.c` - Low-level I2C interface

### Main Application
- `main/main.c` - Main application with multi-core task architecture

## Key Design Decisions

1. **ESP-IDF 5.x API**: Using new I2S channel API (`i2s_chan_handle_t`) instead of deprecated `i2s_config_t`

2. **Multi-Core Architecture**:
   - Core 1: Audio tasks (I2S capture, VAD processing)
   - Core 0: Network tasks (WiFi, TCP sender, DSP control)

3. **Board-Specific Configuration**: Single codebase with `#ifdef` and Kconfig for board selection

4. **Audio Quality**: Soft-knee limiter to preserve jitter/shimmer features for depression detection

5. **VAD Calibration**: Adaptive noise floor with per-board initial thresholds

## Review Checklist

- [ ] Code structure and organization
- [ ] ESP-IDF 5.x API usage correctness
- [ ] Memory allocation strategy (PSRAM vs internal)
- [ ] Task priorities and stack sizes
- [ ] Error handling and recovery
- [ ] Compatibility with existing `respeaker_service.py` protocol

## Build Instructions

```bash
# For ReSpeaker Lite
cd data_ingestion_layer/firmware
BOARD_TYPE=lite idf.py build

# For ReSpeaker XVF3800
cd data_ingestion_layer/firmware
BOARD_TYPE=xvf3800 idf.py build
```

## Related Documentation

- `docs/firmware/UNIFIED_FIRMWARE_DESIGN.md` - Full design document with PI review

---

**Instructions:** Copy this content and create a new issue on GitHub with the label "Jules".
