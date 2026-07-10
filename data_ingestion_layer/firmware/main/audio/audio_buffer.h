/**
 * @file audio_buffer.h
 * @brief Audio Ring Buffer with PSRAM support
 *
 * @copyright IHearYou Research Project
 */

#ifndef AUDIO_BUFFER_H
#define AUDIO_BUFFER_H

#include "esp_err.h"
#include "config/audio_config.h"
#include "freertos/FreeRTOS.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize the audio buffer system
 *
 * Allocates ring buffers in PSRAM.
 *
 * @return ESP_OK on success
 */
esp_err_t audio_buffer_init(void);

/**
 * @brief Deinitialize the audio buffer system
 *
 * @return ESP_OK on success
 */
esp_err_t audio_buffer_deinit(void);

/**
 * @brief Write raw audio data to the ring buffer
 *
 * @param data Audio data (int16_t samples)
 * @param size Size in bytes
 * @return ESP_OK on success, ESP_ERR_NO_MEM if buffer full
 */
esp_err_t audio_buffer_write(const int16_t *data, size_t size);

/**
 * @brief Read raw audio data from the ring buffer
 *
 * @param data Buffer to store data
 * @param size Maximum bytes to read
 * @param bytes_read Actual bytes read
 * @param timeout Timeout in ticks
 * @return ESP_OK on success
 */
esp_err_t audio_buffer_read(int16_t *data, size_t size,
                             size_t *bytes_read, TickType_t timeout);

/**
 * @brief Write speech chunk with quality metrics to transmission queue
 *
 * @param data Speech audio data
 * @param size Size in bytes
 * @param metrics Quality metrics for the chunk
 * @return ESP_OK on success
 */
esp_err_t audio_buffer_write_speech(const int16_t *data, size_t size,
                                      const audio_quality_metrics_t *metrics);

/**
 * @brief Read speech chunk from transmission queue
 *
 * @param data Buffer to store data
 * @param max_size Maximum bytes to read
 * @param bytes_read Actual bytes read
 * @param metrics Quality metrics for the chunk
 * @param timeout Timeout in ticks
 * @return ESP_OK on success
 */
esp_err_t audio_buffer_read_speech(uint8_t *data, size_t max_size,
                                     size_t *bytes_read,
                                     audio_quality_metrics_t *metrics,
                                     TickType_t timeout);

/**
 * @brief Get current buffer fill level
 *
 * @return Fill level as percentage (0-100)
 */
uint8_t audio_buffer_get_fill_percent(void);

/**
 * @brief Check if buffer is above high watermark
 *
 * @return true if above high watermark
 */
bool audio_buffer_is_high_watermark(void);

/**
 * @brief Get buffer statistics
 *
 * @param total_size Total buffer size in bytes
 * @param used_size Used bytes
 * @param overflow_count Number of overflows since init
 */
void audio_buffer_get_stats(size_t *total_size, size_t *used_size,
                             uint32_t *overflow_count);

#ifdef __cplusplus
}
#endif

#endif // AUDIO_BUFFER_H
