/**
 * @file hal_audio.h
 * @brief Hardware Abstraction Layer for Audio I2S
 *
 * Provides unified interface for both ReSpeaker Lite and XVF3800 boards.
 *
 * @copyright IHearYou Research Project
 */

#ifndef HAL_AUDIO_H
#define HAL_AUDIO_H

#include "esp_err.h"
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize the audio HAL
 *
 * Configures I2S peripheral for the target board.
 * - ReSpeaker Lite: I2S slave mode, receives from XU316
 * - XVF3800: I2S slave mode, receives from XVF3800, optional TX for AEC
 *
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t hal_audio_init(void);

/**
 * @brief Deinitialize the audio HAL
 *
 * Releases I2S resources.
 *
 * @return ESP_OK on success
 */
esp_err_t hal_audio_deinit(void);

/**
 * @brief Read audio data from I2S
 *
 * Blocking read with timeout. Returns raw 32-bit samples from I2S.
 * Caller is responsible for conversion to 16-bit.
 *
 * @param buffer Buffer to store audio data
 * @param buffer_size Size of buffer in bytes
 * @param bytes_read Actual bytes read
 * @param timeout_ms Read timeout in milliseconds
 * @return ESP_OK on success, ESP_ERR_TIMEOUT on timeout
 */
esp_err_t hal_audio_read(void *buffer, size_t buffer_size,
                          size_t *bytes_read, uint32_t timeout_ms);

/**
 * @brief Write audio data to I2S (XVF3800 only)
 *
 * Used for reference audio for AEC.
 *
 * @param buffer Audio data to write
 * @param buffer_size Size of data in bytes
 * @param bytes_written Actual bytes written
 * @param timeout_ms Write timeout in milliseconds
 * @return ESP_OK on success, ESP_ERR_NOT_SUPPORTED if TX not available
 */
esp_err_t hal_audio_write(const void *buffer, size_t buffer_size,
                           size_t *bytes_written, uint32_t timeout_ms);

/**
 * @brief Check if audio HAL is initialized
 *
 * @return true if initialized, false otherwise
 */
bool hal_audio_is_initialized(void);

/**
 * @brief Get current audio sample rate
 *
 * @return Sample rate in Hz
 */
uint32_t hal_audio_get_sample_rate(void);

/**
 * @brief Apply soft-knee limiting to a sample
 *
 * Used instead of hard clipping to preserve jitter/shimmer measurements.
 *
 * @param sample Input sample (float)
 * @return Limited sample
 */
float audio_soft_limit(float sample);

/**
 * @brief Apply DC blocking filter to a sample
 *
 * High-pass filter to remove DC offset (~20Hz cutoff).
 *
 * @param sample Input sample (float)
 * @return Filtered sample
 */
float audio_dc_block(float sample);

#ifdef __cplusplus
}
#endif

#endif // HAL_AUDIO_H
