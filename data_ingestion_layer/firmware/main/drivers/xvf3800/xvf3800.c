/**
 * @file xvf3800.c
 * @brief XMOS XVF3800 DSP Driver - Implementation
 *
 * @copyright IHearYou Research Project
 */

#include "xvf3800.h"
#include "xvf3800_i2c.h"
#include "config/board_config.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>
#include <stdio.h>

static const char *TAG = "XVF3800";

// =============================================================================
// Static Variables
// =============================================================================

static bool s_initialized = false;
static xvf3800_config_t s_config = XVF3800_CONFIG_DEFAULT;

// =============================================================================
// Internal Functions
// =============================================================================

static esp_err_t wait_for_ready(uint32_t timeout_ms)
{
    uint32_t start = xTaskGetTickCount() * portTICK_PERIOD_MS;

    while ((xTaskGetTickCount() * portTICK_PERIOD_MS - start) < timeout_ms) {
        uint8_t status;
        if (xvf3800_i2c_read_reg(XVF3800_REG_STATUS, &status) == ESP_OK) {
            if (status & 0x01) {  // Ready bit
                return ESP_OK;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    return ESP_ERR_TIMEOUT;
}

// =============================================================================
// Public Functions
// =============================================================================

esp_err_t xvf3800_init(int i2c_port)
{
    if (s_initialized) {
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Initializing XVF3800 driver");

    // Initialize I2C
    esp_err_t ret = xvf3800_i2c_init(i2c_port);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize I2C: %s", esp_err_to_name(ret));
        return ret;
    }

    // Probe device
    if (!xvf3800_i2c_probe()) {
        ESP_LOGE(TAG, "XVF3800 not detected at address 0x%02X", XVF3800_I2C_ADDR);
        xvf3800_i2c_deinit();
        return ESP_ERR_NOT_FOUND;
    }

    // Wait for device ready
    ret = wait_for_ready(1000);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "XVF3800 not ready: %s", esp_err_to_name(ret));
        xvf3800_i2c_deinit();
        return ret;
    }

    s_initialized = true;

    // Read and log version
    char version[XVF3800_VERSION_MAX_LEN];
    if (xvf3800_get_version(version, sizeof(version)) == ESP_OK) {
        ESP_LOGI(TAG, "XVF3800 initialized, firmware: %s", version);
    } else {
        ESP_LOGI(TAG, "XVF3800 initialized");
    }

    return ESP_OK;
}

esp_err_t xvf3800_deinit(void)
{
    if (!s_initialized) {
        return ESP_OK;
    }

    esp_err_t ret = xvf3800_i2c_deinit();
    s_initialized = false;

    ESP_LOGI(TAG, "XVF3800 deinitialized");
    return ret;
}

bool xvf3800_is_ready(void)
{
    if (!s_initialized) {
        return false;
    }

    return xvf3800_i2c_probe();
}

esp_err_t xvf3800_get_status(xvf3800_status_t *status)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (status == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    uint8_t reg_val;
    esp_err_t ret = xvf3800_i2c_read_reg(XVF3800_REG_STATUS, &reg_val);
    if (ret != ESP_OK) {
        return ret;
    }

    status->ready = (reg_val & 0x01) != 0;
    status->voice_detected = (reg_val & 0x02) != 0;
    status->aec_active = (reg_val & 0x04) != 0;
    status->error = (reg_val & 0x80) != 0;

    return ESP_OK;
}

esp_err_t xvf3800_get_version(char *version, size_t len)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (version == NULL || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Read version bytes (format: major.minor.patch)
    uint8_t ver_bytes[3];
    esp_err_t ret = xvf3800_i2c_read_reg_multi(XVF3800_REG_VERSION, ver_bytes, 3);
    if (ret != ESP_OK) {
        return ret;
    }

    snprintf(version, len, "%d.%d.%d", ver_bytes[0], ver_bytes[1], ver_bytes[2]);
    return ESP_OK;
}

esp_err_t xvf3800_configure(const xvf3800_config_t *config)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (config == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t ret;

    // Store config
    memcpy(&s_config, config, sizeof(xvf3800_config_t));

    // Apply AGC settings
    ret = xvf3800_set_agc_enabled(config->agc_enabled);
    if (ret != ESP_OK) return ret;

    if (config->agc_enabled) {
        ret = xvf3800_i2c_write_reg(XVF3800_REG_AGC_TARGET, config->agc_target_db);
        if (ret != ESP_OK) return ret;
        ret = xvf3800_i2c_write_reg(XVF3800_REG_AGC_MAX_GAIN, config->agc_max_gain_db);
        if (ret != ESP_OK) return ret;
    }

    // Apply NS settings
    ret = xvf3800_set_ns_enabled(config->ns_enabled);
    if (ret != ESP_OK) return ret;

    if (config->ns_enabled) {
        ret = xvf3800_i2c_write_reg(XVF3800_REG_NS_LEVEL, config->ns_level);
        if (ret != ESP_OK) return ret;
    }

    // Apply de-reverb settings
    ret = xvf3800_enable_dereverb(config->dereverb_enabled);
    if (ret != ESP_OK) return ret;

    if (config->dereverb_enabled) {
        ret = xvf3800_i2c_write_reg(XVF3800_REG_DEREVERB_DECAY, config->dereverb_decay);
        if (ret != ESP_OK) return ret;
    }

    // Apply beam settings
    ret = xvf3800_set_beam_mode(config->beam_mode);
    if (ret != ESP_OK) return ret;

    if (config->beam_mode == XVF3800_BEAM_FIXED) {
        ret = xvf3800_set_beam_direction(config->beam_direction);
        if (ret != ESP_OK) return ret;
    }

    // Apply DoA settings
    ret = xvf3800_i2c_write_reg(XVF3800_REG_DOA_ENABLE, config->doa_enabled ? 1 : 0);
    if (ret != ESP_OK) return ret;

    ESP_LOGI(TAG, "Configuration applied: AGC=%d, NS=%d, DeReverb=%d, BeamMode=%d, DoA=%d",
             config->agc_enabled, config->ns_enabled, config->dereverb_enabled,
             config->beam_mode, config->doa_enabled);

    return ESP_OK;
}

esp_err_t xvf3800_set_agc_enabled(bool enabled)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_err_t ret = xvf3800_i2c_write_reg(XVF3800_REG_AGC_ENABLE, enabled ? 1 : 0);
    if (ret == ESP_OK) {
        s_config.agc_enabled = enabled;
        ESP_LOGI(TAG, "AGC %s", enabled ? "enabled" : "disabled");
    }
    return ret;
}

