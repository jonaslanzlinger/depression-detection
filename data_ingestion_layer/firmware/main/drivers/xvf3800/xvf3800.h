/**
 * @file xvf3800.h
 * @brief XMOS XVF3800 DSP Driver - Header
 *
 * Provides I2C control interface for the XVF3800 far-field voice processor.
 * Used to configure AGC, AEC, beamforming, de-reverb, and retrieve DoA.
 *
 * Reference: XMOS XVF3800 Datasheet and I2C Control Protocol
 *
 * @copyright IHearYou Research Project
 */

#ifndef XVF3800_H
#define XVF3800_H

#include "esp_err.h"
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

// =============================================================================
// Configuration
// =============================================================================

/**
 * @brief XVF3800 I2C address
 *
 * Default I2C address for XVF3800 (7-bit address)
 */
#define XVF3800_I2C_ADDR        0x2C

/**
 * @brief I2C communication timeout
 */
#define XVF3800_I2C_TIMEOUT_MS  100

/**
 * @brief Maximum firmware version string length
 */
#define XVF3800_VERSION_MAX_LEN 32

// =============================================================================
// Register Definitions (from XVF3800 datasheet)
// =============================================================================

// Control registers
#define XVF3800_REG_CONTROL         0x00
#define XVF3800_REG_STATUS          0x01
#define XVF3800_REG_VERSION         0x02

// AEC (Acoustic Echo Cancellation)
#define XVF3800_REG_AEC_ENABLE      0x10
#define XVF3800_REG_AEC_FILTER_LEN  0x11
#define XVF3800_REG_AEC_ADAPT_RATE  0x12

// AGC (Automatic Gain Control)
#define XVF3800_REG_AGC_ENABLE      0x20
#define XVF3800_REG_AGC_TARGET      0x21
#define XVF3800_REG_AGC_MAX_GAIN    0x22

// Noise Suppression
#define XVF3800_REG_NS_ENABLE       0x30
#define XVF3800_REG_NS_LEVEL        0x31

// De-reverberation
#define XVF3800_REG_DEREVERB_ENABLE 0x40
#define XVF3800_REG_DEREVERB_DECAY  0x41

// Beamforming
#define XVF3800_REG_BEAM_MODE       0x50
#define XVF3800_REG_BEAM_DIRECTION  0x51

// Direction of Arrival
#define XVF3800_REG_DOA_ENABLE      0x60
#define XVF3800_REG_DOA_AZIMUTH     0x61
#define XVF3800_REG_DOA_CONFIDENCE  0x62

// VAD
#define XVF3800_REG_VAD_ENABLE      0x70
#define XVF3800_REG_VAD_THRESHOLD   0x71
#define XVF3800_REG_VAD_STATUS      0x72

// =============================================================================
// Types
// =============================================================================

/**
 * @brief XVF3800 status register bits
 */
typedef struct {
    bool ready;             ///< DSP ready for commands
    bool voice_detected;    ///< VAD detected voice
    bool aec_active;        ///< AEC is actively cancelling
    bool error;             ///< Error condition
} xvf3800_status_t;

/**
 * @brief Beamforming mode
 */
typedef enum {
    XVF3800_BEAM_FIXED = 0,     ///< Fixed beam (forward-facing)
    XVF3800_BEAM_ADAPTIVE = 1,  ///< Adaptive beam (tracks speaker)
} xvf3800_beam_mode_t;

/**
 * @brief Direction of Arrival data
 */
typedef struct {
    int16_t azimuth_degrees;    ///< Azimuth angle (-180 to +180)
    uint8_t confidence;         ///< Confidence (0-100%)
    uint32_t timestamp;         ///< Measurement timestamp (ms)
} xvf3800_doa_t;

/**
 * @brief XVF3800 configuration structure
 */
