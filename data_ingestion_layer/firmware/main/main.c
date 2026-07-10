/**
 * @file main.c
 * @brief IHearYou Firmware - Main Application Entry Point
 *
 * Unified firmware for ReSpeaker Lite and XVF3800 boards.
 * Captures audio, applies VAD, and streams to respeaker_service.py
 *
 * @copyright IHearYou Research Project
 */

#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "nvs_flash.h"
#include "esp_heap_caps.h"

#include "config/board_config.h"
#include "config/audio_config.h"
#include "hal/hal_audio.h"
#include "audio/audio_buffer.h"
#include "audio/vad.h"
#include "audio/audio_quality.h"
#include "network/wifi_manager.h"
#include "network/tcp_client.h"
#include "system/watchdog.h"

#if BOARD_TYPE_XVF3800
#include "drivers/xvf3800/xvf3800.h"
#endif

#if CONFIG_TRANSPORT_MQTT_OFFLOAD
#include "app/offload_app.h"
#include "transport/mqtt_sender.h"   // telemetry reports the sender's counters
// Plug-and-play runtime state (provisioning, capabilities, live assignment).
static app_ctx_t s_app_ctx;
#endif

static const char *TAG = "IHEARYOU";

// =============================================================================
// Global State
// =============================================================================

static EventGroupHandle_t s_app_event_group;

// Event bits
#define WIFI_CONNECTED_BIT      BIT0
#define TCP_CONNECTED_BIT       BIT1
#define AUDIO_STREAMING_BIT     BIT2
#define ERROR_BIT               BIT3

// =============================================================================
// Task Handles
// =============================================================================

static TaskHandle_t s_i2s_capture_task = NULL;
static TaskHandle_t s_vad_task = NULL;
#if !CONFIG_TRANSPORT_MQTT_OFFLOAD
static TaskHandle_t s_tcp_sender_task = NULL;
#endif
#if BOARD_TYPE_XVF3800
static TaskHandle_t s_dsp_control_task = NULL;
#endif

// =============================================================================
// Firmware Telemetry
// =============================================================================

typedef struct {
    uint32_t uptime_seconds;
    uint32_t audio_chunks_captured;
    uint32_t audio_chunks_sent;
    uint32_t buffer_overflows;
    uint32_t tcp_reconnections;
    float avg_audio_rms;
    int8_t wifi_rssi;
    uint32_t free_heap;
    uint32_t free_psram;
} firmware_telemetry_t;

static firmware_telemetry_t s_telemetry = {0};

// =============================================================================
// Audio Pipeline State
// =============================================================================

typedef enum {
    AUDIO_STATE_INIT,
    AUDIO_STATE_CONFIGURING,
    AUDIO_STATE_RUNNING,
    AUDIO_STATE_ERROR_I2S,
    AUDIO_STATE_ERROR_BUFFER,
    AUDIO_STATE_RECOVERING,
    AUDIO_STATE_FATAL
} audio_state_t;

static audio_state_t s_audio_state = AUDIO_STATE_INIT;

// =============================================================================
// Forward Declarations
// =============================================================================

static void i2s_capture_task(void *param);
static void vad_processor_task(void *param);
static void tcp_sender_task(void *param);
#if BOARD_TYPE_XVF3800
static void dsp_control_task(void *param);
#endif
static void telemetry_task(void *param);

// =============================================================================
// Initialization
// =============================================================================

static esp_err_t init_nvs(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    return ret;
}

