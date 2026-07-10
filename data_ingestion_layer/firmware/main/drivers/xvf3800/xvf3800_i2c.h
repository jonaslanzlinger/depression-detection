/**
 * @file xvf3800_i2c.h
 * @brief XVF3800 I2C Low-Level Interface - Header
 *
 * @copyright IHearYou Research Project
 */

#ifndef XVF3800_I2C_H
#define XVF3800_I2C_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize I2C interface for XVF3800
 *
 * @param i2c_port I2C port number
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_init(int i2c_port);

/**
 * @brief Deinitialize I2C interface
 *
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_deinit(void);

/**
 * @brief Write single byte to register
 *
 * @param reg Register address
 * @param value Value to write
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_write_reg(uint8_t reg, uint8_t value);

/**
 * @brief Write multiple bytes to register
 *
 * @param reg Register address
 * @param data Data buffer
 * @param len Data length
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_write_reg_multi(uint8_t reg, const uint8_t *data, size_t len);

/**
 * @brief Read single byte from register
 *
 * @param reg Register address
 * @param[out] value Value read
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_read_reg(uint8_t reg, uint8_t *value);

/**
 * @brief Read multiple bytes from register
 *
 * @param reg Register address
 * @param[out] data Data buffer
 * @param len Data length
 * @return ESP_OK on success
 */
esp_err_t xvf3800_i2c_read_reg_multi(uint8_t reg, uint8_t *data, size_t len);

/**
 * @brief Check if device responds at I2C address
 *
 * @return true if device responds
 */
bool xvf3800_i2c_probe(void);

#ifdef __cplusplus
}
#endif

#endif // XVF3800_I2C_H
