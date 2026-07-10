/**
 * @file hal_audio.c
 * @brief Hardware Abstraction Layer for Audio I2S - Implementation
 *
 * Uses ESP-IDF 5.x I2S channel API.
 *
 * @copyright IHearYou Research Project
 */

#include "hal_audio.h"
#include "config/board_config.h"
#include "config/audio_config.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include <math.h>

static const char *TAG = "HAL_AUDIO";

// =============================================================================
// Static Variables
// =============================================================================

static i2s_chan_handle_t s_rx_handle = NULL;
#if BOARD_TYPE_XVF3800
static i2s_chan_handle_t s_tx_handle = NULL;
#endif

static bool s_initialized = false;

// DC blocker state
static float s_dc_prev_input = 0.0f;
static float s_dc_prev_output = 0.0f;
static const float DC_BLOCKER_ALPHA = 0.995f;

// Soft limiter configuration
static soft_limiter_config_t s_limiter_config = SOFT_LIMITER_DEFAULT;

// =============================================================================
// Initialization
// =============================================================================

esp_err_t hal_audio_init(void)
{
    if (s_initialized) {
        ESP_LOGW(TAG, "Audio HAL already initialized");
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Initializing I2S for %s", BOARD_NAME);

    // Create I2S channel
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE);

    esp_err_t ret;

#if BOARD_TYPE_XVF3800
    // XVF3800: Create both RX and TX channels
    ret = i2s_new_channel(&chan_cfg, &s_tx_handle, &s_rx_handle);
#else
    // ReSpeaker Lite: RX only
    ret = i2s_new_channel(&chan_cfg, NULL, &s_rx_handle);
#endif

    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2S channel: %s", esp_err_to_name(ret));
        return ret;
    }

    // Configure I2S standard mode
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_BITS_PER_SAMPLE, I2S_SLOT_MODE),
        .gpio_cfg = {
            .mclk = I2S_MCLK_PIN,
            .bclk = I2S_BCK_PIN,
            .ws = I2S_WS_PIN,
            .dout = I2S_DOUT_PIN,
            .din = I2S_DIN_PIN,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };

    // Initialize RX channel
    ret = i2s_channel_init_std_mode(s_rx_handle, &std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to init I2S RX: %s", esp_err_to_name(ret));
        i2s_del_channel(s_rx_handle);
        s_rx_handle = NULL;
        return ret;
    }

#if BOARD_TYPE_XVF3800
    // Initialize TX channel for AEC reference
    ret = i2s_channel_init_std_mode(s_tx_handle, &std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to init I2S TX (AEC disabled): %s", esp_err_to_name(ret));
        // Continue without TX - AEC won't work but audio capture will
    }
#endif

    // Enable RX channel
    ret = i2s_channel_enable(s_rx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable I2S RX: %s", esp_err_to_name(ret));
        i2s_del_channel(s_rx_handle);
        s_rx_handle = NULL;
        return ret;
    }

#if BOARD_TYPE_XVF3800
    if (s_tx_handle != NULL) {
        ret = i2s_channel_enable(s_tx_handle);
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "Failed to enable I2S TX");
        }
    }
#endif

    s_initialized = true;
    ESP_LOGI(TAG, "I2S initialized successfully");
    ESP_LOGI(TAG, "  Sample rate: %d Hz", AUDIO_SAMPLE_RATE);
    ESP_LOGI(TAG, "  Bits per sample: 32 (input) -> 16 (output)");
    ESP_LOGI(TAG, "  DMA buffers: %d x %d samples", I2S_DMA_BUF_COUNT, I2S_DMA_BUF_LEN);

    return ESP_OK;
}

esp_err_t hal_audio_deinit(void)
{
    if (!s_initialized) {
        return ESP_OK;
    }

    if (s_rx_handle != NULL) {
        i2s_channel_disable(s_rx_handle);
        i2s_del_channel(s_rx_handle);
        s_rx_handle = NULL;
    }

#if BOARD_TYPE_XVF3800
    if (s_tx_handle != NULL) {
        i2s_channel_disable(s_tx_handle);
        i2s_del_channel(s_tx_handle);
        s_tx_handle = NULL;
    }
#endif

    s_initialized = false;
    ESP_LOGI(TAG, "I2S deinitialized");

    return ESP_OK;
}

// =============================================================================
// Read/Write Operations
// =============================================================================

esp_err_t hal_audio_read(void *buffer, size_t buffer_size,
                          size_t *bytes_read, uint32_t timeout_ms)
{
    if (!s_initialized || s_rx_handle == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (buffer == NULL || bytes_read == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    return i2s_channel_read(s_rx_handle, buffer, buffer_size, bytes_read,
                             pdMS_TO_TICKS(timeout_ms));
}

esp_err_t hal_audio_write(const void *buffer, size_t buffer_size,
                           size_t *bytes_written, uint32_t timeout_ms)
{
#if BOARD_TYPE_XVF3800
    if (!s_initialized || s_tx_handle == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (buffer == NULL || bytes_written == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    return i2s_channel_write(s_tx_handle, buffer, buffer_size, bytes_written,
                              pdMS_TO_TICKS(timeout_ms));
#else
    return ESP_ERR_NOT_SUPPORTED;
#endif
}

bool hal_audio_is_initialized(void)
{
    return s_initialized;
}

uint32_t hal_audio_get_sample_rate(void)
{
    return AUDIO_SAMPLE_RATE;
}

// =============================================================================
// Audio Processing Functions
// =============================================================================

float audio_soft_limit(float sample)
{
    float threshold = s_limiter_config.threshold;
    float knee = s_limiter_config.knee;
    float ratio = s_limiter_config.ratio;

    float abs_sample = fabsf(sample);

    if (abs_sample < threshold - knee / 2.0f) {
        // Linear region - no change
        return sample;
    } else if (abs_sample < threshold + knee / 2.0f) {
        // Soft knee region
        float x = abs_sample - threshold + knee / 2.0f;
        float compressed = threshold - knee / 2.0f + x - (x * x) / (2.0f * knee);
        return copysignf(compressed, sample);
    } else {
        // Compression region
        float excess = abs_sample - threshold;
        float compressed = threshold + excess * ratio;
        return copysignf(compressed, sample);
    }
}

float audio_dc_block(float sample)
{
    // High-pass filter: y[n] = x[n] - x[n-1] + alpha * y[n-1]
    float output = sample - s_dc_prev_input + DC_BLOCKER_ALPHA * s_dc_prev_output;

    s_dc_prev_input = sample;
    s_dc_prev_output = output;

    return output;
}