static void print_system_info(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "IHearYou Firmware v%s", FIRMWARE_VERSION_STRING);
    ESP_LOGI(TAG, "Board: %s", BOARD_NAME);
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());
    ESP_LOGI(TAG, "Free PSRAM: %lu bytes", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    ESP_LOGI(TAG, "Audio: %d Hz, %d-bit, %d ch", AUDIO_SAMPLE_RATE, AUDIO_BIT_DEPTH, AUDIO_CHANNELS);
    ESP_LOGI(TAG, "Chunk: %d sec (%d samples, %d bytes)",
             AUDIO_CHUNK_DURATION_S, AUDIO_CHUNK_SAMPLES, AUDIO_CHUNK_BYTES);
    ESP_LOGI(TAG, "Ring buffer: %d KB", CONFIG_RING_BUFFER_SIZE_KB);
    ESP_LOGI(TAG, "VAD threshold: %.1f, hangover: %d ms", VAD_THRESHOLD, VAD_HANGOVER_MS);
#if BOARD_TYPE_XVF3800
    ESP_LOGI(TAG, "XVF3800 AGC: %s", XVF3800_AGC_ENABLED ? "enabled" : "disabled");
    ESP_LOGI(TAG, "XVF3800 De-reverb: %s", XVF3800_DEREVERB_ENABLED ? "enabled" : "disabled");
    ESP_LOGI(TAG, "XVF3800 DoA: %s", XVF3800_INCLUDE_DOA ? "included" : "excluded");
#endif
    ESP_LOGI(TAG, "========================================");
}

// =============================================================================
// Main Application
// =============================================================================

void app_main(void)
{
    ESP_LOGI(TAG, "Starting IHearYou firmware...");

    // Initialize NVS
    ESP_ERROR_CHECK(init_nvs());

    // Initialize watchdog
    ESP_LOGI(TAG, "Initializing watchdog...");
    esp_err_t wdt_ret = watchdog_init();
    if (wdt_ret != ESP_OK) {
        ESP_LOGW(TAG, "Watchdog init failed: %s (continuing anyway)", esp_err_to_name(wdt_ret));
    }

    // Print system information
    print_system_info();

    // Create event group
    s_app_event_group = xEventGroupCreate();
    if (s_app_event_group == NULL) {
        ESP_LOGE(TAG, "Failed to create event group");
        return;
    }

    // Initialize audio buffer (PSRAM)
    ESP_LOGI(TAG, "Initializing audio buffer...");
    esp_err_t ret = audio_buffer_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize audio buffer: %s", esp_err_to_name(ret));
        s_audio_state = AUDIO_STATE_FATAL;
        return;
    }

    // Initialize audio HAL
    ESP_LOGI(TAG, "Initializing audio HAL...");
    ret = hal_audio_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize audio HAL: %s", esp_err_to_name(ret));
        s_audio_state = AUDIO_STATE_FATAL;
        return;
    }

    // Initialize VAD
    ESP_LOGI(TAG, "Initializing VAD...");
    vad_config_t vad_config = VAD_CONFIG_DEFAULT;
    ret = vad_init(&vad_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize VAD: %s", esp_err_to_name(ret));
        s_audio_state = AUDIO_STATE_FATAL;
        return;
    }

#if BOARD_TYPE_XVF3800
    // Initialize XVF3800 DSP control
    ESP_LOGI(TAG, "Initializing XVF3800 DSP...");
    ret = xvf3800_init(XVF3800_I2C_PORT);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "XVF3800 control unavailable - using default DSP settings");
        // Continue without DSP control - audio still works via I2S
    } else {
        // Configure DSP settings per PI directive
        xvf3800_set_agc_enabled(XVF3800_AGC_ENABLED);
        if (XVF3800_DEREVERB_ENABLED) {
            xvf3800_enable_dereverb(true);
        }
        xvf3800_set_beam_mode(XVF3800_BEAM_MODE);

        char version[32];
        if (xvf3800_get_version(version, sizeof(version)) == ESP_OK) {
            ESP_LOGI(TAG, "XVF3800 firmware: %s", version);
        }
    }
#endif

#if CONFIG_TRANSPORT_MQTT_OFFLOAD
    // Plug-and-play path: offload_app owns Wi-Fi (NVS creds -> default site SSID ->
    // captive portal), discovers the sink via mDNS, negotiates, and starts the MQTT
    // segment sender once an assignment arrives. No compiled server IP, no TCP client.
    ESP_LOGI(TAG, "Starting plug-and-play offload app...");
    offload_app_start(&s_app_ctx);
