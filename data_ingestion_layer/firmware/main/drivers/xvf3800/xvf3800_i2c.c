/**
 * @file xvf3800_i2c.c
 * @brief XVF3800 I2C Low-Level Interface - Implementation
 *
 * Uses ESP-IDF 5.x new I2C master driver API.
 *
 * @copyright IHearYou Research Project
 */

#include "xvf3800_i2c.h"
#include "xvf3800.h"
#include "config/board_config.h"
#include "esp_log.h"
#include "driver/i2c_master.h"
#include <string.h>

static const char *TAG = "XVF3800_I2C";

// =============================================================================
// Static Variables
// =============================================================================

static i2c_master_bus_handle_t s_i2c_bus = NULL;
static i2c_master_dev_handle_t s_xvf3800_dev = NULL;
static bool s_initialized = false;

// =============================================================================
// Public Functions
// =============================================================================

esp_err_t xvf3800_i2c_init(int i2c_port)
{
    if (s_initialized) {
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Initializing I2C for XVF3800 on port %d", i2c_port);

    // Configure I2C master bus
    i2c_master_bus_config_t bus_config = {
        .i2c_port = i2c_port,
        .sda_io_num = XVF3800_I2C_SDA,
        .scl_io_num = XVF3800_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };

    esp_err_t ret = i2c_new_master_bus(&bus_config, &s_i2c_bus);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2C bus: %s", esp_err_to_name(ret));
        return ret;
    }

    // Add XVF3800 device
    i2c_device_config_t dev_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = XVF3800_I2C_ADDR,
        .scl_speed_hz = 400000,  // 400 kHz
    };

    ret = i2c_master_bus_add_device(s_i2c_bus, &dev_config, &s_xvf3800_dev);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add XVF3800 device: %s", esp_err_to_name(ret));
        i2c_del_master_bus(s_i2c_bus);
        s_i2c_bus = NULL;
        return ret;
    }

    s_initialized = true;
    ESP_LOGI(TAG, "I2C initialized: SDA=%d, SCL=%d, addr=0x%02X",
             XVF3800_I2C_SDA, XVF3800_I2C_SCL, XVF3800_I2C_ADDR);

    return ESP_OK;
}

esp_err_t xvf3800_i2c_deinit(void)
{
    if (!s_initialized) {
        return ESP_OK;
    }

    if (s_xvf3800_dev != NULL) {
        i2c_master_bus_rm_device(s_xvf3800_dev);
        s_xvf3800_dev = NULL;
    }

    if (s_i2c_bus != NULL) {
        i2c_del_master_bus(s_i2c_bus);
        s_i2c_bus = NULL;
    }

    s_initialized = false;
    ESP_LOGI(TAG, "I2C deinitialized");

    return ESP_OK;
}

esp_err_t xvf3800_i2c_write_reg(uint8_t reg, uint8_t value)
{
    if (!s_initialized || s_xvf3800_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    uint8_t write_buf[2] = {reg, value};

    esp_err_t ret = i2c_master_transmit(s_xvf3800_dev, write_buf, sizeof(write_buf),
                                         XVF3800_I2C_TIMEOUT_MS);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Write reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }

    return ret;
}

esp_err_t xvf3800_i2c_write_reg_multi(uint8_t reg, const uint8_t *data, size_t len)
{
    if (!s_initialized || s_xvf3800_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Create buffer with register address followed by data
    uint8_t *write_buf = malloc(len + 1);
    if (write_buf == NULL) {
        return ESP_ERR_NO_MEM;
    }

    write_buf[0] = reg;
    memcpy(&write_buf[1], data, len);

    esp_err_t ret = i2c_master_transmit(s_xvf3800_dev, write_buf, len + 1,
                                         XVF3800_I2C_TIMEOUT_MS);
    free(write_buf);

    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Write multi reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }

    return ret;
}

esp_err_t xvf3800_i2c_read_reg(uint8_t reg, uint8_t *value)
{
    if (!s_initialized || s_xvf3800_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (value == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    // Write register address, then read value
    esp_err_t ret = i2c_master_transmit_receive(s_xvf3800_dev,
                                                  &reg, 1,
                                                  value, 1,
                                                  XVF3800_I2C_TIMEOUT_MS);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Read reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }

    return ret;
}

esp_err_t xvf3800_i2c_read_reg_multi(uint8_t reg, uint8_t *data, size_t len)
{
    if (!s_initialized || s_xvf3800_dev == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Write register address, then read data
    esp_err_t ret = i2c_master_transmit_receive(s_xvf3800_dev,
                                                  &reg, 1,
                                                  data, len,
                                                  XVF3800_I2C_TIMEOUT_MS);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Read multi reg 0x%02X failed: %s", reg, esp_err_to_name(ret));
    }

    return ret;
}

bool xvf3800_i2c_probe(void)
{
    if (!s_initialized || s_xvf3800_dev == NULL) {
        return false;
    }

    // Try to read status register
    uint8_t value;
    esp_err_t ret = xvf3800_i2c_read_reg(XVF3800_REG_STATUS, &value);

    return (ret == ESP_OK);
}
