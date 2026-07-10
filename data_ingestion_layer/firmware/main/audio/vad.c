/**
 * @file vad.c
 * @brief Voice Activity Detection - Implementation
 *
 * Energy-based VAD with adaptive noise floor tracking
 * and per-board calibration support.
 *
 * @copyright IHearYou Research Project
 */

#include "vad.h"
#include "config/board_config.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <math.h>
#include <string.h>

static const char *TAG = "VAD";

// =============================================================================
// Static Variables
// =============================================================================

static vad_state_t s_vad_state = {0};
static vad_config_t s_vad_config = {0};
static bool s_initialized = false;

// =============================================================================
// Initialization
// =============================================================================

esp_err_t vad_init(const vad_config_t *config)
{
    if (config == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (s_initialized) {
        ESP_LOGW(TAG, "VAD already initialized");
        return ESP_OK;
    }

    // Copy configuration
    memcpy(&s_vad_config, config, sizeof(vad_config_t));

    // Initialize state
    memset(&s_vad_state, 0, sizeof(vad_state_t));
    s_vad_state.threshold = config->initial_threshold;
    s_vad_state.hangover_ms = config->hangover_ms;
    s_vad_state.noise_floor_alpha = config->noise_floor_alpha;
    s_vad_state.noise_floor = 0.0f;
    s_vad_state.calibration_frames = 0;
    s_vad_state.calibrated = false;
    s_vad_state.is_streaming = false;
    s_vad_state.last_speech_time = 0;

    s_initialized = true;

    ESP_LOGI(TAG, "VAD initialized:");
    ESP_LOGI(TAG, "  Initial threshold: %.1f", s_vad_state.threshold);
    ESP_LOGI(TAG, "  Hangover: %lu ms", s_vad_state.hangover_ms);
    ESP_LOGI(TAG, "  Noise floor alpha: %.4f", s_vad_state.noise_floor_alpha);

    return ESP_OK;
}

esp_err_t vad_deinit(void)
{
    s_initialized = false;
    memset(&s_vad_state, 0, sizeof(vad_state_t));
    ESP_LOGI(TAG, "VAD deinitialized");
    return ESP_OK;
}

// =============================================================================
// VAD Processing
// =============================================================================

static float calculate_frame_energy(const int16_t *samples, size_t sample_count)
{
    if (samples == NULL || sample_count == 0) {
        return 0.0f;
    }

    float energy_sum = 0.0f;
    for (size_t i = 0; i < sample_count; i++) {
        float sample = (float)samples[i];
        energy_sum += fabsf(sample);
    }

    return energy_sum / (float)sample_count;
}

vad_result_t vad_process(const int16_t *samples, size_t sample_count)
{
    if (!s_initialized) {
        return VAD_RESULT_SILENCE;
    }

    if (samples == NULL || sample_count == 0) {
        return VAD_RESULT_SILENCE;
    }

    // Calculate frame energy
    float energy = calculate_frame_energy(samples, sample_count);

    // Get current time
    uint32_t current_time_ms = (uint32_t)(esp_timer_get_time() / 1000);

    // Calibration phase: estimate noise floor
    if (!s_vad_state.calibrated) {
        // Update noise floor estimate
        if (s_vad_state.noise_floor == 0.0f) {
            s_vad_state.noise_floor = energy;
        } else {
            s_vad_state.noise_floor =
                s_vad_state.noise_floor * (1.0f - s_vad_state.noise_floor_alpha) +
                energy * s_vad_state.noise_floor_alpha;
        }

        s_vad_state.calibration_frames++;

        // Check if calibration complete
        if (s_vad_state.calibration_frames >= s_vad_config.calibration_frames) {
            // Set threshold based on noise floor
            s_vad_state.threshold = s_vad_state.noise_floor * s_vad_config.threshold_multiplier;

            // Clamp to reasonable range
            if (s_vad_state.threshold < 50.0f) {
                s_vad_state.threshold = 50.0f;
            } else if (s_vad_state.threshold > 500.0f) {
                s_vad_state.threshold = 500.0f;
            }

            s_vad_state.calibrated = true;
            ESP_LOGI(TAG, "VAD calibrated: noise_floor=%.1f, threshold=%.1f",
                     s_vad_state.noise_floor, s_vad_state.threshold);
        }

        // During calibration, assume silence
        return VAD_RESULT_SILENCE;
    }

    // Update noise floor during silence (slow adaptation)
    if (energy < s_vad_state.threshold * 0.5f) {
        s_vad_state.noise_floor =
            s_vad_state.noise_floor * (1.0f - s_vad_state.noise_floor_alpha * 0.1f) +
            energy * (s_vad_state.noise_floor_alpha * 0.1f);
    }

    // Speech detection
    if (energy > s_vad_state.threshold) {
        s_vad_state.last_speech_time = current_time_ms;
        s_vad_state.is_streaming = true;
        return VAD_RESULT_SPEECH;
    }

    // Check hangover period
    if (s_vad_state.is_streaming) {
        uint32_t time_since_speech = current_time_ms - s_vad_state.last_speech_time;
        if (time_since_speech < s_vad_state.hangover_ms) {
            return VAD_RESULT_HANGOVER;
        }
    }

    // Silence
    s_vad_state.is_streaming = false;
    return VAD_RESULT_SILENCE;
}

// =============================================================================
// State Access
// =============================================================================

const vad_state_t* vad_get_state(void)
{
    return &s_vad_state;
}

bool vad_is_calibrated(void)
{
    return s_vad_state.calibrated;
}

void vad_reset_calibration(void)
{
    s_vad_state.calibrated = false;
    s_vad_state.calibration_frames = 0;
    s_vad_state.noise_floor = 0.0f;
    s_vad_state.threshold = s_vad_config.initial_threshold;
    ESP_LOGI(TAG, "VAD calibration reset");
}

void vad_set_threshold(float threshold)
{
    if (threshold > 0.0f) {
        s_vad_state.threshold = threshold;
        ESP_LOGI(TAG, "VAD threshold set to %.1f", threshold);
    }
}

float vad_get_threshold(void)
{
    return s_vad_state.threshold;
}