#else
    // Initialize WiFi
    ESP_LOGI(TAG, "Initializing WiFi...");
    wifi_manager_config_t wifi_config = {
        .max_retry_count = WIFI_MAXIMUM_RETRY,
        .retry_interval_ms = RECONNECT_DELAY_MS
    };
    strncpy(wifi_config.ssid, CONFIG_WIFI_SSID, sizeof(wifi_config.ssid));
    strncpy(wifi_config.password, CONFIG_WIFI_PASSWORD, sizeof(wifi_config.password));

    ret = wifi_manager_init(&wifi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize WiFi manager: %s", esp_err_to_name(ret));
        s_audio_state = AUDIO_STATE_FATAL;
        return;
    }

    // Initialize TCP client
    ESP_LOGI(TAG, "Initializing TCP client...");
    tcp_client_config_t tcp_config = {
        .server_port = SERVER_PORT,
        .connect_timeout_ms = TCP_CONNECT_TIMEOUT_MS,
        .handshake_timeout_ms = HANDSHAKE_TIMEOUT_MS,
        .reconnect_delay_ms = RECONNECT_DELAY_MS
    };
    strncpy(tcp_config.server_host, CONFIG_SERVER_HOST, sizeof(tcp_config.server_host));

    ret = tcp_client_init(&tcp_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize TCP client: %s", esp_err_to_name(ret));
        s_audio_state = AUDIO_STATE_FATAL;
        return;
    }

    // Start WiFi connection
    ESP_LOGI(TAG, "Starting WiFi connection...");
    ret = wifi_manager_start();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WiFi: %s", esp_err_to_name(ret));
    }
#endif

    s_audio_state = AUDIO_STATE_RUNNING;

    // Create tasks
    ESP_LOGI(TAG, "Creating tasks...");

    // I2S Capture Task (Core 1 - Audio)
    xTaskCreatePinnedToCore(
        i2s_capture_task,
        "i2s_capture",
        TASK_STACK_I2S_CAPTURE,
        NULL,
        TASK_PRIORITY_I2S_CAPTURE,
        &s_i2s_capture_task,
        TASK_CORE_AUDIO
    );

    // VAD Processor Task (Core 1 - Audio)
    xTaskCreatePinnedToCore(
        vad_processor_task,
        "vad_proc",
        TASK_STACK_VAD,
        NULL,
        TASK_PRIORITY_VAD,
        &s_vad_task,
        TASK_CORE_AUDIO
    );

#if !CONFIG_TRANSPORT_MQTT_OFFLOAD
    // TCP Sender Task (Core 0 - Network). In offload mode the MQTT sender (started by
    // offload_app once an assignment arrives) drains the speech queue instead.
    xTaskCreatePinnedToCore(
        tcp_sender_task,
        "tcp_sender",
        TASK_STACK_TCP_SENDER,
        NULL,
        TASK_PRIORITY_TCP_SENDER,
        &s_tcp_sender_task,
        TASK_CORE_NETWORK
    );
#endif

#if BOARD_TYPE_XVF3800
    // DSP Control Task (Core 0 - Network)
    xTaskCreatePinnedToCore(
        dsp_control_task,
        "dsp_ctrl",
        TASK_STACK_DSP_CONTROL,
        NULL,
        TASK_PRIORITY_DSP_CONTROL,
        &s_dsp_control_task,
        TASK_CORE_NETWORK
    );
#endif

    // Telemetry Task (Core 0)
#if CONFIG_ENABLE_TELEMETRY
    xTaskCreatePinnedToCore(
        telemetry_task,
        "telemetry",
        TASK_STACK_TELEMETRY,
        NULL,
        3,
        NULL,
        TASK_CORE_NETWORK
    );
#endif

    ESP_LOGI(TAG, "Firmware initialization complete. Starting audio capture...");
}

// =============================================================================
// I2S Capture Task
// =============================================================================

