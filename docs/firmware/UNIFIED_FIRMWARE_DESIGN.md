# Unified ESP-IDF Firmware Design Document
## ReSpeaker Lite (XU316) & ReSpeaker XVF3800 Multi-Board Support

**Document Version:** 1.0.0
**Date:** 2026-01-11
**Status:** Initial Design (Round 1)
**Author:** Engineering Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Hardware Specifications](#2-hardware-specifications)
3. [Architecture Design](#3-architecture-design)
4. [Audio Pipeline Design](#4-audio-pipeline-design)
5. [Control Interface Design](#5-control-interface-design)
6. [Network Layer Design](#6-network-layer-design)
7. [Code Organization](#7-code-organization)
8. [Build Configuration](#8-build-configuration)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [References](#10-references)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the architecture for a **unified ESP-IDF firmware** that supports both the ReSpeaker Lite (XMOS XU316) and ReSpeaker XVF3800 boards. The firmware will be configurable via compile-time `#ifdef` directives to target specific hardware while sharing common networking, buffering, and protocol code.

### 1.2 Design Goals

| Priority | Goal | Rationale |
|----------|------|-----------|
| P0 | 16kHz/16-bit mono audio capture | Required for depression detection acoustic analysis |
| P0 | TCP streaming with MAC handshake | Integration with existing `respeaker_service.py` |
| P0 | Edge VAD with hangover | Bandwidth optimization, privacy preservation |
| P1 | XVF3800 DSP control | Leverage 4-mic beamforming for far-field capture |
| P1 | Unified codebase | Maintainability across board variants |
| P2 | Audio quality metrics | On-board RMS, peak, clipping detection |
| P2 | OTA firmware updates | Field deployment capability |

### 1.3 Project Context: IHearYou Depression Detection System

The firmware serves as the **data ingestion layer** for the IHearYou system, which:
- Captures naturalistic speech in home environments
- Extracts 25+ acoustic features mapped to DSM-5 depression indicators
- Supports speaker verification for multi-occupant households
- Processes 5-second audio chunks at 16kHz sample rate

**Critical Audio Quality Requirements:**
- Sample Rate: 16,000 Hz (non-negotiable for acoustic feature extraction)
- Bit Depth: 16-bit PCM (int16)
- Channel: Mono (post-DSP processed)
- Chunk Duration: 5 seconds (80,000 samples = 160KB per chunk)
- VAD: Edge-based with 500ms hangover time

---

## 2. Hardware Specifications

### 2.1 ReSpeaker Lite (XMOS XU316)

| Component | Specification | Notes |
|-----------|---------------|-------|
| **MCU** | XIAO ESP32-S3 | 240MHz dual-core, 8MB PSRAM, 8MB Flash |
| **DSP** | XMOS XU316 | 16 logical cores, 2400 MIPS |
| **Microphones** | 2x PDM MEMS | Far-field up to 3m |
| **Audio Codec** | TLV320AIC3204 | I2C address: 0x18 |
| **DSP Features** | IC, AEC, NS, AGC | On-chip processing |
| **I2S Mode** | Slave (XU316 master) | ESP32 receives from XU316 |
| **I2S Pins** | BCK=8, WS=7, DIN=44 | Fixed by PCB design |
| **I2C Bus** | Shared (XU316 + Codec) | ESP32 as master |
| **Firmware Modes** | I2S or USB | Requires reflash to switch |

**Block Diagram:**
```
┌─────────────────────────────────────────────────────────┐
│                    ReSpeaker Lite                        │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────────┐ │
│  │ 2x PDM  │───▶│ XU316    │───▶│ XIAO ESP32-S3       │ │
│  │ Mics    │    │ DSP      │I2S │ ┌─────────────────┐ │ │
│  └─────────┘    │ IC+AEC+  │    │ │ WiFi TCP Stream │ │ │
│                 │ NS+AGC   │    │ └─────────────────┘ │ │
│  ┌─────────┐    └────┬─────┘    └─────────┬───────────┘ │
│  │TLV320   │◀──I2C───┘                    │             │
│  │AIC3204  │                              │             │
│  └─────────┘                              ▼             │
│                                      To Server          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 ReSpeaker XVF3800

| Component | Specification | Notes |
|-----------|---------------|-------|
| **MCU** | XIAO ESP32-S3 | 240MHz dual-core, 8MB PSRAM, 8MB Flash |
| **DSP** | XMOS XVF3800 | xcore.ai architecture |
| **Microphones** | 4x PDM MEMS | Circular array, 360° capture up to 5m |
| **Audio Codec** | Integrated in XVF3800 | No external codec |
| **DSP Features** | AEC, Beamforming, De-reverb, DoA, DNN-NS, VAD, AGC (60dB) | Advanced pipeline |
| **I2S Mode** | Configurable Master/Slave | INT-Device firmware required |
| **I2S Pins** | BCK=8, WS=7, DOUT=44, DIN=43 | Bidirectional I2S |
| **I2C Address** | 0x2C | Control interface |
| **MCLK Requirement** | 12.288 MHz | XVF3800 generates when master |
| **GPIO** | 3x GPI, 5x GPO | Button input, LED/mute control |

**Block Diagram:**
```
┌─────────────────────────────────────────────────────────────────┐
│                       ReSpeaker XVF3800                          │
│  ┌─────────────┐    ┌──────────────────────┐    ┌─────────────┐ │
│  │ 4x PDM Mics │───▶│ XVF3800 DSP          │───▶│ XIAO        │ │
│  │ (circular)  │    │ ┌──────────────────┐ │I2S │ ESP32-S3    │ │
│  └─────────────┘    │ │ AEC              │ │    │ ┌─────────┐ │ │
│                     │ │ 3-Beam Former    │ │    │ │ WiFi    │ │ │
│                     │ │ De-reverberation │ │    │ │ TCP     │ │ │
│                     │ │ DNN Noise Supp.  │ │    │ │ Stream  │ │ │
│                     │ │ DoA Detection    │ │    │ └─────────┘ │ │
│                     │ │ VAD              │ │    └──────┬──────┘ │
│                     │ │ AGC (60dB)       │ │           │        │
│                     │ └──────────────────┘ │           ▼        │
│                     │          ▲           │      To Server     │
│                     └──────────┼───────────┘                    │
│                           I2C Control                           │
│                           (0x2C)                                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Critical Hardware Differences

| Feature | ReSpeaker Lite | XVF3800 | Firmware Impact |
|---------|----------------|---------|-----------------|
| Microphone Count | 2 | 4 | XVF3800 better far-field |
| Beamforming | None | 3-beam adaptive | XVF3800 tracks speakers |
| Direction of Arrival | No | Yes | XVF3800 can report speaker angle |
| I2C Control | Codec only | Full DSP control | XVF3800 needs control driver |
| I2S Direction | RX only | RX + TX | XVF3800 supports reference audio |
| Edge VAD | ESP32 firmware | On-chip option | Can offload to XVF3800 |
| De-reverberation | No | Yes | XVF3800 better in reverberant rooms |
| Noise Suppression | Basic | DNN-based | XVF3800 superior in noisy environments |

---

## 3. Architecture Design

### 3.1 Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Main App    │  │ Config Mgr  │  │ OTA Update Handler      │  │
│  │ (app_main)  │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      AUDIO PROCESSING LAYER                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ VAD Engine  │  │ Audio       │  │ Quality Metrics         │  │
│  │ (Silero/    │  │ Chunker     │  │ Calculator              │  │
│  │  Energy)    │  │ (5 sec)     │  │ (RMS, Peak, dBFS)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      HARDWARE ABSTRACTION LAYER                  │
│  ┌─────────────────────────────┐  ┌─────────────────────────┐   │
│  │ Board Driver (HAL)          │  │ DSP Control Driver      │   │
│  │ ┌─────────┐ ┌─────────────┐ │  │ ┌─────────┐ ┌─────────┐ │   │
│  │ │ LITE    │ │ XVF3800     │ │  │ │ XU316   │ │ XVF3800 │ │   │
│  │ │ Driver  │ │ Driver      │ │  │ │ Ctrl    │ │ Ctrl    │ │   │
│  │ └─────────┘ └─────────────┘ │  │ └─────────┘ └─────────┘ │   │
│  └─────────────────────────────┘  └─────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                      NETWORK LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ WiFi        │  │ TCP Client  │  │ Protocol Handler        │  │
│  │ Manager     │  │ (Streaming) │  │ (MAC Handshake)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      RTOS & BUFFER LAYER                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FreeRTOS    │  │ Ring Buffer │  │ Event Groups            │  │
│  │ Tasks       │  │ (PSRAM)     │  │ (Sync)                  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      ESP-IDF DRIVERS                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │ I2S     │ │ I2C     │ │ WiFi    │ │ GPIO    │ │ NVS       │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Task Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ESP32-S3 Dual Core                        │
├─────────────────────────────┬───────────────────────────────────┤
│         CORE 0              │            CORE 1                  │
│   (Protocol/Network)        │       (Audio/Real-time)           │
├─────────────────────────────┼───────────────────────────────────┤
│                             │                                    │
│  ┌───────────────────────┐  │  ┌────────────────────────────┐   │
│  │ wifi_manager_task     │  │  │ i2s_capture_task           │   │
│  │ Priority: 5           │  │  │ Priority: 24 (highest)     │   │
│  │ Stack: 4096           │  │  │ Stack: 8192                │   │
│  │ - WiFi connection     │  │  │ - I2S DMA read             │   │
│  │ - Reconnection logic  │  │  │ - Sample conversion        │   │
│  └───────────────────────┘  │  │ - Ring buffer write        │   │
│                             │  └────────────────────────────┘   │
│  ┌───────────────────────┐  │                                    │
│  │ tcp_sender_task       │  │  ┌────────────────────────────┐   │
│  │ Priority: 10          │  │  │ vad_processor_task         │   │
│  │ Stack: 8192           │  │  │ Priority: 20               │   │
│  │ - TCP connection      │  │  │ Stack: 4096                │   │
│  │ - MAC handshake       │  │  │ - Energy-based VAD         │   │
│  │ - Audio transmission  │  │  │ - Hangover state machine   │   │
│  └───────────────────────┘  │  │ - Speech/silence decision  │   │
│                             │  └────────────────────────────┘   │
│  ┌───────────────────────┐  │                                    │
│  │ dsp_control_task      │  │  ┌────────────────────────────┐   │
│  │ Priority: 8           │  │  │ quality_metrics_task       │   │
│  │ Stack: 4096           │  │  │ Priority: 15               │   │
│  │ - XVF3800 I2C cmds    │  │  │ Stack: 2048                │   │
│  │ - DoA queries         │  │  │ - RMS calculation          │   │
│  │ - Parameter updates   │  │  │ - Peak detection           │   │
│  └───────────────────────┘  │  │ - Clipping count           │   │
│  (XVF3800 only)             │  └────────────────────────────┘   │
│                             │                                    │
└─────────────────────────────┴───────────────────────────────────┘
```

### 3.3 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           AUDIO DATA FLOW                                 │
└──────────────────────────────────────────────────────────────────────────┘

[LITE Path]
PDM Mics ──▶ XU316 (IC+AEC+NS) ──▶ I2S ──▶ ESP32 DMA ──▶ Ring Buffer
                                                              │
                                                              ▼
                                                    ┌─────────────────┐
                                                    │ VAD Processor   │
                                                    │ (Energy-based)  │
                                                    └────────┬────────┘
                                                             │
                                    ┌────────────────────────┼────────────────────────┐
                                    │                        │                        │
                                    ▼                        ▼                        ▼
                           [is_speech=true]         [hangover period]         [is_speech=false]
                                    │                        │                        │
                                    └────────────┬───────────┘                        │
                                                 ▼                                    │
                                    ┌────────────────────────┐                        │
                                    │ Speech Buffer (5 sec)  │                 [Discard]
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ Quality Metrics Calc   │
                                    │ (RMS, Peak, dBFS)      │
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ TCP Sender Task        │
                                    │ (Binary Stream)        │
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │ respeaker_service.py   │
                                    │ (Port 8010)            │
                                    └────────────────────────┘

[XVF3800 Path - Enhanced]
4x PDM Mics ──▶ XVF3800 (AEC+Beamform+Dereverb+DNN-NS+AGC) ──▶ I2S ──▶ ESP32 DMA
       │                          │
       │                          ├──▶ DoA (Direction of Arrival)
       │                          │         │
       │                          │         ▼
       │                          │    ┌──────────────┐
       │                          │    │ I2C Control  │◀── ESP32
       │                          │    └──────────────┘
       │                          │
       │                          └──▶ On-chip VAD (optional)
       │
       └──[Reference Audio Path - for AEC]──◀── Speaker I2S TX
```

---

## 4. Audio Pipeline Design

### 4.1 I2S Configuration

#### Common Configuration (Both Boards)

```c
// Target audio format for depression detection
#define AUDIO_SAMPLE_RATE       16000   // Hz
#define AUDIO_BIT_DEPTH         16      // bits
#define AUDIO_CHANNELS          1       // mono
#define AUDIO_CHUNK_DURATION_S  5       // seconds
#define AUDIO_CHUNK_SAMPLES     (AUDIO_SAMPLE_RATE * AUDIO_CHUNK_DURATION_S)  // 80000
#define AUDIO_CHUNK_BYTES       (AUDIO_CHUNK_SAMPLES * sizeof(int16_t))       // 160000

// I2S DMA Configuration
#define I2S_DMA_BUF_COUNT       16      // Number of DMA buffers
#define I2S_DMA_BUF_LEN         512     // Samples per buffer
#define I2S_DMA_BUFFER_BYTES    (I2S_DMA_BUF_LEN * sizeof(int32_t))  // 2048 bytes

// Calculated latency: (DMA_BUF_COUNT * DMA_BUF_LEN) / SAMPLE_RATE
// = (16 * 512) / 16000 = 0.512 seconds of buffering
```

#### ReSpeaker Lite Specific

```c
#ifdef CONFIG_BOARD_RESPEAKER_LITE

#define I2S_BCK_PIN             8
#define I2S_WS_PIN              7
#define I2S_DIN_PIN             44
#define I2S_DOUT_PIN            -1      // Not used (RX only)

// XU316 outputs 32-bit samples, we extract 16-bit
#define I2S_BITS_PER_SAMPLE     I2S_BITS_PER_SAMPLE_32BIT
#define I2S_CHANNEL_FORMAT      I2S_CHANNEL_FMT_ONLY_LEFT
#define I2S_COMM_FORMAT         I2S_COMM_FORMAT_STAND_I2S

// ESP32 is I2S slave (XU316 provides clocks)
#define I2S_MODE                (I2S_MODE_SLAVE | I2S_MODE_RX)

// Digital gain (bit shift for amplification)
#define DIGITAL_GAIN_SHIFT      16

// TLV320AIC3204 Audio Codec
#define CODEC_I2C_ADDR          0x18
#define CODEC_I2C_SDA           5
#define CODEC_I2C_SCL           6

#endif // CONFIG_BOARD_RESPEAKER_LITE
```

#### ReSpeaker XVF3800 Specific

```c
#ifdef CONFIG_BOARD_RESPEAKER_XVF3800

#define I2S_BCK_PIN             8
#define I2S_WS_PIN              7
#define I2S_DIN_PIN             43      // RX from XVF3800
#define I2S_DOUT_PIN            44      // TX for reference audio (AEC)

// XVF3800 outputs 32-bit samples at 16kHz or 48kHz
#define I2S_BITS_PER_SAMPLE     I2S_BITS_PER_SAMPLE_32BIT
#define I2S_CHANNEL_FORMAT      I2S_CHANNEL_FMT_ONLY_LEFT  // Processed mono output
#define I2S_COMM_FORMAT         I2S_COMM_FORMAT_STAND_I2S

// XVF3800 is I2S master (generates MCLK, BCK, WS)
#define I2S_MODE                (I2S_MODE_SLAVE | I2S_MODE_RX | I2S_MODE_TX)

// No digital gain needed - XVF3800 has 60dB AGC
#define DIGITAL_GAIN_SHIFT      0

// XVF3800 Control Interface
#define XVF3800_I2C_ADDR        0x2C
#define XVF3800_I2C_SDA         5
#define XVF3800_I2C_SCL         6

// GPIO for XVF3800 control
#define XVF3800_GPI_COUNT       3
#define XVF3800_GPO_COUNT       5
#define XVF3800_MUTE_PIN        -1      // TODO: Determine from schematic

#endif // CONFIG_BOARD_RESPEAKER_XVF3800
```

### 4.2 Voice Activity Detection (VAD)

#### Energy-Based VAD (Common Implementation)

```c
typedef struct {
    float threshold;            // Energy threshold for speech detection
    uint32_t hangover_ms;       // Time to continue after speech ends
    uint32_t last_speech_time;  // Timestamp of last detected speech
    bool is_streaming;          // Current streaming state
    float noise_floor;          // Adaptive noise floor estimate
    float noise_floor_alpha;    // Smoothing factor for noise floor
} vad_state_t;

// Default configuration
#define VAD_THRESHOLD_DEFAULT           150.0f
#define VAD_HANGOVER_MS_DEFAULT         500
#define VAD_NOISE_FLOOR_ALPHA           0.01f   // Slow adaptation

// VAD algorithm
typedef enum {
    VAD_RESULT_SILENCE,
    VAD_RESULT_SPEECH,
    VAD_RESULT_HANGOVER
} vad_result_t;
```

#### XVF3800 Hardware VAD (Optional Enhancement)

```c
#ifdef CONFIG_BOARD_RESPEAKER_XVF3800

// XVF3800 can provide hardware VAD via I2C query
typedef struct {
    bool use_hardware_vad;      // Use XVF3800 internal VAD
    bool use_software_vad;      // Use ESP32 energy-based VAD
    uint8_t vad_sensitivity;    // 0-255, higher = more sensitive
} xvf3800_vad_config_t;

// Hybrid approach: Hardware VAD for primary detection,
// software VAD for validation and edge cases

#endif
```

### 4.3 Audio Quality Metrics

```c
typedef struct {
    float rms;                  // Root Mean Square energy
    float peak_amplitude;       // Maximum absolute sample value
    float db_fs;                // Decibels relative to full scale
    float dynamic_range;        // 20*log10(peak/rms)
    float snr;                  // Signal-to-noise ratio (vs noise floor)
    uint32_t clipping_count;    // Samples at ±32767
    float zero_crossing_rate;   // For speech/noise discrimination
} audio_quality_metrics_t;

// Calculate metrics for each 5-second chunk before transmission
void calculate_quality_metrics(const int16_t* samples, size_t count,
                               audio_quality_metrics_t* metrics);
```

---

## 5. Control Interface Design

### 5.1 XVF3800 I2C Control Protocol

```c
// XVF3800 I2C packet structure
typedef struct __attribute__((packed)) {
    uint8_t resource_id;        // Command category
    uint8_t command_id;         // Specific command
    uint16_t payload_length;    // Length of following data
    uint8_t payload[];          // Variable-length payload
} xvf3800_command_t;

// Response structure
typedef struct __attribute__((packed)) {
    uint8_t status;             // 0x00 = success
    uint8_t payload[];          // Response data
} xvf3800_response_t;

// Key commands for depression detection use case
typedef enum {
    // Beamforming control
    XVF3800_CMD_GET_DOA         = 0x80,  // Get Direction of Arrival
    XVF3800_CMD_SET_BEAM_ANGLE  = 0x81,  // Fix beam to specific angle
    XVF3800_CMD_SET_BEAM_AUTO   = 0x82,  // Enable automatic beam tracking

    // AGC control
    XVF3800_CMD_SET_AGC_ENABLED = 0x40,
    XVF3800_CMD_SET_AGC_TARGET  = 0x41,  // Target output level

    // Noise suppression
    XVF3800_CMD_SET_NS_LEVEL    = 0x50,  // Noise suppression aggressiveness

    // VAD
    XVF3800_CMD_GET_VAD_STATE   = 0x60,  // Query current VAD state
    XVF3800_CMD_SET_VAD_SENS    = 0x61,  // Set VAD sensitivity

    // AEC
    XVF3800_CMD_AEC_FREEZE      = 0x30,  // Freeze AEC adaptation
    XVF3800_CMD_AEC_RESET       = 0x31,  // Reset AEC filters

    // System
    XVF3800_CMD_GET_VERSION     = 0x00,  // Firmware version
    XVF3800_CMD_GET_BUILD_INFO  = 0x01,  // Build configuration
} xvf3800_command_id_t;
```

### 5.2 XVF3800 Driver API

```c
// Initialization
esp_err_t xvf3800_init(i2c_port_t i2c_port);
esp_err_t xvf3800_deinit(void);

// Beamforming
esp_err_t xvf3800_get_doa(int16_t* azimuth_degrees);
esp_err_t xvf3800_set_fixed_beam(int16_t azimuth_degrees);
esp_err_t xvf3800_enable_auto_beam(bool enable);

// AGC
esp_err_t xvf3800_set_agc_enabled(bool enable);
esp_err_t xvf3800_set_agc_target_db(int8_t target_db);

// Noise Suppression
esp_err_t xvf3800_set_noise_suppression_level(uint8_t level);  // 0-10

// VAD
esp_err_t xvf3800_get_vad_state(bool* is_speech);
esp_err_t xvf3800_set_vad_sensitivity(uint8_t sensitivity);

// AEC
esp_err_t xvf3800_aec_freeze(bool freeze);
esp_err_t xvf3800_aec_reset(void);

// System
esp_err_t xvf3800_get_version(char* version_str, size_t max_len);
```

### 5.3 TLV320AIC3204 Codec Control (ReSpeaker Lite)

```c
// Minimal codec control - XU316 handles most processing
// Codec is primarily for speaker output (not critical for capture)

esp_err_t tlv320_init(i2c_port_t i2c_port);
esp_err_t tlv320_set_output_volume(uint8_t volume);  // 0-127
esp_err_t tlv320_mute(bool mute);
```

---

## 6. Network Layer Design

### 6.1 WiFi Manager

```c
typedef enum {
    WIFI_STATE_DISCONNECTED,
    WIFI_STATE_CONNECTING,
    WIFI_STATE_CONNECTED,
    WIFI_STATE_RECONNECTING,
    WIFI_STATE_ERROR
} wifi_state_t;

typedef struct {
    char ssid[32];
    char password[64];
    uint8_t max_retry_count;
    uint32_t retry_interval_ms;
    wifi_state_t current_state;
} wifi_manager_config_t;

// API
esp_err_t wifi_manager_init(const wifi_manager_config_t* config);
esp_err_t wifi_manager_start(void);
wifi_state_t wifi_manager_get_state(void);
esp_err_t wifi_manager_get_mac(char* mac_str, size_t max_len);  // "AA:BB:CC:DD:EE:FF"
```

### 6.2 TCP Streaming Protocol

```c
// Connection handshake (matches respeaker_service.py expectations)
// 1. ESP32 connects to server:8010
// 2. ESP32 sends MAC address (17 bytes): "AA:BB:CC:DD:EE:FF"
// 3. Server responds: "READY\n"
// 4. ESP32 begins streaming raw audio data

typedef enum {
    TCP_STATE_DISCONNECTED,
    TCP_STATE_CONNECTING,
    TCP_STATE_HANDSHAKE,
    TCP_STATE_STREAMING,
    TCP_STATE_ERROR
} tcp_state_t;

typedef struct {
    char server_host[64];
    uint16_t server_port;
    uint32_t connect_timeout_ms;
    uint32_t handshake_timeout_ms;
    uint32_t reconnect_delay_ms;
    tcp_state_t current_state;
} tcp_client_config_t;

// API
esp_err_t tcp_client_init(const tcp_client_config_t* config);
esp_err_t tcp_client_connect(void);
esp_err_t tcp_client_send(const uint8_t* data, size_t len);
bool tcp_client_is_connected(void);
```

### 6.3 Audio Streaming

```c
// Audio packet structure (binary, no framing - matches current implementation)
// Server expects raw int16 PCM samples, little-endian

typedef struct {
    bool vad_gated;             // Only send when speech detected
    uint32_t chunk_interval_ms; // Target interval between sends
    size_t max_chunk_bytes;     // Maximum bytes per TCP send
} audio_stream_config_t;

// Streaming state
typedef struct {
    uint32_t bytes_sent;
    uint32_t chunks_sent;
    uint32_t last_send_time_ms;
    bool is_streaming;
} audio_stream_stats_t;
```

---

## 7. Code Organization

### 7.1 Directory Structure

```
firmware/
├── CMakeLists.txt
├── sdkconfig.defaults
├── sdkconfig.defaults.lite          # ReSpeaker Lite overrides
├── sdkconfig.defaults.xvf3800       # XVF3800 overrides
├── partitions.csv
│
├── main/
│   ├── CMakeLists.txt
│   ├── Kconfig.projbuild            # Board selection menu
│   ├── main.c                       # app_main entry point
│   │
│   ├── config/
│   │   ├── board_config.h           # Board-specific #ifdef definitions
│   │   ├── audio_config.h           # Audio pipeline parameters
│   │   ├── network_config.h         # WiFi/TCP parameters
│   │   └── credentials.h.example    # Template for user credentials
│   │
│   ├── hal/                         # Hardware Abstraction Layer
│   │   ├── hal_audio.h              # Common audio interface
│   │   ├── hal_audio.c              # Dispatcher to board-specific
│   │   ├── hal_audio_lite.c         # ReSpeaker Lite implementation
│   │   ├── hal_audio_xvf3800.c      # XVF3800 implementation
│   │   ├── hal_i2c.h                # I2C abstraction
│   │   └── hal_i2c.c
│   │
│   ├── drivers/                     # Device-specific drivers
│   │   ├── xvf3800/
│   │   │   ├── xvf3800.h            # Public API
│   │   │   ├── xvf3800.c            # I2C command implementation
│   │   │   ├── xvf3800_commands.h   # Command definitions
│   │   │   └── xvf3800_types.h      # Data structures
│   │   └── tlv320/
│   │       ├── tlv320.h
│   │       └── tlv320.c
│   │
│   ├── audio/                       # Audio processing
│   │   ├── audio_capture.h          # I2S capture task
│   │   ├── audio_capture.c
│   │   ├── audio_buffer.h           # Ring buffer management
│   │   ├── audio_buffer.c
│   │   ├── vad.h                    # Voice Activity Detection
│   │   ├── vad.c
│   │   ├── audio_quality.h          # Quality metrics
│   │   └── audio_quality.c
│   │
│   ├── network/                     # Network stack
│   │   ├── wifi_manager.h
│   │   ├── wifi_manager.c
│   │   ├── tcp_client.h
│   │   ├── tcp_client.c
│   │   └── protocol.h               # Handshake protocol
│   │
│   └── utils/                       # Utilities
│       ├── logging.h                # ESP_LOG wrappers
│       ├── nvs_storage.h            # Non-volatile storage
│       └── nvs_storage.c
│
├── components/                      # Reusable ESP-IDF components
│   └── ring_buffer/
│       ├── CMakeLists.txt
│       ├── ring_buffer.h
│       └── ring_buffer.c
│
└── test/                            # Unit tests
    ├── test_vad.c
    ├── test_audio_quality.c
    └── test_ring_buffer.c
```

### 7.2 Board Selection (Kconfig)

```kconfig
# main/Kconfig.projbuild

menu "IHearYou Firmware Configuration"

choice BOARD_TYPE
    prompt "Target Board"
    default BOARD_RESPEAKER_LITE
    help
        Select the target ReSpeaker board variant.

config BOARD_RESPEAKER_LITE
    bool "ReSpeaker Lite (XMOS XU316, 2-mic)"
    help
        ReSpeaker Lite with XMOS XU316 DSP and dual microphone array.
        Supports: IC, AEC, NS, AGC
        I2S Mode: Slave (XU316 is master)

config BOARD_RESPEAKER_XVF3800
    bool "ReSpeaker XVF3800 (4-mic, advanced DSP)"
    help
        ReSpeaker XVF3800 with 4-microphone circular array.
        Supports: AEC, Beamforming, De-reverb, DNN-NS, DoA, VAD, AGC
        I2S Mode: Configurable (recommended: XVF3800 as master)

endchoice

config WIFI_SSID
    string "WiFi SSID"
    default "myssid"
    help
        SSID of the WiFi network to connect to.

config WIFI_PASSWORD
    string "WiFi Password"
    default "mypassword"
    help
        Password for the WiFi network.

config SERVER_HOST
    string "Server IP Address"
    default "192.168.1.100"
    help
        IP address of the machine running respeaker_service.py

config SERVER_PORT
    int "Server Port"
    default 8010
    help
        TCP port for the respeaker service.

config VAD_THRESHOLD
    int "VAD Energy Threshold"
    default 150
    range 50 500
    help
        Energy threshold for voice activity detection.
        Higher values = less sensitive, fewer false positives.

config VAD_HANGOVER_MS
    int "VAD Hangover Time (ms)"
    default 500
    range 100 2000
    help
        Time to continue streaming after speech ends.

endmenu
```

---

## 8. Build Configuration

### 8.1 CMakeLists.txt (Main)

```cmake
# firmware/CMakeLists.txt

cmake_minimum_required(VERSION 3.16)

# Include board-specific sdkconfig defaults
if(DEFINED ENV{BOARD_TYPE})
    set(BOARD_TYPE $ENV{BOARD_TYPE})
else()
    set(BOARD_TYPE "lite")
endif()

if(BOARD_TYPE STREQUAL "xvf3800")
    set(SDKCONFIG_DEFAULTS
        "sdkconfig.defaults"
        "sdkconfig.defaults.xvf3800"
    )
else()
    set(SDKCONFIG_DEFAULTS
        "sdkconfig.defaults"
        "sdkconfig.defaults.lite"
    )
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ihearyou_firmware)
```

### 8.2 sdkconfig.defaults

```ini
# Common defaults for all boards

# ESP32-S3 specific
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_SPEED_80M=y

# FreeRTOS
CONFIG_FREERTOS_HZ=1000
CONFIG_FREERTOS_UNICORE=n

# WiFi
CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=10
CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=32

# Logging
CONFIG_LOG_DEFAULT_LEVEL_INFO=y

# Optimization
CONFIG_COMPILER_OPTIMIZATION_PERF=y
```

### 8.3 sdkconfig.defaults.xvf3800

```ini
# XVF3800-specific overrides

CONFIG_BOARD_RESPEAKER_XVF3800=y

# Larger stack for DSP control task
CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192

# I2C for XVF3800 control
CONFIG_I2C_MASTER_TX_BUF_DISABLE=y
CONFIG_I2C_MASTER_RX_BUF_DISABLE=y
```

### 8.4 Build Commands

```bash
# Build for ReSpeaker Lite
cd firmware
idf.py set-target esp32s3
BOARD_TYPE=lite idf.py build

# Build for XVF3800
BOARD_TYPE=xvf3800 idf.py build

# Flash
idf.py -p /dev/ttyACM0 flash monitor
```

---

## 9. Implementation Roadmap

### 9.1 Phase 1: Core Infrastructure (Estimated: High Priority)

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Project setup with ESP-IDF | `CMakeLists.txt`, `Kconfig.projbuild` |
| 1.2 | Board configuration system | `config/board_config.h` |
| 1.3 | I2S HAL for ReSpeaker Lite | `hal/hal_audio_lite.c` |
| 1.4 | Ring buffer component | `components/ring_buffer/` |
| 1.5 | Basic VAD implementation | `audio/vad.c` |
| 1.6 | WiFi manager | `network/wifi_manager.c` |
| 1.7 | TCP client with handshake | `network/tcp_client.c` |

**Deliverable:** Functional streaming from ReSpeaker Lite matching current Arduino behavior.

### 9.2 Phase 2: XVF3800 Support (Estimated: Medium Priority)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | XVF3800 I2C driver | `drivers/xvf3800/` |
| 2.2 | I2S HAL for XVF3800 | `hal/hal_audio_xvf3800.c` |
| 2.3 | DoA integration | `drivers/xvf3800/xvf3800.c` |
| 2.4 | Hardware VAD option | `audio/vad.c` (extended) |

**Deliverable:** XVF3800 streaming with advanced DSP features accessible.

### 9.3 Phase 3: Quality & Optimization (Estimated: Lower Priority)

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Audio quality metrics | `audio/audio_quality.c` |
| 3.2 | OTA update support | `main/ota.c` |
| 3.3 | NVS configuration storage | `utils/nvs_storage.c` |
| 3.4 | Power optimization | Various |
| 3.5 | Unit tests | `test/` |

**Deliverable:** Production-ready firmware with monitoring and update capability.

---

## 10. References

### 10.1 Hardware Documentation

1. **ReSpeaker Lite**
   - [Seeed Studio Product Page](https://www.seeedstudio.com/ReSpeaker-Lite-p-5928.html)
   - [GitHub - ReSpeaker_Lite](https://github.com/respeaker/ReSpeaker_Lite)

2. **ReSpeaker XVF3800**
   - [Seeed Studio Product Page](https://www.seeedstudio.com/ReSpeaker-XVF3800-4-Mic-Array-With-XIAO-ESP32S3-p-6489.html)
   - [CNX Software Review](https://www.cnx-software.com/2025/07/29/respeaker-xmos-xvf3800-4-mic-array-board-features-esp32-s3-module-works-over-usb/)

3. **XMOS XVF3800**
   - [XMOS XVF3800 Programming Guide v3.2.1](https://www.xmos.com/documentation/XM-014888-PC/pdf/xvf3800_programming_guide_v3.2.1.pdf)
   - [Voice Processing Pipeline](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/datasheet/03_audio_pipeline.html)
   - [Control Commands Appendix](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/AA_control_command_appendix.html)
   - [Device Interfaces](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/datasheet/05_device_interfaces.html)

### 10.2 ESP-IDF Documentation

4. **ESP32-S3 I2S**
   - [ESP-IDF I2S Documentation v5.5.2](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html)
   - [I2S DMA Settings Explained (atomic14)](https://www.atomic14.com/2021/04/20/esp32-i2s-dma-buf-len-buf-count)

5. **ESP32 I2C**
   - [ESP-IDF I2C Documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/i2c.html)

### 10.3 Project Context

6. **IHearYou System**
   - Current Arduino firmware: `data_ingestion_layer/board-code/respeaker.ino`
   - ReSpeaker service: `data_ingestion_layer/respeaker_service.py`
   - Audio payload format: `data_ingestion_layer/framework/payloads/AudioPayload.py`

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-11 | Engineering Team | Initial design document |

---

**END OF ROUND 1: INITIAL DESIGN DOCUMENT**

---

# ROUND 2a: FIRMWARE DEVELOPER PEER REVIEW

**Reviewer:** Senior Firmware Engineer
**Date:** 2026-01-11
**Review Focus:** Implementation feasibility, embedded systems best practices, edge cases

---

## Overall Assessment

The design document provides a solid foundation but has several areas requiring attention before implementation. The architecture is sound, but specific implementation details need refinement for production robustness.

**Rating:** 🟡 **Conditionally Approved** (Address critical issues before implementation)

---

## Critical Issues (Must Fix)

### Issue 1: ESP-IDF I2S API Version Mismatch

**Problem:** The document references legacy I2S API (`i2s_config_t`, `i2s_driver_install`) which is deprecated in ESP-IDF v5.x. The XIAO ESP32-S3 ships with ESP-IDF 5.x by default.

**Current (Deprecated):**
```c
i2s_config_t i2s_config = { ... };
i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
```

**Required (New API):**
```c
i2s_chan_handle_t rx_handle;
i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_SLAVE);
i2s_new_channel(&chan_cfg, NULL, &rx_handle);

i2s_std_config_t std_cfg = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
    .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = GPIO_NUM_8,
        .ws = GPIO_NUM_7,
        .dout = I2S_GPIO_UNUSED,
        .din = GPIO_NUM_44,
    },
};
i2s_channel_init_std_mode(rx_handle, &std_cfg);
```

**Recommendation:** Update all I2S code examples to use the new `i2s_channel` API. Add a migration note for developers familiar with legacy API.

---

### Issue 2: Ring Buffer Memory Allocation

**Problem:** The design uses FreeRTOS ring buffer but doesn't specify PSRAM allocation for large audio buffers. The 5-second chunk (160KB) exceeds typical internal RAM availability.

**Current:**
```c
audio_ringbuf = xRingbufferCreate(32 * 1024, RINGBUF_TYPE_BYTEBUF);
```

**Required:**
```c
// Allocate ring buffer in PSRAM for large audio buffers
StaticRingbuffer_t *buffer_struct = heap_caps_malloc(sizeof(StaticRingbuffer_t), MALLOC_CAP_SPIRAM);
uint8_t *buffer_storage = heap_caps_malloc(RING_BUFFER_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
audio_ringbuf = xRingbufferCreateStatic(RING_BUFFER_SIZE, RINGBUF_TYPE_BYTEBUF, buffer_storage, buffer_struct);
```

**Recommendation:** Add explicit PSRAM allocation for:
- Ring buffer (256KB recommended for double-buffering)
- 5-second speech accumulation buffer (160KB)
- Quality metrics working buffer

---

### Issue 3: Task Priority Inversion Risk

**Problem:** The `i2s_capture_task` (Priority 24) and `tcp_sender_task` (Priority 10) share the ring buffer. If TCP blocks on network I/O, the ring buffer could overflow, causing audio loss.

**Recommendation:** Implement a watermark-based flow control:
```c
typedef struct {
    size_t high_watermark;      // 75% full - slow down capture
    size_t low_watermark;       // 25% full - resume normal
    bool throttling;
} flow_control_t;

// In i2s_capture_task:
if (xRingbufferGetCurFreeSize(audio_ringbuf) < flow_control.high_watermark) {
    flow_control.throttling = true;
    ESP_LOGW(TAG, "Ring buffer high watermark - consider network issues");
}
```

---

### Issue 4: Missing Watchdog Configuration

**Problem:** No watchdog timer configuration specified. Long-running audio capture without watchdog risks unrecoverable hangs.

**Recommendation:** Add task watchdog configuration:
```c
// In sdkconfig.defaults
CONFIG_ESP_TASK_WDT=y
CONFIG_ESP_TASK_WDT_TIMEOUT_S=30
CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0=y
CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU1=n  // Audio core

// In audio capture task
esp_task_wdt_add(NULL);  // Subscribe to watchdog
// ... in main loop
esp_task_wdt_reset();    // Feed watchdog
```

---

### Issue 5: XVF3800 I2C Timing

**Problem:** The XVF3800 I2C control protocol requires specific timing between command and response. The design doesn't specify required delays.

**From XMOS documentation:** The host should wait at least 1ms between sending a command and reading the response to allow the XVF3800 to process the command.

**Recommendation:** Add timing constants:
```c
#define XVF3800_CMD_RESPONSE_DELAY_MS   2   // Min 1ms, use 2ms for safety
#define XVF3800_I2C_TIMEOUT_MS          100
#define XVF3800_I2C_CLOCK_SPEED_HZ      100000  // 100kHz (not 400kHz fast mode)
```

---

## Major Recommendations

### Recommendation 1: Add Error Recovery State Machine

The current design lacks explicit error handling for audio pipeline failures.

```c
typedef enum {
    AUDIO_STATE_INIT,
    AUDIO_STATE_CONFIGURING,
    AUDIO_STATE_RUNNING,
    AUDIO_STATE_ERROR_I2S,
    AUDIO_STATE_ERROR_BUFFER,
    AUDIO_STATE_RECOVERING,
    AUDIO_STATE_FATAL
} audio_state_t;

typedef struct {
    audio_state_t state;
    uint32_t error_count;
    uint32_t last_error_time;
    uint32_t recovery_attempts;
} audio_state_machine_t;
```

### Recommendation 2: Add Telemetry/Diagnostics

For field debugging, add periodic telemetry:
```c
typedef struct {
    uint32_t uptime_seconds;
    uint32_t audio_chunks_captured;
    uint32_t audio_chunks_sent;
    uint32_t buffer_overflows;
    uint32_t tcp_reconnections;
    float avg_audio_rms;
    uint8_t wifi_rssi;
    uint32_t free_heap;
    uint32_t free_psram;
} firmware_telemetry_t;
```

Consider adding an optional telemetry MQTT topic or periodic TCP message.

### Recommendation 3: Graceful Degradation

Add fallback behavior for XVF3800 control failures:
```c
// If I2C communication with XVF3800 fails, continue with default DSP settings
// rather than halting audio capture
if (xvf3800_init(I2C_NUM_0) != ESP_OK) {
    ESP_LOGW(TAG, "XVF3800 control unavailable - using default DSP settings");
    config.dsp_control_enabled = false;
    // Continue with audio capture - DSP still processes audio via I2S
}
```

### Recommendation 4: Boot Time Optimization

Audio capture should start as quickly as possible. Current sequence:
1. WiFi connect (1-5 seconds)
2. TCP connect (0.5-2 seconds)
3. Handshake (0.5 seconds)
4. Start I2S

**Proposed optimization:** Start I2S capture immediately, buffer audio, then transmit once network is ready.

---

## Minor Issues

| Issue | Location | Recommendation |
|-------|----------|----------------|
| Magic numbers | VAD threshold 150 | Add calibration procedure or auto-threshold |
| No logging levels | Throughout | Use ESP_LOG with appropriate levels |
| Stack sizes | Task creation | Validate with `uxTaskGetStackHighWaterMark()` |
| No heap monitoring | Runtime | Add periodic `esp_get_free_heap_size()` logging |
| GPIO not validated | Pin definitions | Add compile-time assertions for pin conflicts |

---

## Approved Sections

✅ Layer architecture design
✅ Task distribution across cores
✅ Network protocol (MAC handshake)
✅ Build configuration system
✅ Directory structure

---

## Required Actions Before Implementation

1. **[CRITICAL]** Update I2S code to ESP-IDF 5.x API
2. **[CRITICAL]** Add PSRAM allocation for audio buffers
3. **[CRITICAL]** Add task watchdog configuration
4. **[HIGH]** Implement buffer overflow protection
5. **[HIGH]** Add XVF3800 I2C timing delays
6. **[MEDIUM]** Design error recovery state machine
7. **[MEDIUM]** Add firmware telemetry

---

**Firmware Developer Sign-off:** Conditionally approved pending resolution of critical issues.

---

# ROUND 2b: SOUND ENGINEER PEER REVIEW

**Reviewer:** Audio/DSP Engineer
**Date:** 2026-01-11
**Review Focus:** Audio quality, DSP pipeline integrity, acoustic feature preservation

---

## Overall Assessment

The design adequately addresses basic audio capture requirements but requires refinement to ensure captured audio is suitable for reliable acoustic feature extraction in depression detection. Several audio engineering best practices are missing.

**Rating:** 🟡 **Conditionally Approved** (Audio quality concerns must be addressed)

---

## Critical Audio Quality Issues

### Issue 1: Sample Rate Conversion Artifacts

**Problem:** The XVF3800 natively operates at 48kHz for optimal DSP performance, but the system requires 16kHz. The design doesn't specify where sample rate conversion (SRC) occurs.

**Analysis:**
- If XVF3800 outputs 48kHz and ESP32 downsamples → Potential aliasing
- If XVF3800 is configured for 16kHz output → Suboptimal DSP performance

**Recommendation:**
```
Option A (Recommended): XVF3800 at 48kHz → ESP32 SRC with anti-aliasing filter
Option B: XVF3800 at 16kHz native (verify DSP quality at this rate)
```

If using SRC on ESP32:
```c
// Anti-aliasing filter coefficients (Butterworth lowpass, 7kHz cutoff)
// Must be applied BEFORE decimation
static const float aa_filter_coeffs[] = { ... };

void downsample_48k_to_16k(const int16_t* input, int16_t* output, size_t input_samples) {
    // 1. Apply anti-aliasing lowpass filter
    apply_lowpass_filter(input, filtered, input_samples, aa_filter_coeffs);
    // 2. Decimate by factor of 3
    for (size_t i = 0; i < input_samples / 3; i++) {
        output[i] = filtered[i * 3];
    }
}
```

---

### Issue 2: Digital Gain May Cause Clipping

**Problem:** The ReSpeaker Lite applies a 16-bit right shift for digital gain, followed by a soft limiter. This approach can cause non-linear distortion affecting:
- Jitter measurements (pitch perturbation)
- Shimmer measurements (amplitude perturbation)
- HNR (Harmonics-to-Noise Ratio)

**Current implementation:**
```c
sample = sample >> BIT_SHIFT;  // Amplify
if (sample > 32767) sample = 32767;  // Hard clip
```

**Recommended implementation:**
```c
// Soft knee compressor instead of hard limiter
float soft_clip(float sample, float threshold, float knee) {
    float abs_sample = fabsf(sample);
    if (abs_sample < threshold - knee/2) {
        return sample;  // Linear region
    } else if (abs_sample < threshold + knee/2) {
        // Soft knee compression
        float x = abs_sample - threshold + knee/2;
        return copysignf(threshold - knee/2 + x - (x*x)/(2*knee), sample);
    } else {
        // Compression region (not hard clip)
        return copysignf(threshold + (abs_sample - threshold) * 0.1f, sample);
    }
}
```

---

### Issue 3: VAD Energy Threshold is Microphone-Dependent

**Problem:** A fixed VAD threshold of 150 assumes consistent microphone sensitivity. The two boards have different microphone arrays and DSP processing, resulting in different output levels.

**Evidence:**
- ReSpeaker Lite: 2-mic with basic NS → Higher noise floor
- XVF3800: 4-mic with DNN-NS → Lower noise floor, different gain structure

**Recommendation:** Implement adaptive threshold with per-board calibration:
```c
typedef struct {
    float noise_floor_estimate;     // Exponential moving average of silence energy
    float speech_floor_estimate;    // Minimum observed speech energy
    float threshold_multiplier;     // Typically 3-5x noise floor
    uint32_t calibration_frames;    // Frames used for calibration
} adaptive_vad_t;

#ifdef CONFIG_BOARD_RESPEAKER_LITE
    #define VAD_INITIAL_THRESHOLD       200.0f
    #define VAD_THRESHOLD_MULTIPLIER    4.0f
#elif CONFIG_BOARD_RESPEAKER_XVF3800
    #define VAD_INITIAL_THRESHOLD       80.0f   // Lower due to better NS
    #define VAD_THRESHOLD_MULTIPLIER    5.0f
#endif
```

---

### Issue 4: XVF3800 AGC May Affect Acoustic Features

**Problem:** The XVF3800's 60dB AGC is designed for voice assistants (consistent loudness) but may interfere with depression detection features that rely on amplitude dynamics:
- RMS energy variability (flattened by AGC)
- Dynamic range (compressed)
- Shimmer (amplitude perturbation masked)

**Analysis of affected features:**
| Feature | Impact of AGC | Severity |
|---------|---------------|----------|
| rms_energy_mean | Normalized, less variance | HIGH |
| rms_energy_std | Reduced by compression | HIGH |
| shimmer | Perturbations masked | MEDIUM |
| dynamic_range | Compressed | MEDIUM |
| spectral_flatness | Minimal impact | LOW |
| f0_* (pitch) | No impact | NONE |

**Recommendation:** Configure XVF3800 AGC conservatively or disable:
```c
// Option 1: Disable AGC entirely (if supported by firmware)
xvf3800_set_agc_enabled(false);

// Option 2: Set high target level to minimize compression
xvf3800_set_agc_target_db(-6);  // High headroom

// Option 3: Use linear mode if available
xvf3800_set_agc_mode(AGC_MODE_LINEAR);
```

**Research Note:** Run comparative analysis with AGC on/off to determine impact on classification accuracy.

---

### Issue 5: Beamforming May Reduce Speaker Separation Cues

**Problem:** The XVF3800's adaptive beamforming tracks the primary speaker, which is excellent for voice assistants but may:
- Suppress secondary speakers (affects "social_interaction" scene detection)
- Lose spatial information useful for multi-occupant analysis

**Recommendation:** For depression detection use case:
```c
// Consider fixed-beam mode pointing at common speaking position
// rather than adaptive tracking
#define BEAMFORMER_MODE_FIXED    0
#define BEAMFORMER_MODE_ADAPTIVE 1

#ifdef DEPRESSION_DETECTION_MODE
    xvf3800_set_beam_mode(BEAMFORMER_MODE_FIXED);
    xvf3800_set_fixed_beam(0);  // Forward-facing
#else
    xvf3800_set_beam_mode(BEAMFORMER_MODE_ADAPTIVE);
#endif
```

---

## Audio Quality Recommendations

### Recommendation 1: Add Pre-Emphasis Filter

Speech analysis typically benefits from pre-emphasis to boost high frequencies attenuated by the vocal tract:
```c
// Pre-emphasis filter: y[n] = x[n] - α * x[n-1]
#define PRE_EMPHASIS_ALPHA 0.97f

void apply_pre_emphasis(int16_t* samples, size_t count) {
    static float prev_sample = 0.0f;
    for (size_t i = 0; i < count; i++) {
        float current = (float)samples[i];
        float emphasized = current - PRE_EMPHASIS_ALPHA * prev_sample;
        samples[i] = (int16_t)emphasized;
        prev_sample = current;
    }
}
```

**Note:** Verify this doesn't interfere with server-side feature extraction that may apply its own pre-emphasis.

### Recommendation 2: DC Offset Removal

Some microphones introduce DC offset that can affect RMS and zero-crossing calculations:
```c
// High-pass filter to remove DC (cutoff ~20Hz)
typedef struct {
    float prev_input;
    float prev_output;
    float alpha;  // ~0.995 for 20Hz at 16kHz
} dc_blocker_t;

float dc_blocker_process(dc_blocker_t* db, float sample) {
    float output = sample - db->prev_input + db->alpha * db->prev_output;
    db->prev_input = sample;
    db->prev_output = output;
    return output;
}
```

### Recommendation 3: Silence Padding for Chunk Boundaries

Abrupt chunk boundaries can cause artifacts in spectral analysis. Add fade-in/fade-out:
```c
#define FADE_SAMPLES 160  // 10ms at 16kHz

void apply_fade(int16_t* samples, size_t count, bool fade_in) {
    for (size_t i = 0; i < FADE_SAMPLES && i < count; i++) {
        float gain = fade_in ? (float)i / FADE_SAMPLES : (float)(FADE_SAMPLES - i) / FADE_SAMPLES;
        size_t idx = fade_in ? i : count - FADE_SAMPLES + i;
        samples[idx] = (int16_t)(samples[idx] * gain);
    }
}
```

### Recommendation 4: Audio Quality Validation

Add runtime audio quality checks before transmission:
```c
typedef enum {
    AUDIO_QUALITY_GOOD,
    AUDIO_QUALITY_LOW_LEVEL,      // RMS below threshold
    AUDIO_QUALITY_CLIPPING,       // >1% samples clipped
    AUDIO_QUALITY_DC_OFFSET,      // Mean > threshold
    AUDIO_QUALITY_SILENCE,        // Extended silence detected
    AUDIO_QUALITY_NOISE_ONLY      // High ZCR, low energy
} audio_quality_status_t;

audio_quality_status_t validate_audio_chunk(const int16_t* samples, size_t count) {
    audio_quality_metrics_t metrics;
    calculate_quality_metrics(samples, count, &metrics);

    if (metrics.clipping_count > count * 0.01) return AUDIO_QUALITY_CLIPPING;
    if (metrics.rms < 50.0f) return AUDIO_QUALITY_LOW_LEVEL;
    if (fabsf(metrics.dc_offset) > 500) return AUDIO_QUALITY_DC_OFFSET;
    // ... additional checks
    return AUDIO_QUALITY_GOOD;
}
```

---

## XVF3800-Specific Audio Considerations

### Direction of Arrival (DoA) Data Value

The XVF3800's DoA detection could provide valuable metadata for depression research:
- Track subject's typical speaking positions
- Detect movement patterns (psychomotor indicators)
- Enhance speaker verification

**Recommendation:** Include DoA in audio metadata:
```c
typedef struct {
    int16_t azimuth_degrees;    // -180 to +180
    uint8_t confidence;         // 0-100%
    bool voice_detected;
} doa_metadata_t;

// Query DoA periodically and include in quality metrics
xvf3800_get_doa(&metadata.azimuth_degrees, &metadata.confidence);
```

### De-reverberation Impact

The XVF3800's de-reverberation is beneficial for:
- Improved formant extraction
- Cleaner HNR measurements
- Better fundamental frequency tracking

**Recommendation:** Enable de-reverberation for depression detection use case.

---

## Board-Specific Audio Configuration Summary

| Parameter | ReSpeaker Lite | XVF3800 | Rationale |
|-----------|----------------|---------|-----------|
| Sample Rate | 16kHz | 16kHz (or 48kHz + SRC) | Feature extraction standard |
| AGC | XU316 default | Disabled or conservative | Preserve amplitude dynamics |
| Noise Suppression | XU316 default | DNN-NS enabled | Clean speech for analysis |
| Beamforming | N/A | Fixed beam or adaptive | TBD based on research needs |
| De-reverb | N/A | Enabled | Cleaner formants |
| Pre-emphasis | ESP32 software | ESP32 software | Consistent processing |
| DC Blocking | ESP32 software | ESP32 software | Remove offset |
| VAD Threshold | 200 | 80 | Board-specific sensitivity |

---

## Required Actions Before Implementation

1. **[CRITICAL]** Determine SRC strategy for XVF3800 (48kHz vs 16kHz)
2. **[CRITICAL]** Implement soft-knee limiting instead of hard clipping
3. **[CRITICAL]** Calibrate per-board VAD thresholds
4. **[HIGH]** Evaluate AGC impact on amplitude-based features
5. **[HIGH]** Add DC offset removal
6. **[MEDIUM]** Consider pre-emphasis filter placement
7. **[MEDIUM]** Add audio quality validation
8. **[LOW]** Implement fade-in/fade-out for chunk boundaries

---

**Sound Engineer Sign-off:** Conditionally approved pending resolution of audio quality concerns, particularly AGC impact assessment and SRC strategy.

---

# ROUND 3: PRINCIPAL INVESTIGATOR REVIEW & IMPLEMENTATION DIRECTIVE

**Reviewer:** Principal Investigator
**Date:** 2026-01-11
**Review Focus:** Research alignment, scientific validity, project goals, resource allocation

---

## Executive Decision

After reviewing the initial design (Round 1) and peer reviews from the Firmware Developer (Round 2a) and Sound Engineer (Round 2b), I am providing final guidance to ensure the firmware development aligns with the IHearYou project's research objectives and clinical validation requirements.

**Decision:** ✅ **APPROVED FOR IMPLEMENTATION** with mandatory revisions and phased delivery.

---

## Strategic Alignment with Research Goals

### Primary Research Objectives Mapping

| Research Goal | Firmware Requirement | Implementation Priority |
|---------------|---------------------|------------------------|
| **DSM-5 Acoustic Biomarker Detection** | Preserve amplitude dynamics (RMS, shimmer), pitch (F0, jitter), and spectral features | P0 - Must have |
| **Privacy-Preserving Edge Processing** | VAD-gated transmission, no raw audio storage on device | P0 - Must have |
| **Multi-Occupant Household Support** | Consistent audio format for speaker verification (D-vectors) | P0 - Must have |
| **Explainable AI (White-Box)** | High-quality audio for reliable feature extraction | P0 - Must have |
| **Real-Time Monitoring** | Low-latency streaming, 5-second chunk delivery | P1 - Should have |
| **Far-Field Capture** | XVF3800 beamforming for naturalistic home environments | P1 - Should have |
| **Scalable Deployment** | OTA updates, multi-board management, telemetry | P2 - Nice to have |

### Critical Scientific Requirements

Based on our acoustic feature extraction pipeline and DSM-5 indicator mapping, the following audio characteristics **must be preserved**:

1. **Amplitude Dynamics (for energy-based indicators)**
   - RMS energy variability → Fatigue, psychomotor retardation
   - Dynamic range → Loss of interest, depressed mood
   - Shimmer → Voice quality degradation

2. **Pitch Dynamics (for prosodic indicators)**
   - F0 mean, std, range → Depressed mood, emotional blunting
   - Jitter → Voice tremor, anxiety markers
   - F0 entropy → Monotonicity (depression indicator)

3. **Temporal Dynamics (for cognitive/behavioral indicators)**
   - Speech velocity → Psychomotor retardation/agitation
   - Pause patterns → Cognitive slowing, concentration difficulties
   - Silence ratio → Anhedonia, social withdrawal

4. **Spectral Characteristics (for voice quality)**
   - HNR → Breathiness, vocal cord tension
   - Formants → Articulatory precision
   - Spectral flatness → Voice quality

---

## PI Directives to Reviewers' Concerns

### Addressing Firmware Developer Concerns

| Issue | PI Directive |
|-------|-------------|
| **ESP-IDF 5.x API** | Mandatory. Use new I2S channel API. Document migration from Arduino sketch. |
| **PSRAM allocation** | Mandatory. Audio quality cannot be compromised by memory constraints. Allocate 512KB for ring buffer. |
| **Watchdog** | Mandatory. Field deployments require automatic recovery. |
| **Task priority** | Accept recommendation. Implement watermark-based flow control. |
| **Telemetry** | Implement in Phase 3. Include MQTT topic for firmware health monitoring. |
| **Boot optimization** | Nice-to-have. Research validity takes priority over boot speed. |

### Addressing Sound Engineer Concerns

| Issue | PI Directive |
|-------|-------------|
| **Sample Rate Conversion** | **Decision: XVF3800 should output 16kHz natively.** The DSP algorithms (beamforming, de-reverb) operate effectively at 16kHz per XMOS documentation. Avoid SRC complexity. Validate DSP quality in testing phase. |
| **Hard clipping** | **Mandatory fix.** Implement soft-knee compression. Clipping artifacts directly impact jitter/shimmer measurements which are critical for depression detection. |
| **VAD threshold** | **Mandatory per-board calibration.** Create calibration procedure in Phase 1. Store thresholds in NVS. |
| **AGC impact** | **CRITICAL RESEARCH QUESTION.** Conduct A/B study before production deployment. For initial development: **disable AGC on XVF3800** to preserve amplitude dynamics. XU316 AGC on ReSpeaker Lite is acceptable as baseline. |
| **Beamforming mode** | Use **adaptive beamforming** initially. The 3-beam architecture may actually help with speaker verification by tracking the target speaker. Evaluate impact on "social_interaction" scene detection in Phase 2. |
| **DoA metadata** | **Include in implementation.** DoA data offers valuable research insights for psychomotor indicators (movement patterns). Add to MQTT payload. |
| **Pre-emphasis** | **Do NOT apply on firmware.** Our server-side feature extraction (openSMILE eGeMAPSv02) applies its own pre-emphasis. Double pre-emphasis would corrupt features. |
| **DC blocking** | Implement as recommended. DC offset affects RMS accuracy. |

---

## Revised Feature Priorities

Based on the peer reviews and research alignment, I am revising the implementation priorities:

### Phase 1: Foundation (Weeks 1-2) - MUST COMPLETE

**Goal:** Achieve feature parity with current Arduino firmware on ReSpeaker Lite using ESP-IDF.

| Task ID | Task | Owner | Acceptance Criteria |
|---------|------|-------|---------------------|
| F1.1 | ESP-IDF project scaffolding | FW Dev | Builds for ESP32-S3, menuconfig works |
| F1.2 | I2S capture (new API) for ReSpeaker Lite | FW Dev | 16kHz/16-bit mono capture verified |
| F1.3 | Soft-knee limiter | FW Dev | No hard clipping, verify with scope |
| F1.4 | DC offset removal | FW Dev | Mean of silent chunks < ±50 |
| F1.5 | PSRAM ring buffer (512KB) | FW Dev | No overflow in 60s network outage |
| F1.6 | Energy-based VAD with calibration | FW Dev | Configurable threshold via NVS |
| F1.7 | WiFi manager with reconnection | FW Dev | Automatic reconnect within 10s |
| F1.8 | TCP client with MAC handshake | FW Dev | Verified with respeaker_service.py |
| F1.9 | Watchdog integration | FW Dev | Auto-recovery from task hang |
| F1.10 | Integration testing | QA | Continuous streaming for 24 hours |

**Phase 1 Deliverable:** ReSpeaker Lite streaming to server with equivalent or better audio quality than Arduino firmware.

### Phase 2: XVF3800 Support (Weeks 3-4) - HIGH PRIORITY

**Goal:** Enable XVF3800 boards with advanced DSP features accessible.

| Task ID | Task | Owner | Acceptance Criteria |
|---------|------|-------|---------------------|
| F2.1 | XVF3800 I2C driver | FW Dev | Read version, set parameters |
| F2.2 | I2S capture for XVF3800 (16kHz native) | FW Dev | Verified audio quality |
| F2.3 | Disable AGC via I2C | FW Dev | Confirm amplitude dynamics preserved |
| F2.4 | Enable de-reverberation | FW Dev | Verify improved HNR |
| F2.5 | DoA query and metadata | FW Dev | Azimuth included in chunk metadata |
| F2.6 | Per-board VAD calibration | FW Dev | XVF3800 threshold stored separately |
| F2.7 | Beamforming configuration | FW Dev | Default adaptive, configurable via NVS |
| F2.8 | Unified build system | FW Dev | Single codebase, BOARD_TYPE selection |
| F2.9 | Audio quality comparison | QA | Compare Lite vs XVF3800 feature extraction |
| F2.10 | AGC A/B study | QA | Document impact on amplitude features |

**Phase 2 Deliverable:** XVF3800 streaming with DSP control, DoA metadata, and validated audio quality.

### Phase 3: Production Readiness (Weeks 5-6) - SHOULD COMPLETE

**Goal:** Prepare firmware for field deployment with monitoring and updates.

| Task ID | Task | Owner | Acceptance Criteria |
|---------|------|-------|---------------------|
| F3.1 | Firmware telemetry | FW Dev | MQTT topic with health metrics |
| F3.2 | OTA update mechanism | FW Dev | Remote firmware update verified |
| F3.3 | Error recovery state machine | FW Dev | Automatic recovery from all error states |
| F3.4 | Audio quality validation | FW Dev | Reject low-quality chunks with status |
| F3.5 | Power optimization | FW Dev | Baseline power consumption documented |
| F3.6 | Multi-board stress test | QA | 8 boards streaming simultaneously |
| F3.7 | Documentation | FW Dev | Build instructions, API reference |
| F3.8 | Calibration utility | FW Dev | CLI tool for board calibration |

**Phase 3 Deliverable:** Production-ready firmware with OTA, telemetry, and documentation.

---

## Implementation Constraints

### Non-Negotiable Requirements

1. **Audio Sample Rate:** 16kHz (required for openSMILE eGeMAPSv02)
2. **Audio Bit Depth:** 16-bit signed integer
3. **Audio Channel:** Mono (left channel from I2S)
4. **Chunk Duration:** 5 seconds
5. **Protocol:** TCP with MAC handshake (backward compatible with respeaker_service.py)
6. **VAD:** Must be edge-based to preserve privacy

### Acceptable Trade-offs

1. Boot time may be 5-10 seconds (research validity > speed)
2. Memory usage can be high (8MB PSRAM available)
3. Power consumption is secondary (devices are wall-powered)

### Unacceptable Compromises

1. ❌ Audio quality degradation (clipping, aliasing, distortion)
2. ❌ Data loss due to buffer overflow without logging
3. ❌ Silent failures without telemetry
4. ❌ Incompatibility with existing server infrastructure

---

## Server-Side Integration Requirements

The firmware must maintain compatibility with:

1. **respeaker_service.py** (Port 8010)
   - MAC handshake protocol unchanged
   - Raw int16 PCM stream format unchanged

2. **MQTT payload format** (via respeaker_service.py)
   - Add optional `doa_azimuth` field for XVF3800
   - Add `board_type` field ("lite" or "xvf3800")
   - Add `firmware_version` field

3. **MongoDB collections**
   - No schema changes required for Phase 1-2
   - Consider `firmware_telemetry` collection for Phase 3

---

## Quality Assurance Requirements

### Phase 1 QA Checklist

- [ ] 24-hour continuous streaming test
- [ ] Network disconnection/reconnection test (10 cycles)
- [ ] Audio quality verification (compare to Arduino baseline)
- [ ] Memory leak detection (heap monitoring over 24h)
- [ ] Feature extraction validation (run openSMILE on captured audio)

### Phase 2 QA Checklist

- [ ] XVF3800 vs ReSpeaker Lite audio quality comparison
- [ ] AGC impact study on 5 acoustic features (RMS, shimmer, dynamic_range, spectral_flatness, hnr_mean)
- [ ] Beamforming impact on speaker verification accuracy
- [ ] DoA accuracy verification (known speaker positions)
- [ ] Cross-board calibration consistency

### Phase 3 QA Checklist

- [ ] OTA update reliability (10 update cycles)
- [ ] 8-board simultaneous streaming stress test
- [ ] Telemetry data completeness verification
- [ ] Error recovery test suite (inject faults)
- [ ] Documentation review

---

## Research Validation Experiments

Before full deployment, conduct the following validation experiments:

### Experiment 1: Audio Quality Equivalence

**Hypothesis:** ESP-IDF firmware produces audio with equivalent acoustic feature extraction quality to Arduino firmware.

**Method:**
1. Capture 1 hour of speech with both firmwares (same board, same speaker)
2. Extract 25 acoustic features with openSMILE
3. Compare feature distributions (Mann-Whitney U test)
4. Accept if p > 0.05 for all features (no significant difference)

### Experiment 2: XVF3800 AGC Impact

**Hypothesis:** Disabling XVF3800 AGC preserves amplitude-based features critical for depression detection.

**Method:**
1. Capture 30 minutes with AGC enabled, 30 minutes disabled
2. Compare RMS variability, shimmer, dynamic_range
3. Document percentage change in each feature
4. Recommend AGC setting based on results

### Experiment 3: Board Type Normalization

**Hypothesis:** Feature distributions differ between ReSpeaker Lite and XVF3800, requiring board-type normalization.

**Method:**
1. Capture identical speech content with both board types
2. Compare 25 feature distributions
3. If significant differences exist, develop normalization coefficients
4. Update analysis layer to apply board-specific normalization

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| XVF3800 16kHz mode has poor DSP quality | Medium | High | Test early in Phase 2; fallback to 48kHz + SRC if needed |
| AGC cannot be disabled via I2C | Low | Medium | Accept XU316 as baseline; document feature impact |
| DoA not available via I2C | Medium | Low | DoA is enhancement, not critical path |
| I2S timing incompatibility | Low | High | Test with logic analyzer; consult XMOS support |
| Memory constraints | Low | Medium | Profile early; optimize if needed |

---

## Final Approval

I approve this design document with the following mandatory conditions:

1. **Phase 1 must achieve audio quality parity with Arduino firmware before proceeding to Phase 2**
2. **AGC must be disabled on XVF3800 until A/B study is complete**
3. **DoA metadata must be included in XVF3800 implementation**
4. **Pre-emphasis must NOT be applied on firmware (server-side only)**
5. **All critical issues from Round 2 reviews must be addressed**

---

## Implementation Pipeline Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FIRMWARE IMPLEMENTATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: Foundation (ReSpeaker Lite)                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ FW Dev Tasks                           │ QA Tasks                    │   │
│  │ ─────────────────────────────────────  │ ──────────────────────────  │   │
│  │ F1.1 Project scaffolding               │                             │   │
│  │ F1.2 I2S capture (ESP-IDF 5.x)         │                             │   │
│  │ F1.3 Soft-knee limiter                 │                             │   │
│  │ F1.4 DC offset removal                 │                             │   │
│  │ F1.5 PSRAM ring buffer                 │                             │   │
│  │ F1.6 VAD with calibration              │                             │   │
│  │ F1.7 WiFi manager                      │                             │   │
│  │ F1.8 TCP client                        │                             │   │
│  │ F1.9 Watchdog                          │ F1.10 Integration testing   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ GATE 1: Audio Quality Validation                                     │   │
│  │ - Feature extraction equivalence test                                │   │
│  │ - 24-hour stability test                                             │   │
│  │ - PI sign-off required                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  PHASE 2: XVF3800 Support                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ FW Dev Tasks                           │ QA Tasks                    │   │
│  │ ─────────────────────────────────────  │ ──────────────────────────  │   │
│  │ F2.1 XVF3800 I2C driver                │                             │   │
│  │ F2.2 I2S capture (16kHz native)        │                             │   │
│  │ F2.3 Disable AGC                       │                             │   │
│  │ F2.4 Enable de-reverb                  │                             │   │
│  │ F2.5 DoA metadata                      │ F2.9 Audio quality compare  │   │
│  │ F2.6 Per-board calibration             │ F2.10 AGC A/B study         │   │
│  │ F2.7 Beamforming config                │                             │   │
│  │ F2.8 Unified build                     │                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ GATE 2: XVF3800 Feature Validation                                   │   │
│  │ - AGC study complete                                                 │   │
│  │ - DoA accuracy verified                                              │   │
│  │ - Board normalization coefficients (if needed)                       │   │
│  │ - PI sign-off required                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  PHASE 3: Production Readiness                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ FW Dev Tasks                           │ QA Tasks                    │   │
│  │ ─────────────────────────────────────  │ ──────────────────────────  │   │
│  │ F3.1 Telemetry                         │ F3.6 Multi-board stress     │   │
│  │ F3.2 OTA updates                       │ F3.7 Documentation review   │   │
│  │ F3.3 Error recovery                    │                             │   │
│  │ F3.4 Audio quality validation          │                             │   │
│  │ F3.5 Power optimization                │                             │   │
│  │ F3.8 Calibration utility               │                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ GATE 3: Production Release                                           │   │
│  │ - 8-board stress test passed                                         │   │
│  │ - OTA reliability verified                                           │   │
│  │ - Documentation complete                                             │   │
│  │ - PI final sign-off                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│                      🚀 PRODUCTION DEPLOYMENT                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Document Revision History (Updated)

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-11 | Engineering Team | Initial design document |
| 1.1.0 | 2026-01-11 | Firmware Developer | Round 2a peer review |
| 1.2.0 | 2026-01-11 | Sound Engineer | Round 2b peer review |
| 1.3.0 | 2026-01-11 | Principal Investigator | Round 3 final review & implementation pipeline |

---

**Principal Investigator Sign-off:**

Approved for implementation. Begin Phase 1 immediately. Report progress at weekly sync.

**Signature:** _PI, IHearYou Research Team_
**Date:** 2026-01-11

---

## Appendix A: Quick Reference for Firmware Developer

### Must Do (Phase 1)
```
✅ Use ESP-IDF 5.x I2S channel API
✅ Allocate audio buffers in PSRAM
✅ Implement soft-knee limiter (no hard clipping)
✅ Add DC offset removal filter
✅ Per-board VAD threshold calibration
✅ Watchdog on all tasks
✅ Backward compatible with respeaker_service.py
```

### Must NOT Do
```
❌ Apply pre-emphasis filter (server-side only)
❌ Use hard clipping (corrupts shimmer/jitter)
❌ Skip watchdog (field deployment requires it)
❌ Change TCP protocol (must match server)
❌ Enable XVF3800 AGC without PI approval
```

### Key Configuration Values
```c
// Audio
#define SAMPLE_RATE             16000
#define BIT_DEPTH               16
#define CHUNK_DURATION_S        5
#define CHUNK_SAMPLES           80000
#define CHUNK_BYTES             160000

// Ring Buffer (PSRAM)
#define RING_BUFFER_SIZE        (512 * 1024)  // 512KB

// VAD
#define VAD_HANGOVER_MS         500
#define VAD_THRESHOLD_LITE      200     // Calibrate
#define VAD_THRESHOLD_XVF3800   80      // Calibrate

// Network
#define SERVER_PORT             8010
#define RECONNECT_DELAY_MS      1000
#define HANDSHAKE_TIMEOUT_MS    5000

// XVF3800
#define XVF3800_I2C_ADDR        0x2C
#define XVF3800_AGC_ENABLED     false   // Critical!
#define XVF3800_DEREVERB        true
```

---

## Appendix B: Quick Reference for QA Team

### Phase 1 Test Cases

| Test ID | Test Name | Pass Criteria |
|---------|-----------|---------------|
| T1.1 | Continuous streaming | 24 hours, no data loss |
| T1.2 | Network recovery | Reconnects within 10s, resumes streaming |
| T1.3 | Audio quality | openSMILE features within 5% of Arduino baseline |
| T1.4 | Memory stability | Heap stable over 24 hours |
| T1.5 | Watchdog recovery | Task hang → automatic restart within 30s |

### Phase 2 Test Cases

| Test ID | Test Name | Pass Criteria |
|---------|-----------|---------------|
| T2.1 | XVF3800 audio quality | Feature extraction successful |
| T2.2 | AGC impact | Document amplitude feature changes |
| T2.3 | DoA accuracy | ±15° accuracy at known positions |
| T2.4 | Board comparison | Document feature distribution differences |
| T2.5 | Calibration persistence | Thresholds survive power cycle |

### Phase 3 Test Cases

| Test ID | Test Name | Pass Criteria |
|---------|-----------|---------------|
| T3.1 | OTA reliability | 10 update cycles, all successful |
| T3.2 | Multi-board stress | 8 boards × 4 hours, no data loss |
| T3.3 | Telemetry completeness | All metrics present in MQTT |
| T3.4 | Error recovery | All injected faults recovered |

---

# ADDENDUM: RESEARCH QUESTIONS REQUIRING PI CLARIFICATION

**Submitted by:** Engineering Team
**Date:** 2026-01-11
**Purpose:** Request for research direction on backend processing challenges

---

## Context

The firmware design document addresses audio capture from multiple boards. However, once audio arrives at the backend, several **fundamental research questions** remain unresolved. These questions directly impact:
- System validity in real-world deployments
- Clinical reliability of depression indicators
- Scientific defensibility of our claims

We respectfully request the PI to clarify these open questions and assign research tasks to elucidate areas that require further investigation.

---

## Category 1: Multi-Occupant Household Differentiation

### Q1.1: Speaker Verification Accuracy in Naturalistic Settings

**Current Implementation:** D-vector embeddings with cosine similarity thresholds (HIGH: 0.70, LOW: 0.55)

**Open Questions:**
- What is the expected false acceptance rate (FAR) and false rejection rate (FRR) in home environments?
- How do we handle voice changes due to illness, emotional state, or fatigue (all relevant to depression)?
- Should thresholds be user-specific or universal?
- How many enrollment samples are sufficient for reliable speaker verification?

**Research Task Needed:**
> Conduct speaker verification accuracy study in multi-occupant households with varying acoustic conditions.

---

### Q1.2: Distinguishing Target User from Household Members

**Current Implementation:** Binary decision (target user vs. other)

**Open Questions:**
- What happens when target user speaks simultaneously with others (crosstalk)?
- Should we track multiple target users per household (e.g., couple where both have depression)?
- How do we handle voice similarity between family members (e.g., parent/child)?
- Should we maintain speaker profiles for all household members to improve differentiation?

**Research Task Needed:**
> Define household speaker modeling strategy and evaluate accuracy with 2-5 occupant scenarios.

---

### Q1.3: Background Noise Source Identification

**Current Implementation:** Basic scene classification (solo_activity, social_interaction, background_noise_tv)

**Open Questions:**
- How do we distinguish TV/radio speech from live human speech?
- What acoustic features reliably differentiate mechanical sounds (HVAC, appliances) from speech?
- Should we use content-based detection (music recognition, TV program fingerprinting)?
- How do we handle mixed scenes (user speaking while TV is on)?

**Proposed Acoustic Discriminators:**
| Source | ZCR | Spectral Centroid | Temporal Consistency | Spatial (DoA) |
|--------|-----|-------------------|---------------------|---------------|
| Live Speech | Variable | 1-4 kHz | Variable | Changes |
| TV Speech | Variable | 1-4 kHz | Consistent patterns | Fixed |
| Music | Low-Medium | Wide range | Highly structured | Fixed |
| HVAC | High | Low (< 500 Hz) | Very consistent | Fixed |

**Research Task Needed:**
> Develop multi-class audio source classifier and validate on home environment recordings.

---

## Category 2: Contextual Understanding

### Q2.1: Temporal Context Extraction

**Current Implementation:** Morning/evening/general time windows with EMA smoothing

**Open Questions:**
- What time granularity is clinically meaningful (hourly, part-of-day, daily)?
- How do we handle shift workers or irregular sleep patterns?
- Should context windows be personalized based on user's routine?
- How long should the "learning period" be before making clinical inferences?

**Research Task Needed:**
> Investigate optimal temporal aggregation strategies for depression biomarkers across diverse daily routines.

---

### Q2.2: Environmental Context

**Open Questions:**
- Does room acoustics (reverberant kitchen vs. carpeted bedroom) affect feature extraction?
- Should we normalize features by environment/board location?
- How do we incorporate multi-board spatial information (user moved from living room to bedroom)?
- Can environmental context (kitchen=social, bedroom=isolation) inform indicator weights?

**Proposed Context Taxonomy:**
```
Environmental Context:
├── Physical Location
│   ├── Private (bedroom, bathroom)
│   ├── Social (living room, kitchen)
│   └── Transition (hallway)
├── Activity Type (inferred)
│   ├── Solo activity
│   ├── Social interaction
│   ├── Media consumption
│   └── Silence/absence
├── Time of Day
│   ├── Morning (wake to noon)
│   ├── Afternoon (noon to 6pm)
│   ├── Evening (6pm to sleep)
│   └── Night (sleep hours)
└── Day Type
    ├── Weekday
    └── Weekend
```

**Research Task Needed:**
> Define context ontology and validate its predictive value for depression indicators.

---

### Q2.3: Social Context Interpretation

**Open Questions:**
- How do we interpret silence? (isolation vs. away from home vs. sleeping)
- What does "social interaction" quality look like? (positive engagement vs. conflict)
- Can we infer emotional valence of interactions without content analysis?
- How do we handle phone/video calls (one-sided audio)?

**Research Task Needed:**
> Develop social context classification beyond binary presence/absence of others.

---

## Category 3: Context-Weighted Indicator Scoring

### Q3.1: Should Context Influence Feature Weights?

**Current Implementation:** Static weights per feature per indicator (from `config.json`)

**Hypothesis:** The same acoustic feature may have different clinical significance depending on context.

**Examples:**
| Feature | Context | Interpretation | Weight Adjustment? |
|---------|---------|----------------|-------------------|
| Low RMS energy | Morning, solo | Possible fatigue | Higher weight |
| Low RMS energy | Evening, social | Normal quiet conversation | Lower weight |
| Monotonic F0 | Social interaction | Possible emotional blunting | Higher weight |
| Monotonic F0 | Reading aloud | Normal reading prosody | Lower weight |
| Long pauses | Morning | Cognitive slowing | Higher weight |
| Long pauses | Late night | Normal tiredness | Lower weight |

**Open Questions:**
- Should we implement context-dependent weight modifiers?
- How do we learn these modifiers (clinical data, literature, expert input)?
- Does this add too much complexity vs. predictive value?

**Research Task Needed:**
> Conduct literature review and expert consultation on context-feature interactions in depression assessment.

---

### Q3.2: Confidence Scoring by Context Quality

**Open Questions:**
- Should indicators derived from noisy/ambiguous audio have lower confidence?
- How do we propagate uncertainty through the analysis pipeline?
- Should we withhold indicator scores when context quality is poor?

**Proposed Confidence Factors:**
```
Indicator Confidence = Base Score × Context Quality Factors

Context Quality Factors:
├── Speaker Verification Confidence (0.5 - 1.0)
├── Audio Quality Score (0.0 - 1.0)
├── Scene Classification Confidence (0.5 - 1.0)
├── Sample Duration Sufficiency (0.0 - 1.0)
└── Temporal Coverage (0.0 - 1.0)

Example:
- High confidence: Verified speaker, clean audio, clear solo activity, 30+ min data
- Low confidence: Uncertain speaker, noisy, mixed scene, < 5 min data
```

**Research Task Needed:**
> Design uncertainty quantification framework for indicator scoring.

---

## Category 4: Validation and Clinical Defensibility

### Q4.1: Ground Truth Definition

**Open Questions:**
- What is our ground truth for depression state? (PHQ-9, clinical diagnosis, both?)
- How frequently should ground truth be collected? (daily, weekly, per episode?)
- How do we handle discordance between self-report and clinical assessment?
- Can we use DAIC-WOZ clinical interviews as validation reference?

**Research Task Needed:**
> Define validation protocol with clinician input and IRB considerations.

---

### Q4.2: Feature-to-Indicator Mapping Validation

**Current Implementation:** Literature-derived mappings from acoustic features to DSM-5 indicators

**Open Questions:**
- Have these mappings been validated in naturalistic (non-clinical) settings?
- Do mappings hold across demographics (age, gender, culture, language)?
- How do we handle individual variability (person A's "low energy" ≠ person B's)?
- Should mappings be personalized over time?

**Research Task Needed:**
> Validate feature-to-indicator mappings with DAIC-WOZ dataset and plan prospective validation study.

---

### Q4.3: Multi-Board Consistency

**Open Questions:**
- If the same person speaks near different boards, do we get consistent features?
- How do we handle feature drift between boards over time?
- Should we cross-calibrate boards using overlapping audio captures?

**Research Task Needed:**
> Conduct multi-board feature consistency study with controlled speech samples.

---

### Q4.4: Longitudinal Validity

**Open Questions:**
- How do we validate that changes in indicators reflect true clinical changes?
- What is the expected sensitivity to detect clinically meaningful change?
- How do we distinguish real changes from measurement noise?
- What is the minimum observation period for reliable assessment?

**Research Task Needed:**
> Design longitudinal validation study with repeated clinical assessments.

---

## Category 5: Ethical and Privacy Considerations

### Q5.1: Consent in Multi-Occupant Households

**Open Questions:**
- How do we handle audio from non-consenting household members?
- Should we actively suppress/delete non-target speaker audio?
- What disclosures are required for household members?

**Research Task Needed:**
> Consult with IRB/ethics board on multi-occupant consent requirements.

---

### Q5.2: Incidental Findings

**Open Questions:**
- What if the system detects indicators of suicidal ideation?
- Should there be automatic alerts to clinicians or emergency contacts?
- What is our liability and duty of care?

**Research Task Needed:**
> Develop incidental findings protocol with clinical and legal input.

---

## Summary: Research Tasks for Assignment

| Task ID | Research Question | Suggested Owner | Priority |
|---------|-------------------|-----------------|----------|
| R1.1 | Speaker verification accuracy study | ML Researcher | HIGH |
| R1.2 | Household speaker modeling strategy | ML Researcher | HIGH |
| R1.3 | Multi-class audio source classifier | Audio Researcher | MEDIUM |
| R2.1 | Temporal aggregation strategies | Data Scientist | MEDIUM |
| R2.2 | Context ontology validation | Clinical Researcher | MEDIUM |
| R2.3 | Social context classification | Audio Researcher | LOW |
| R3.1 | Context-feature interaction review | Clinical Researcher | MEDIUM |
| R3.2 | Uncertainty quantification framework | Data Scientist | MEDIUM |
| R4.1 | Validation protocol with clinicians | PI + Clinical | HIGH |
| R4.2 | Feature-to-indicator validation (DAIC-WOZ) | ML Researcher | HIGH |
| R4.3 | Multi-board consistency study | Audio Researcher | MEDIUM |
| R4.4 | Longitudinal validation design | PI + Clinical | HIGH |
| R5.1 | Multi-occupant consent requirements | PI + IRB | HIGH |
| R5.2 | Incidental findings protocol | PI + Clinical + Legal | HIGH |

---

## Request to Principal Investigator

We request the PI to:

1. **Clarify** which of these questions have existing answers from literature or prior work
2. **Prioritize** research tasks based on project timeline and resources
3. **Assign** researchers to each task with clear deliverables
4. **Define** acceptance criteria for each research question
5. **Identify** any additional questions we may have missed
6. **Determine** which questions are blocking for firmware deployment vs. can be addressed in parallel

**These questions do not block Phase 1 firmware development** (ReSpeaker Lite parity), but several are **critical for Phase 2 and production deployment**.

---

## PI Response Section

**Date of Response:** 2026-01-12
**Reviewer:** Principal Investigator, IHearYou Research Program

---

### Executive Summary

Thank you for this thorough enumeration of research challenges. These questions reflect the complexity of deploying acoustic biomarker systems in real-world settings—a challenge that distinguishes our work from controlled laboratory studies.

I have reviewed each category and provide below:
1. Clarifications on what we already know or have implemented
2. Strategic decisions that can be made now
3. Research tasks requiring investigation
4. Priority ranking aligned with deployment timeline

**Key Principle:** We are building a **screening and monitoring tool**, not a diagnostic device. This distinction is critical for setting appropriate validation thresholds and managing clinical expectations.

---

### Clarifications on Existing Answers

#### Category 1: Multi-Occupant Household Differentiation

**Q1.1 - Speaker Verification Accuracy:**

*What we know:*
- The current implementation uses Resemblyzer D-vectors, which achieve ~95% accuracy in controlled conditions but degrade to ~85% in noisy home environments (literature: Wan et al., 2018).
- Voice changes due to depression are a *feature*, not a bug—we want to detect these changes. However, acute illness (cold, flu) creates confounds.

*Decision:*
- **Thresholds should be user-calibrated during enrollment**, not universal. The current HIGH/LOW thresholds (0.70/0.55) are starting points.
- Implement a **"voice health" check** during enrollment to establish baseline under normal conditions.
- Add **re-enrollment prompts** if verification consistently fails (>3 days of low match rates).

**Q1.2 - Distinguishing Target User from Household Members:**

*What we know:*
- The current system is designed for **single target user per household**. This is intentional—clinical responsibility and consent are clearer.
- Crosstalk is handled by the scene resolver's "social_interaction" classification, which correctly excludes mixed audio from solo analysis.

*Decision:*
- **Do NOT expand to multiple target users** in Phase 1-2. This adds complexity without clear clinical benefit.
- Household member profiles are **out of scope**—privacy concerns outweigh benefits.
- For couples where both have depression, recommend **separate deployments** (different user accounts, can share hardware).

**Q1.3 - Background Noise Source Identification:**

*What we know:*
- The XVF3800's DoA detection is key here—TV/radio have **fixed DoA**, live speakers move.
- ZCR and spectral centroid are already computed in quality metrics.
- Current scene classification is rudimentary but functional.

*Decision:*
- **Enhance scene classifier in Phase 2** using DoA variance as primary discriminator.
- TV fingerprinting is **out of scope**—too complex, privacy concerns (recording content).
- Accept that some edge cases (user watching TV silently) will be misclassified; rely on temporal aggregation to smooth errors.

---

#### Category 2: Contextual Understanding

**Q2.1 - Temporal Context Extraction:**

*What we know:*
- Literature supports **part-of-day granularity** (morning/afternoon/evening) as clinically meaningful for depression (diurnal mood variation is a DSM-5 specifier).
- Our EMA smoothing with α=0.8667 (14-day window) is based on PHQ-9 standard recall period.

*Decision:*
- **Keep current temporal structure** (morning/evening/general) for Phase 1-2.
- Add **personalized time windows** in Phase 3 based on detected sleep patterns (first/last activity times).
- Shift workers: Flag in user profile; use relative time (hours since wake) instead of clock time.
- Learning period: **14 days minimum** before clinical inferences. This is already implemented.

**Q2.2 - Environmental Context:**

*What we know:*
- Room acoustics DO affect features, particularly HNR and formants. This is unavoidable without per-room calibration.
- Multi-board spatial tracking is possible but adds complexity.

*Decision:*
- **Implement per-environment baseline normalization** in Phase 2. Each board/environment gets its own baseline statistics.
- Spatial tracking (user movement between rooms) is **deferred to Phase 3**—interesting research but not critical for MVP.
- The proposed context taxonomy is approved. Implement as metadata fields.

**Q2.3 - Social Context Interpretation:**

*What we know:*
- Silence interpretation is the hardest problem. We cannot distinguish isolation from absence from sleep.
- Phone calls: We capture one side only; useful for speech features but not social context.

*Decision:*
- **Silence is NOT absence of depression signal**—reduced vocalization IS a signal (psychomotor retardation, social withdrawal).
- Track **silence patterns over time**, not instantaneous silence. Extended silence (>6 hours during waking hours) should flag for review.
- Emotional valence of interactions: **Out of scope** without content analysis, which we explicitly avoid for privacy.
- Phone calls: Classify as "solo_activity" (we only hear target user); note in documentation.

---

#### Category 3: Context-Weighted Indicator Scoring

**Q3.1 - Should Context Influence Feature Weights?**

*What we know:*
- This is an active research question with limited literature in naturalistic settings.
- Adding context-dependent weights risks overfitting without sufficient validation data.

*Decision:*
- **Phase 1-2: Static weights only.** This maintains interpretability and allows us to validate base model first.
- **Phase 3: Introduce context as MULTIPLICATIVE confidence modifier**, not weight modifier. Example: Morning solo activity → 1.2x confidence; late night any context → 0.8x confidence.
- This preserves the core model while acknowledging context affects reliability.
- **Research task assigned** (see below) to review literature and propose specific modifiers.

**Q3.2 - Confidence Scoring by Context Quality:**

*What we know:*
- The proposed confidence factors are reasonable and partially implemented (audio quality metrics exist).

*Decision:*
- **Implement composite confidence score** in Phase 2 analysis layer.
- Formula approved as proposed:
  ```
  Confidence = Speaker_Conf × Audio_Quality × Scene_Conf × Duration_Factor × Coverage_Factor
  ```
- **Withhold indicator display** (show as "insufficient data") when composite confidence < 0.5.
- This is critical for clinical credibility—we should not report indicators we cannot defend.

---

#### Category 4: Validation and Clinical Defensibility

**Q4.1 - Ground Truth Definition:**

*What we know:*
- PHQ-9 is self-report, completed weekly in our system. It is NOT ground truth—it is one signal.
- Clinical diagnosis requires structured interview (SCID, MINI) by trained clinician.
- DAIC-WOZ provides PHQ-8 (not PHQ-9) scores with clinical interviews.

*Decision:*
- **Primary validation metric:** Correlation with PHQ-9 change scores (within-subject tracking).
- **Secondary validation:** Classification accuracy against DAIC-WOZ PHQ-8 thresholds (PHQ ≥ 10 = moderate depression).
- **We are NOT claiming diagnostic accuracy.** We claim:
  1. Acoustic features correlate with self-reported depression severity
  2. Changes in features track changes in symptoms over time
  3. System can flag individuals for clinical follow-up
- This framing is defensible and avoids FDA device classification issues.

**Q4.2 - Feature-to-Indicator Mapping Validation:**

*What we know:*
- Mappings are derived from peer-reviewed literature (Cummins et al., 2015; Low et al., 2020; Scherer et al., 2013).
- Most studies are on clinical interviews, not naturalistic speech—this is a known gap.

*Decision:*
- **Immediate task:** Validate mappings on DAIC-WOZ (we have pending access request).
- **Accept that individual variability exists.** Address via personalized baseline (Z-score normalization is already per-user).
- Demographic factors: **Do not adjust weights by demographics** in Phase 1-2. Document any observed differences for future research.
- **Prospective validation study** is required before any clinical deployment. This is Phase 4 (post-production).

**Q4.3 - Multi-Board Consistency:**

*What we know:*
- Feature drift between boards is expected due to microphone aging, environmental changes.
- Cross-calibration is possible but operationally complex.

*Decision:*
- **Include board_id in all metrics** (already implemented).
- **Analyze for board effects** in Phase 2 QA—if significant, add board-type normalization.
- Cross-calibration: **Deferred.** Too complex for Phase 1-2. Recommend instead: periodic re-enrollment to update baseline.

**Q4.4 - Longitudinal Validity:**

*What we know:*
- Minimum observation period for depression screening is typically 2 weeks (PHQ-9 recall period).
- Clinically meaningful change on PHQ-9 is typically ≥5 points.

*Decision:*
- **Minimum observation period: 14 days** (already implemented as learning period).
- **Sensitivity target:** Detect PHQ-9 change ≥5 points with sensitivity >0.70, specificity >0.60.
- These are realistic targets for a screening tool. We are NOT targeting diagnostic sensitivity.
- **Longitudinal validation study** (R4.4) is HIGH priority and must be completed before production deployment.

---

#### Category 5: Ethical and Privacy Considerations

**Q5.1 - Consent in Multi-Occupant Households:**

*What we know:*
- This is a legal and IRB matter, not purely technical.
- Many ambient sensing studies use "household consent" where primary participant informs household members.

*Decision:*
- **Require explicit disclosure** to all household members during setup. Add consent acknowledgment screen.
- **Do NOT store or analyze non-target speaker audio** beyond scene classification. D-vectors are computed but discarded if not target user.
- Technical implementation: Non-target audio is used only for scene context; no features are extracted or stored.
- **Consult IRB** before any deployment outside research setting. This is blocking for production.

**Q5.2 - Incidental Findings:**

*What we know:*
- DSM-5 Indicator 9 (thoughts of death) is in our model but flagged as requiring "content analysis or self-report."
- We cannot detect suicidal ideation from acoustic features alone.

*Decision:*
- **Remove automated alerts for suicidal ideation.** We are not equipped to handle this clinically.
- **PHQ-9 Item 9** ("thoughts that you would be better off dead") is captured in self-report. This triggers existing clinical protocols.
- If user endorses Item 9: Display crisis resources (988 Suicide & Crisis Lifeline), recommend contacting provider.
- **Acoustic system should NOT independently flag suicide risk.** This is beyond our validated capability.
- Document this limitation clearly in all user-facing materials.

---

### Priority Ranking of Research Tasks

Based on deployment timeline and blocking dependencies:

| Priority | Task ID | Rationale |
|----------|---------|-----------|
| **CRITICAL** | R4.1 | Validation protocol is blocking for any clinical claims |
| **CRITICAL** | R5.1 | IRB/consent is blocking for production deployment |
| **CRITICAL** | R5.2 | Incidental findings protocol is blocking for user safety |
| **HIGH** | R4.2 | DAIC-WOZ validation required for credibility |
| **HIGH** | R1.1 | Speaker verification accuracy affects all downstream analysis |
| **HIGH** | R4.4 | Longitudinal validity is core scientific claim |
| **MEDIUM** | R1.3 | Scene classifier improvements for Phase 2 |
| **MEDIUM** | R3.2 | Confidence framework needed for clinical display |
| **MEDIUM** | R4.3 | Multi-board consistency for XVF3800 deployment |
| **MEDIUM** | R2.2 | Context ontology improves interpretability |
| **LOW** | R1.2 | Household modeling deferred (single-user focus) |
| **LOW** | R2.1 | Temporal aggregation working adequately |
| **LOW** | R2.3 | Social context beyond current implementation |
| **LOW** | R3.1 | Context-weighted scoring deferred to Phase 3 |

---

### Research Assignments

| Task ID | Title | Assigned To | Start | Deadline | Deliverable |
|---------|-------|-------------|-------|----------|-------------|
| R4.1 | Validation protocol design | PI + Clinical Advisor | Immediate | Week 2 | Protocol document, IRB submission draft |
| R5.1 | Multi-occupant consent | PI + Legal Counsel | Immediate | Week 2 | Consent forms, disclosure requirements |
| R5.2 | Incidental findings protocol | PI + Clinical Advisor | Immediate | Week 2 | Safety protocol document |
| R4.2 | DAIC-WOZ validation | ML Researcher | Week 2 | Week 6 | Validation report with accuracy metrics |
| R1.1 | Speaker verification study | ML Researcher | Week 2 | Week 4 | FAR/FRR analysis, threshold recommendations |
| R4.4 | Longitudinal validation design | PI + Biostatistician | Week 3 | Week 6 | Study protocol, power analysis, IRB application |
| R1.3 | Scene classifier enhancement | Audio Researcher | Week 3 | Week 5 | Improved classifier, DoA integration |
| R3.2 | Confidence scoring framework | Data Scientist | Week 3 | Week 5 | Implementation spec, threshold recommendations |
| R4.3 | Multi-board consistency | Audio Researcher | Week 4 | Week 6 | Consistency analysis, normalization coefficients |
| R2.2 | Context ontology | Clinical Researcher | Week 4 | Week 6 | Ontology spec, integration recommendations |

**Note:** Tasks R1.2, R2.1, R2.3, R3.1 are **deferred** to Phase 3 or later. They are valuable research directions but not blocking for MVP deployment.

---

### Additional Questions Identified by PI

#### Q6.1: Medication and Treatment Effects

**Question:** How do we account for patients starting/stopping antidepressants, which affect voice characteristics?

**Decision:** Add optional "treatment status" field in user profile. Flag significant changes for clinical interpretation. This is metadata, not algorithmic adjustment.

#### Q6.2: Comorbidity Handling

**Question:** Depression often co-occurs with anxiety, PTSD, substance use. Do our acoustic markers discriminate?

**Decision:** We do NOT claim to discriminate depression from comorbidities. Our indicators map to DSM-5 MDD criteria specifically. Comorbid conditions may affect scores—this is documented as limitation.

#### Q6.3: Cultural and Linguistic Validity

**Question:** Are acoustic depression markers valid across languages and cultures?

**Decision:** Phase 1-2 limited to English speakers. Non-English validation is Phase 4 research. Document this limitation.

#### Q6.4: Age-Related Voice Changes

**Question:** Elderly voices differ from younger adults. Do our models account for this?

**Decision:** Per-user baseline normalization partially addresses this. Age is captured in user profile. Document as potential confound requiring future research.

---

### Decisions Made (Summary)

| Decision | Rationale | Effective |
|----------|-----------|-----------|
| Single target user per household | Simplicity, consent clarity | Immediate |
| 14-day minimum learning period | PHQ-9 recall period standard | Already implemented |
| Static weights in Phase 1-2 | Validation before complexity | Immediate |
| Context as confidence modifier, not weight modifier | Interpretability | Phase 3 |
| Withhold indicators when confidence < 0.5 | Clinical credibility | Phase 2 |
| PHQ-9 correlation as primary validation metric | Realistic, defensible | Immediate |
| No automated suicide risk alerts | Beyond validated capability | Immediate |
| Non-target audio discarded after scene classification | Privacy protection | Verify implementation |
| Board-type normalization if needed | Based on Phase 2 QA findings | Conditional |
| English-only in Phase 1-2 | Validation scope | Document limitation |

---

### Blocking Dependencies for Production

The following must be completed before production deployment:

```
BLOCKING FOR PRODUCTION DEPLOYMENT
══════════════════════════════════

1. IRB Approval (R5.1)
   └── Consent forms approved
   └── Household disclosure requirements defined

2. Safety Protocol (R5.2)
   └── Incidental findings procedure documented
   └── Crisis resource integration verified

3. Validation Evidence (R4.2, R4.4)
   └── DAIC-WOZ validation report
   └── Longitudinal validation protocol approved

4. Confidence Framework (R3.2)
   └── Composite confidence score implemented
   └── Indicator withholding logic verified

5. Speaker Verification QA (R1.1)
   └── FAR/FRR documented
   └── Threshold recommendations implemented
```

**Timeline Implication:** Production deployment is **no earlier than Week 8**, contingent on completing blocking items.

---

### Next Steps

1. **Immediate (This Week):**
   - PI to draft validation protocol (R4.1)
   - PI to engage legal counsel on consent (R5.1)
   - PI to draft safety protocol (R5.2)
   - Firmware team continues Phase 1 (not blocked)

2. **Week 2:**
   - ML Researcher begins DAIC-WOZ validation prep
   - ML Researcher begins speaker verification study design
   - Submit IRB pre-application

3. **Week 3:**
   - Audio Researcher begins scene classifier work
   - Data Scientist begins confidence framework design
   - Phase 1 firmware expected complete

4. **Week 4-6:**
   - Research tasks execute in parallel with Phase 2 firmware
   - Weekly sync on research progress
   - Phase 2 firmware expected complete

5. **Week 6-8:**
   - Research results integrated
   - Validation reports completed
   - Production readiness assessment

---

### Closing Remarks

The engineering team has done excellent work identifying these challenges. This document will serve as our research roadmap for the next 8 weeks.

Key message to the team: **We are building a screening and monitoring tool, not a diagnostic device.** This framing guides our validation requirements and helps us ship something useful while maintaining scientific integrity.

The firmware development is **not blocked** by these research questions. Phase 1 (ReSpeaker Lite) and Phase 2 (XVF3800) can proceed in parallel with research activities. Production deployment is blocked pending completion of the items listed above.

I am available for weekly sync meetings to review progress on research tasks.

---

**Principal Investigator Sign-off:**

Questions addressed. Research tasks assigned. Development authorized to proceed.

**Signature:** _PI, IHearYou Research Program_
**Date:** 2026-01-12

---

**END OF DOCUMENT**
