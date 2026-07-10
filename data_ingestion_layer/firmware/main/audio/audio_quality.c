/**
 * @file audio_quality.c
 * @brief Audio Quality Metrics - Implementation
 *
 * @copyright IHearYou Research Project
 */

#include "audio_quality.h"
#include "config/board_config.h"
#include <math.h>
#include <string.h>

// Quality thresholds
static const quality_thresholds_t s_thresholds = QUALITY_THRESHOLDS_DEFAULT;

void audio_calculate_quality_metrics(const int16_t *samples, size_t sample_count,
                                       audio_quality_metrics_t *metrics)
{
    if (samples == NULL || sample_count == 0 || metrics == NULL) {
        if (metrics != NULL) {
            memset(metrics, 0, sizeof(audio_quality_metrics_t));
        }
        return;
    }

    // Initialize accumulators
    double sum = 0.0;
    double sum_squared = 0.0;
    int16_t peak = 0;
    uint32_t clipping_count = 0;
    uint32_t zero_crossings = 0;
    int16_t prev_sample = 0;

    // Single pass through samples
    for (size_t i = 0; i < sample_count; i++) {
        int16_t sample = samples[i];
        float fsample = (float)sample;

        // Sum for mean (DC offset)
        sum += fsample;

        // Sum squared for RMS
        sum_squared += fsample * fsample;

        // Peak detection
        int16_t abs_sample = (sample < 0) ? -sample : sample;
        if (abs_sample > peak) {
            peak = abs_sample;
        }

        // Clipping detection
        if (sample == 32767 || sample == -32768) {
            clipping_count++;
        }

        // Zero crossing
        if (i > 0) {
            if ((prev_sample >= 0 && sample < 0) || (prev_sample < 0 && sample >= 0)) {
                zero_crossings++;
            }
        }
        prev_sample = sample;
    }

    // Calculate metrics
    double mean = sum / (double)sample_count;
    double mean_squared = sum_squared / (double)sample_count;
    double rms = sqrt(mean_squared);

    // Store results
    metrics->dc_offset = (float)mean;
    metrics->rms = (float)rms;
    metrics->peak_amplitude = (float)peak;
    metrics->clipping_count = clipping_count;
    metrics->zero_crossing_rate = (float)zero_crossings / (float)(sample_count - 1);

    // dBFS (decibels relative to full scale)
    // Full scale = 32767 for int16_t
    if (rms > 0) {
        metrics->db_fs = 20.0f * log10f((float)rms / 32767.0f);
    } else {
        metrics->db_fs = -120.0f;  // Effectively silence
    }

    // Dynamic range
    if (rms > 0 && peak > 0) {
        metrics->dynamic_range = 20.0f * log10f((float)peak / (float)rms);
    } else {
        metrics->dynamic_range = 0.0f;
    }

    // SNR estimation (simplified - assumes noise floor from quiet periods)
    // This is a standard S/N (Signal-to-Noise) ratio, where the configured
    // `s_thresholds.min_rms` value acts as a proxy for the noise floor.
    // This is a rough estimate; actual SNR requires noise floor tracking.
    if (rms > s_thresholds.min_rms) {
        metrics->snr = 20.0f * log10f((float)rms / s_thresholds.min_rms);
    } else {
        metrics->snr = 0.0f;
    }
}

audio_quality_status_t audio_validate_quality(const audio_quality_metrics_t *metrics)
{
    if (metrics == NULL) {
        return AUDIO_QUALITY_SILENCE;
    }

    // Check clipping (>1% samples clipped)
    // Note: We need sample count context, using clipping count > threshold
    if (metrics->clipping_count > 800) {  // ~1% of 80000 samples
        return AUDIO_QUALITY_CLIPPING;
    }

    // Check low level
    if (metrics->rms < s_thresholds.min_rms) {
        return AUDIO_QUALITY_LOW_LEVEL;
    }

    // Check DC offset
    if (fabsf(metrics->dc_offset) > s_thresholds.max_dc_offset) {
        return AUDIO_QUALITY_DC_OFFSET;
    }

    // Check for noise-only (high ZCR, low RMS)
    if (metrics->zero_crossing_rate > 0.5f && metrics->rms < 100.0f) {
        return AUDIO_QUALITY_NOISE_ONLY;
    }

    return AUDIO_QUALITY_GOOD;
}

const char* audio_quality_status_to_string(audio_quality_status_t status)
{
    switch (status) {
        case AUDIO_QUALITY_GOOD:       return "GOOD";
        case AUDIO_QUALITY_LOW_LEVEL:  return "LOW_LEVEL";
        case AUDIO_QUALITY_CLIPPING:   return "CLIPPING";
        case AUDIO_QUALITY_DC_OFFSET:  return "DC_OFFSET";
        case AUDIO_QUALITY_SILENCE:    return "SILENCE";
        case AUDIO_QUALITY_NOISE_ONLY: return "NOISE_ONLY";
        default:                       return "UNKNOWN";
    }
}