esp_err_t xvf3800_set_ns_enabled(bool enabled)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_err_t ret = xvf3800_i2c_write_reg(XVF3800_REG_NS_ENABLE, enabled ? 1 : 0);
    if (ret == ESP_OK) {
        s_config.ns_enabled = enabled;
        ESP_LOGI(TAG, "NS %s", enabled ? "enabled" : "disabled");
    }
    return ret;
}

esp_err_t xvf3800_enable_dereverb(bool enabled)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_err_t ret = xvf3800_i2c_write_reg(XVF3800_REG_DEREVERB_ENABLE, enabled ? 1 : 0);
    if (ret == ESP_OK) {
        s_config.dereverb_enabled = enabled;
        ESP_LOGI(TAG, "De-reverb %s", enabled ? "enabled" : "disabled");
    }
    return ret;
}

esp_err_t xvf3800_set_beam_mode(xvf3800_beam_mode_t mode)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    esp_err_t ret = xvf3800_i2c_write_reg(XVF3800_REG_BEAM_MODE, (uint8_t)mode);
    if (ret == ESP_OK) {
        s_config.beam_mode = mode;
        ESP_LOGI(TAG, "Beam mode set to %s", mode == XVF3800_BEAM_FIXED ? "fixed" : "adaptive");
    }
    return ret;
}

esp_err_t xvf3800_set_beam_direction(int16_t degrees)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    // Clamp to valid range
    if (degrees < -180) degrees = -180;
    if (degrees > 180) degrees = 180;

    // Send as two bytes (signed 16-bit)
    uint8_t data[2] = {
        (uint8_t)(degrees & 0xFF),
        (uint8_t)((degrees >> 8) & 0xFF)
    };

    esp_err_t ret = xvf3800_i2c_write_reg_multi(XVF3800_REG_BEAM_DIRECTION, data, 2);
    if (ret == ESP_OK) {
        s_config.beam_direction = degrees;
        ESP_LOGI(TAG, "Beam direction set to %d degrees", degrees);
    }
    return ret;
}

esp_err_t xvf3800_get_doa(int16_t *azimuth, uint8_t *confidence)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (azimuth == NULL || confidence == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    // Read azimuth (2 bytes, signed)
    uint8_t az_data[2];
    esp_err_t ret = xvf3800_i2c_read_reg_multi(XVF3800_REG_DOA_AZIMUTH, az_data, 2);
    if (ret != ESP_OK) {
        return ret;
    }

    *azimuth = (int16_t)(az_data[0] | (az_data[1] << 8));

    // Read confidence (1 byte)
    ret = xvf3800_i2c_read_reg(XVF3800_REG_DOA_CONFIDENCE, confidence);
    if (ret != ESP_OK) {
        return ret;
    }

    return ESP_OK;
}

esp_err_t xvf3800_get_doa_full(xvf3800_doa_t *doa)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (doa == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t ret = xvf3800_get_doa(&doa->azimuth_degrees, &doa->confidence);
    if (ret == ESP_OK) {
        doa->timestamp = xTaskGetTickCount() * portTICK_PERIOD_MS;
    }

    return ret;
}

bool xvf3800_voice_detected(void)
{
    if (!s_initialized) {
        return false;
    }

    uint8_t status;
    if (xvf3800_i2c_read_reg(XVF3800_REG_VAD_STATUS, &status) != ESP_OK) {
        return false;
    }

    return (status & 0x01) != 0;
}

esp_err_t xvf3800_reset(void)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI(TAG, "Performing software reset");

    // Write reset command
    esp_err_t ret = xvf3800_i2c_write_reg(XVF3800_REG_CONTROL, 0x01);
    if (ret != ESP_OK) {
        return ret;
    }

    // Wait for device to restart
    vTaskDelay(pdMS_TO_TICKS(100));

    // Wait for ready
    ret = wait_for_ready(1000);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Device not ready after reset");
        return ret;
    }

    ESP_LOGI(TAG, "Reset complete");
    return ESP_OK;
}
