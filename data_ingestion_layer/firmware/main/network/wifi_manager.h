/**
 * @file wifi_manager.h
 * @brief WiFi Connection Manager
 *
 * @copyright IHearYou Research Project
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief WiFi connection state
 */
typedef enum {
    WIFI_STATE_DISCONNECTED,
    WIFI_STATE_CONNECTING,
    WIFI_STATE_CONNECTED,
    WIFI_STATE_RECONNECTING,
    WIFI_STATE_ERROR
} wifi_state_t;

/**
 * @brief WiFi manager configuration
 */
typedef struct {
    char ssid[32];
    char password[64];
    uint8_t max_retry_count;
    uint32_t retry_interval_ms;
} wifi_manager_config_t;

/**
 * @brief Initialize WiFi manager
 *
 * @param config Configuration
 * @return ESP_OK on success
 */
esp_err_t wifi_manager_init(const wifi_manager_config_t *config);

/**
 * @brief Start WiFi connection
 *
 * @return ESP_OK on success
 */
esp_err_t wifi_manager_start(void);

/**
 * @brief Stop WiFi and disconnect
 *
 * @return ESP_OK on success
 */
esp_err_t wifi_manager_stop(void);

/**
 * @brief Get current WiFi state
 *
 * @return Current state
 */
wifi_state_t wifi_manager_get_state(void);

/**
 * @brief Check if WiFi is connected
 *
 * @return true if connected
 */
bool wifi_manager_is_connected(void);

/**
 * @brief Get MAC address as string
 *
 * @param mac_str Buffer for MAC string (at least 18 bytes)
 * @param max_len Maximum length
 * @return ESP_OK on success
 */
esp_err_t wifi_manager_get_mac(char *mac_str, size_t max_len);

/**
 * @brief Get current RSSI
 *
 * @return RSSI in dBm, or 0 if not connected
 */
int8_t wifi_manager_get_rssi(void);

#ifdef __cplusplus
}
#endif

#endif // WIFI_MANAGER_H