static void i2s_capture_task(void *param)
{
    ESP_LOGI(TAG, "I2S capture task started on core %d", xPortGetCoreID());

    // Register with watchdog manager
    esp_err_t wdt_ret = watchdog_register_task();
    if (wdt_ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to register with watchdog: %s", esp_err_to_name(wdt_ret));
    }

    // Buffer for raw I2S data (32-bit samples)
    const size_t samples_per_read = I2S_DMA_BUF_LEN;
    int32_t *raw_buffer = heap_caps_malloc(samples_per_read * sizeof(int32_t), MALLOC_CAP_DMA);
    int16_t *processed_buffer = heap_caps_malloc(samples_per_read * sizeof(int16_t), MALLOC_CAP_INTERNAL);

    if (raw_buffer == NULL || processed_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate I2S buffers");
        watchdog_unregister_task();
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        // Feed watchdog
        watchdog_feed();

        // Read from I2S
        size_t bytes_read = 0;
        esp_err_t ret = hal_audio_read(raw_buffer, samples_per_read * sizeof(int32_t),
                                        &bytes_read, I2S_READ_TIMEOUT_MS);

        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "I2S read error: %s", esp_err_to_name(ret));
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        size_t samples_read = bytes_read / sizeof(int32_t);
        if (samples_read == 0) {
            continue;
        }

#if CONFIG_ENABLE_AUDIO_DEBUG
        // Bring-up instrumentation: raw 32-bit sample stats every ~2 s.
        // Splits wrong-DIN-pin (all zero) / wrong-shift (energy only in low
        // 16 bits) / VAD-threshold (healthy hi-16 energy) in one look.
        {
            static uint32_t s_dbg_iter = 0;
            if ((s_dbg_iter++ % 64) == 0) {   // 512 samples/read @16k => ~2 s
                int32_t mn = raw_buffer[0], mx = raw_buffer[0];
                uint64_t acc_hi = 0, acc_lo = 0;
                for (size_t i = 0; i < samples_read; i += I2S_SLOT_STRIDE) {
                    int32_t v = raw_buffer[i];
                    if (v < mn) mn = v;
                    if (v > mx) mx = v;
                    int32_t hi = v >> 16;
                    int32_t lo = (int16_t)(v & 0xFFFF);
                    acc_hi += (uint64_t)(hi * hi);
                    acc_lo += (uint64_t)(lo * lo);
                }
                size_t dbg_frames = samples_read / I2S_SLOT_STRIDE;
                ESP_LOGI(TAG, "RAWDBG min=%ld max=%ld rms_hi16=%lu rms_lo16=%lu",
                         (long)mn, (long)mx,
                         (unsigned long)sqrtf((float)(acc_hi / dbg_frames)),
                         (unsigned long)sqrtf((float)(acc_lo / dbg_frames)));
            }
        }
#endif

        // Process samples: convert 32-bit to 16-bit with soft limiting.
        // Stereo boards (Lite): deinterleave — keep slot 0 (processed mic) only.
        size_t frames = samples_read / I2S_SLOT_STRIDE;
        for (size_t i = 0; i < frames; i++) {
            // Apply digital gain (board-specific)
            int32_t sample = raw_buffer[i * I2S_SLOT_STRIDE] >> DIGITAL_GAIN_SHIFT;

            // Apply soft-knee limiter (instead of hard clipping)
            float fsample = (float)sample;
            fsample = audio_soft_limit(fsample);

            // Apply DC blocker
            fsample = audio_dc_block(fsample);

            // Convert to int16
            processed_buffer[i] = (int16_t)fsample;
        }

        // Write to ring buffer
        ret = audio_buffer_write(processed_buffer, frames * sizeof(int16_t));
        if (ret != ESP_OK) {
            s_telemetry.buffer_overflows++;
            ESP_LOGW(TAG, "Ring buffer overflow - dropping audio");
        }

        s_telemetry.audio_chunks_captured++;
    }

    free(raw_buffer);
    free(processed_buffer);
    vTaskDelete(NULL);
}

// =============================================================================
// VAD Processor Task
// =============================================================================

