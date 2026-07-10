/**
 * @file audio_config.h
 * @brief Audio processing configuration for IHearYou firmware
 *
 * @copyright IHearYou Research Project
 */

#ifndef AUDIO_CONFIG_H
#define AUDIO_CONFIG_H

#include "board_config.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// =============================================================================
// Audio Processing Parameters
// =============================================================================

/**
 * @brief Soft-knee limiter configuration
 *
 * Used instead of hard clipping to preserve jitter/shimmer measurements
 */
typedef struct {
    float threshold;        // Threshold in sample units (default: 30000)
    float knee;             // Knee width (default: 4000)
    float ratio;            // Compression ratio above threshold (default: 0.1)
} soft_limiter_config_t;

#define SOFT_LIMITER_DEFAULT { \
    .threshold = 30000.0f, \
    .knee = 4000.0f, \
    .ratio = 0.1f \
}

/**
 * @brief DC blocker configuration
 *
 * High-pass filter to remove DC offset (~20Hz cutoff at 16kHz)
 */
typedef struct {
    float alpha;            // Filter coefficient (default: 0.995)
} dc_blocker_config_t;

#define DC_BLOCKER_DEFAULT { \
    .alpha = 0.995f \
}

/**
 * @brief Audio quality metrics thresholds
 */
typedef struct {
    float min_rms;              // Minimum acceptable RMS (default: 50)
    float max_dc_offset;        // Maximum acceptable DC offset (default: 500)
    float max_clipping_ratio;   // Maximum clipping ratio (default: 0.01 = 1%)
} quality_thresholds_t;

#define QUALITY_THRESHOLDS_DEFAULT { \
    .min_rms = 50.0f, \
    .max_dc_offset = 500.0f, \
    .max_clipping_ratio = 0.01f \
}

// =============================================================================
// Audio Quality Metrics Structure
// =============================================================================

/**
 * @brief Audio quality metrics for each chunk
 *
 * Calculated before transmission and included in metadata
 */
typedef struct {
    float rms;                  // Root Mean Square energy
    float peak_amplitude;       // Maximum absolute sample value
    float db_fs;                // Decibels relative to full scale
    float dynamic_range;        // 20*log10(peak/rms)
    float snr;                  // Signal-to-noise ratio (vs noise floor)
    uint32_t clipping_count;    // Samples at ±32767
    float zero_crossing_rate;   // For speech/noise discrimination
    float dc_offset;            // Mean value (should be ~0)
} audio_quality_metrics_t;

/**
 * @brief Audio quality status
 */
typedef enum {
    AUDIO_QUALITY_GOOD = 0,
    AUDIO_QUALITY_LOW_LEVEL,        // RMS below threshold
    AUDIO_QUALITY_CLIPPING,         // >1% samples clipped
    AUDIO_QUALITY_DC_OFFSET,        // Mean > threshold
    AUDIO_QUALITY_SILENCE,          // Extended silence detected
    AUDIO_QUALITY_NOISE_ONLY        // High ZCR, low energy
} audio_quality_status_t;

// =============================================================================
// VAD Configuration
// =============================================================================

/**
 * @brief VAD result types
 */
typedef enum {
    VAD_RESULT_SILENCE = 0,
    VAD_RESULT_SPEECH,
    VAD_RESULT_HANGOVER
} vad_result_t;

/**
 * @brief VAD state structure
 */
typedef struct {
    float threshold;            // Energy threshold for speech detection
    uint32_t hangover_ms;       // Time to continue after speech ends
    uint32_t last_speech_time;  // Timestamp of last detected speech (ms)
    bool is_streaming;          // Current streaming state
    float noise_floor;          // Adaptive noise floor estimate
    float noise_floor_alpha;    // Smoothing factor for noise floor
    uint32_t calibration_frames;// Frames used for calibration
    bool calibrated;            // Whether calibration is complete
} vad_state_t;

/**
 * @brief VAD configuration
 */
typedef struct {
    float initial_threshold;    // Starting threshold
    float threshold_multiplier; // Multiplier for noise floor
    uint32_t hangover_ms;       // Hangover time in ms
    float noise_floor_alpha;    // Noise floor adaptation rate
    uint32_t calibration_frames;// Frames needed for calibration
} vad_config_t;

#if BOARD_TYPE_LITE
    #define VAD_CONFIG_DEFAULT { \
        .initial_threshold = 200.0f, \
        .threshold_multiplier = 4.0f, \
        .hangover_ms = 500, \
        .noise_floor_alpha = 0.01f, \
        .calibration_frames = 100 \
    }
#else
    #define VAD_CONFIG_DEFAULT { \
        .initial_threshold = 80.0f, \
        .threshold_multiplier = 5.0f, \
        .hangover_ms = 500, \
        .noise_floor_alpha = 0.01f, \
        .calibration_frames = 100 \
    }
#endif

// =============================================================================
// XVF3800 DoA Metadata (if available)
// =============================================================================

#if HAS_DOA_DETECTION

/**
 * @brief Direction of Arrival metadata
 */
typedef struct {
    int16_t azimuth_degrees;    // -180 to +180
    uint8_t confidence;         // 0-100%
    bool voice_detected;        // XVF3800 VAD state
} doa_metadata_t;

#endif // HAS_DOA_DETECTION

// =============================================================================
// Audio Chunk Structure
// =============================================================================

/**
 * @brief Complete audio chunk with metadata
 */
typedef struct {
    int16_t* samples;                   // Audio data
    size_t sample_count;                // Number of samples
    uint32_t timestamp_ms;              // Capture timestamp
    audio_quality_metrics_t quality;    // Quality metrics
    audio_quality_status_t status;      // Quality status
    vad_result_t vad_result;            // VAD decision
#if HAS_DOA_DETECTION
    doa_metadata_t doa;                 // Direction of arrival
#endif
} audio_chunk_t;

#ifdef __cplusplus
}
#endif

#endif // AUDIO_CONFIG_H
