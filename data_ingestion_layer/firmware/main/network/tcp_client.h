/**
 * @file tcp_client.h
 * @brief TCP Client with MAC Handshake Protocol
 *
 * Compatible with respeaker_service.py
 *
 * @copyright IHearYou Research Project
 */

#ifndef TCP_CLIENT_H
#define TCP_CLIENT_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief TCP connection state
 */
typedef enum {
    TCP_STATE_DISCONNECTED,
    TCP_STATE_CONNECTING,
    TCP_STATE_HANDSHAKE,
    TCP_STATE_STREAMING,
    TCP_STATE_ERROR
} tcp_state_t;

/**
 * @brief TCP client configuration
 */
typedef struct {
    char server_host[64];
    uint16_t server_port;
    uint32_t connect_timeout_ms;
    uint32_t handshake_timeout_ms;
    uint32_t reconnect_delay_ms;
} tcp_client_config_t;

/**
 * @brief Initialize TCP client
 *
 * @param config Configuration
 * @return ESP_OK on success
 */
esp_err_t tcp_client_init(const tcp_client_config_t *config);

/**
 * @brief Connect to server and perform handshake
 *
 * Handshake protocol:
 * 1. Connect to server
 * 2. Send MAC address (17 bytes): "AA:BB:CC:DD:EE:FF"
 * 3. Wait for "READY\n" response
 *
 * @return ESP_OK on success
 */
esp_err_t tcp_client_connect(void);

/**
 * @brief Disconnect from server
 *
 * @return ESP_OK on success
 */
esp_err_t tcp_client_disconnect(void);

/**
 * @brief Send data to server
 *
 * @param data Data to send
 * @param len Data length
 * @return ESP_OK on success
 */
esp_err_t tcp_client_send(const uint8_t *data, size_t len);

/**
 * @brief Check if connected and streaming
 *
 * @return true if connected and ready to stream
 */
bool tcp_client_is_connected(void);

/**
 * @brief Get current connection state
 *
 * @return Current state
 */
tcp_state_t tcp_client_get_state(void);

#ifdef __cplusplus
}
#endif

#endif // TCP_CLIENT_H