static void vad_processor_task(void *param)
{
    ESP_LOGI(TAG, "VAD processor task started on core %d", xPortGetCoreID());

    // Buffer for VAD processing
    const size_t vad_frame_samples = 512;  // ~32ms at 16kHz
    int16_t *frame_buffer = heap_caps_malloc(vad_frame_samples * sizeof(int16_t), MALLOC_CAP_INTERNAL);

    // Accumulation buffer for speech chunks
    int16_t *speech_buffer = heap_caps_malloc(AUDIO_CHUNK_BYTES, MALLOC_CAP_SPIRAM);
    size_t speech_buffer_pos = 0;

    if (frame_buffer == NULL || speech_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate VAD buffers");
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        // Read frame from ring buffer
        size_t bytes_read = 0;
        esp_err_t ret = audio_buffer_read(frame_buffer, vad_frame_samples * sizeof(int16_t),
                                           &bytes_read, pdMS_TO_TICKS(100));

        if (ret != ESP_OK || bytes_read == 0) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        size_t samples_read = bytes_read / sizeof(int16_t);

        // Process VAD
        vad_result_t vad_result = vad_process(frame_buffer, samples_read);

        // Accumulate speech frames
        if (vad_result == VAD_RESULT_SPEECH || vad_result == VAD_RESULT_HANGOVER) {
            size_t bytes_to_copy = samples_read * sizeof(int16_t);
            if (speech_buffer_pos + bytes_to_copy <= AUDIO_CHUNK_BYTES) {
                memcpy(&speech_buffer[speech_buffer_pos / sizeof(int16_t)],
                       frame_buffer, bytes_to_copy);
                speech_buffer_pos += bytes_to_copy;
            }

            // Check if we have a complete chunk
            if (speech_buffer_pos >= AUDIO_CHUNK_BYTES) {
                // Calculate quality metrics
                audio_quality_metrics_t metrics;
                audio_calculate_quality_metrics(speech_buffer, AUDIO_CHUNK_SAMPLES, &metrics);

                // Validate quality
                audio_quality_status_t status = audio_validate_quality(&metrics);

                if (status == AUDIO_QUALITY_GOOD) {
                    // Queue for transmission
                    ret = audio_buffer_write_speech(speech_buffer, AUDIO_CHUNK_BYTES, &metrics);
                    if (ret == ESP_OK) {
                        s_telemetry.avg_audio_rms =
                            (s_telemetry.avg_audio_rms * 0.9f) + (metrics.rms * 0.1f);
                    }
                } else {
                    ESP_LOGW(TAG, "Audio chunk rejected: quality status %d", status);
                }

                // Reset buffer
                speech_buffer_pos = 0;
            }
        } else {
            // Silence - if we have partial speech, process it
            if (speech_buffer_pos > AUDIO_SAMPLE_RATE * sizeof(int16_t)) {  // > 1 second
                // Process partial chunk
                size_t samples = speech_buffer_pos / sizeof(int16_t);
                audio_quality_metrics_t metrics;
                audio_calculate_quality_metrics(speech_buffer, samples, &metrics);

                audio_quality_status_t status = audio_validate_quality(&metrics);
                if (status == AUDIO_QUALITY_GOOD) {
                    audio_buffer_write_speech(speech_buffer, speech_buffer_pos, &metrics);
                }
            }
            speech_buffer_pos = 0;
        }
    }

    free(frame_buffer);
    free(speech_buffer);
    vTaskDelete(NULL);
}

// =============================================================================
// TCP Sender Task
// =============================================================================