typedef struct {
    bool agc_enabled;
    uint8_t agc_target_db;
    uint8_t agc_max_gain_db;

    bool ns_enabled;
    uint8_t ns_level;           ///< 0 = off, 1 = low, 2 = medium, 3 = high

    bool dereverb_enabled;
    uint16_t dereverb_decay;    ///< Decay time in ms (default 300 — does not fit uint8_t)

    xvf3800_beam_mode_t beam_mode;
    int16_t beam_direction;     ///< Fixed beam direction (degrees)

    bool doa_enabled;
} xvf3800_config_t;

/**
 * @brief Default configuration
 */
#define XVF3800_CONFIG_DEFAULT {     \
    .agc_enabled = false,            \
    .agc_target_db = 20,             \
    .agc_max_gain_db = 30,           \
    .ns_enabled = true,              \
    .ns_level = 2,                   \
    .dereverb_enabled = true,        \
    .dereverb_decay = 300,           \
    .beam_mode = XVF3800_BEAM_ADAPTIVE, \
    .beam_direction = 0,             \
    .doa_enabled = true,             \
}

// =============================================================================
// Functions
// =============================================================================

/**
 * @brief Initialize XVF3800 driver
 *
 * Sets up I2C communication and verifies device presence.
 *
 * @param i2c_port I2C port number
 * @return ESP_OK on success
 */
esp_err_t xvf3800_init(int i2c_port);

/**
 * @brief Deinitialize XVF3800 driver
 *
 * @return ESP_OK on success
 */
esp_err_t xvf3800_deinit(void);

/**
 * @brief Check if XVF3800 is detected and ready
 *
 * @return true if device is ready
 */
bool xvf3800_is_ready(void);

/**
 * @brief Get device status
 *
 * @param[out] status Status structure
 * @return ESP_OK on success
 */
esp_err_t xvf3800_get_status(xvf3800_status_t *status);

/**
 * @brief Get firmware version
 *
 * @param[out] version Version string buffer
 * @param len Buffer length
 * @return ESP_OK on success
 */
esp_err_t xvf3800_get_version(char *version, size_t len);

/**
 * @brief Apply full configuration
 *
 * @param config Configuration structure
 * @return ESP_OK on success
 */
esp_err_t xvf3800_configure(const xvf3800_config_t *config);

/**
 * @brief Set AGC enabled state
 *
 * @param enabled true to enable AGC
 * @return ESP_OK on success
 */
esp_err_t xvf3800_set_agc_enabled(bool enabled);

/**
 * @brief Set noise suppression enabled state
 *
 * @param enabled true to enable NS
 * @return ESP_OK on success
 */
esp_err_t xvf3800_set_ns_enabled(bool enabled);

/**
 * @brief Set de-reverberation enabled state
 *
 * @param enabled true to enable de-reverb
 * @return ESP_OK on success
 */
esp_err_t xvf3800_enable_dereverb(bool enabled);

/**
 * @brief Set beamforming mode
 *
 * @param mode Beamforming mode
 * @return ESP_OK on success
 */
esp_err_t xvf3800_set_beam_mode(xvf3800_beam_mode_t mode);

/**
 * @brief Set fixed beam direction
 *
 * @param degrees Beam direction (-180 to +180 degrees)
 * @return ESP_OK on success
 */
esp_err_t xvf3800_set_beam_direction(int16_t degrees);

/**
 * @brief Get current Direction of Arrival
 *
 * @param[out] azimuth Azimuth angle in degrees
 * @param[out] confidence Confidence (0-100)
 * @return ESP_OK on success
 */
esp_err_t xvf3800_get_doa(int16_t *azimuth, uint8_t *confidence);

/**
 * @brief Get full DoA structure
 *
 * @param[out] doa DoA structure
 * @return ESP_OK on success
 */
esp_err_t xvf3800_get_doa_full(xvf3800_doa_t *doa);

/**
 * @brief Check if voice is currently detected
 *
 * Uses the XVF3800's built-in VAD.
 *
 * @return true if voice detected
 */
bool xvf3800_voice_detected(void);

/**
 * @brief Perform software reset of XVF3800
 *
 * @return ESP_OK on success
 */
esp_err_t xvf3800_reset(void);

#ifdef __cplusplus
}
#endif

#endif // XVF3800_H
