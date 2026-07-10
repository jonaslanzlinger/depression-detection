/**
 * @file vad.h
 * @brief Voice Activity Detection with adaptive calibration
 *
 * @copyright IHearYou Research Project
 */

#ifndef VAD_H
#define VAD_H

#include "esp_err.h"
#include "config/audio_config.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize VAD with configuration
 *
 * @param config VAD configuration
 * @return ESP_OK on success
 */
esp_err_t vad_init(const vad_config_t *config);

/**
 * @brief Deinitialize VAD
 *
 * @return ESP_OK on success
 */
esp_err_t vad_deinit(void);

/**
 * @brief Process audio frame for VAD
 *
 * @param samples Audio samples (int16_t)
 * @param sample_count Number of samples
 * @return VAD result (silence, speech, or hangover)
 */
vad_result_t vad_process(const int16_t *samples, size_t sample_count);

/**
 * @brief Get current VAD state
 *
 * @return Pointer to VAD state (read-only)
 */
const vad_state_t* vad_get_state(void);

/**
 * @brief Check if VAD is calibrated
 *
 * @return true if calibrated
 */
bool vad_is_calibrated(void);

/**
 * @brief Reset VAD calibration
 */
void vad_reset_calibration(void);

/**
 * @brief Set VAD threshold (for NVS persistence)
 *
 * @param threshold New threshold value
 */
void vad_set_threshold(float threshold);

/**
 * @brief Get current VAD threshold
 *
 * @return Current threshold
 */
float vad_get_threshold(void);

#ifdef __cplusplus
}
#endif

#endif // VAD_H