static void tcp_sender_task(void *param)
{
    ESP_LOGI(TAG, "TCP sender task started on core %d", xPortGetCoreID());

    // Wait for WiFi connection
    ESP_LOGI(TAG, "Waiting for WiFi connection...");
    while (!wifi_manager_is_connected()) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    ESP_LOGI(TAG, "WiFi connected!");

    // Buffer for speech data
    uint8_t *send_buffer = heap_caps_malloc(AUDIO_CHUNK_BYTES, MALLOC_CAP_SPIRAM);
    if (send_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate send buffer");
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        // Ensure TCP connection
        if (!tcp_client_is_connected()) {
            ESP_LOGI(TAG, "Connecting to server...");
            esp_err_t ret = tcp_client_connect();
            if (ret != ESP_OK) {
                ESP_LOGW(TAG, "Failed to connect: %s", esp_err_to_name(ret));
                s_telemetry.tcp_reconnections++;
                vTaskDelay(pdMS_TO_TICKS(RECONNECT_DELAY_MS));
                continue;
            }
            ESP_LOGI(TAG, "Connected to server!");
        }

        // Read speech chunk from queue
        size_t bytes_read = 0;
        audio_quality_metrics_t metrics;
        esp_err_t ret = audio_buffer_read_speech(send_buffer, AUDIO_CHUNK_BYTES,
                                                   &bytes_read, &metrics, pdMS_TO_TICKS(100));

        if (ret != ESP_OK || bytes_read == 0) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        // Send audio data
        ret = tcp_client_send(send_buffer, bytes_read);
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Failed to send audio: %s", esp_err_to_name(ret));
            tcp_client_disconnect();
            continue;
        }

        s_telemetry.audio_chunks_sent++;

#if CONFIG_ENABLE_AUDIO_DEBUG
        ESP_LOGD(TAG, "Sent %d bytes, RMS=%.1f, dBFS=%.1f",
                 bytes_read, metrics.rms, metrics.db_fs);
#endif
    }

    free(send_buffer);
    vTaskDelete(NULL);
}

// =============================================================================
// DSP Control Task (XVF3800 only)
// =============================================================================

#if BOARD_TYPE_XVF3800
static void dsp_control_task(void *param)
{
    ESP_LOGI(TAG, "DSP control task started on core %d", xPortGetCoreID());

    while (1) {
        // Periodically query DoA if enabled
#if XVF3800_INCLUDE_DOA
        doa_metadata_t doa;
        if (xvf3800_get_doa(&doa.azimuth_degrees, &doa.confidence) == ESP_OK) {
            // Store DoA for next audio chunk
            // This will be included in the metadata sent to server
        }
#endif

        vTaskDelay(pdMS_TO_TICKS(100));  // Query every 100ms
    }

    vTaskDelete(NULL);
}
#endif

// =============================================================================
// Telemetry Task
// =============================================================================

static void telemetry_task(void *param)
{
    ESP_LOGI(TAG, "Telemetry task started");

    TickType_t last_wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(60000);  // Every 60 seconds

    while (1) {
        vTaskDelayUntil(&last_wake, period);

        s_telemetry.uptime_seconds += 60;
        s_telemetry.free_heap = esp_get_free_heap_size();
        s_telemetry.free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);

        wifi_ap_record_t ap_info;
        if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
            s_telemetry.wifi_rssi = ap_info.rssi;
        }

#if CONFIG_TRANSPORT_MQTT_OFFLOAD
        // In offload mode the MQTT sender owns the send counters — report those.
        // (audio_chunks_sent is the legacy TCP path's counter and stays 0 here,
        // which made silently-failing nodes look healthy at first fleet bring-up.)
        mqtt_sender_stats_t ss;
        mqtt_sender_get_stats(&ss);
        ESP_LOGI(TAG, "Telemetry: uptime=%lus, seg_pub=%u, seg_drop=%u, pub_fail=%u, overflows=%lu, heap=%lu, rssi=%d",
                 s_telemetry.uptime_seconds,
                 (unsigned)ss.segments_published,
                 (unsigned)ss.segments_dropped,
                 (unsigned)ss.publish_failures,
                 s_telemetry.buffer_overflows,
                 s_telemetry.free_heap,
                 s_telemetry.wifi_rssi);
#else
        ESP_LOGI(TAG, "Telemetry: uptime=%lus, chunks_sent=%lu, overflows=%lu, heap=%lu, rssi=%d",
                 s_telemetry.uptime_seconds,
                 s_telemetry.audio_chunks_sent,
                 s_telemetry.buffer_overflows,
                 s_telemetry.free_heap,
                 s_telemetry.wifi_rssi);
#endif
    }

    vTaskDelete(NULL);
}
