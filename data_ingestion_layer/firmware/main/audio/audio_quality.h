/**
 * @file audio_quality.h
 * @brief Audio Quality Metrics Calculation
 *
 * @copyright IHearYou Research Project
 */

#ifndef AUDIO_QUALITY_H
#define AUDIO_QUALITY_H

#include "esp_err.h"
#include "config/audio_config.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Calculate audio quality metrics for a chunk
 *
 * @param samples Audio samples (int16_t)
 * @param sample_count Number of samples
 * @param metrics Output metrics structure
 */
void audio_calculate_quality_metrics(const int16_t *samples, size_t sample_count,
                                       audio_quality_metrics_t *metrics);

/**
 * @brief Validate audio quality against thresholds
 *
 * @param metrics Metrics to validate
 * @return Quality status
 */
audio_quality_status_t audio_validate_quality(const audio_quality_metrics_t *metrics);

/**
 * @brief Get quality status as string
 *
 * @param status Quality status
 * @return Status string
 */
const char* audio_quality_status_to_string(audio_quality_status_t status);

#ifdef __cplusplus
}
#endif

#endif // AUDIO_QUALITY_H
