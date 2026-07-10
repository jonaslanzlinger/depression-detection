/**
 * @file tcp_client.c
 * @brief TCP Client - Implementation
 *
 * @copyright IHearYou Research Project
 */

#include "tcp_client.h"
#include "wifi_manager.h"
#include "config/board_config.h"
#include "esp_log.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include "lwip/netdb.h"
#include <string.h>

static const char *TAG = "TCP_CLIENT";

// =============================================================================
// Static Variables
// =============================================================================

static tcp_client_config_t s_config = {0};
static tcp_state_t s_state = TCP_STATE_DISCONNECTED;
static int s_socket = -1;
static bool s_initialized = false;

// =============================================================================
// Internal Functions
// =============================================================================

static esp_err_t tcp_perform_handshake(void)
{
    // Get MAC address
    char mac_str[18];
    esp_err_t ret = wifi_manager_get_mac(mac_str, sizeof(mac_str));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to get MAC address");
        return ret;
    }

    ESP_LOGI(TAG, "Sending handshake: %s", mac_str);

    // Send MAC address
    int sent = send(s_socket, mac_str, strlen(mac_str), 0);
    if (sent < 0) {
        ESP_LOGE(TAG, "Failed to send MAC: errno %d", errno);
        return ESP_FAIL;
    }

    // Wait for "READY\n" response
    char response[16] = {0};
    int received = 0;
    uint32_t start_time = xTaskGetTickCount() * portTICK_PERIOD_MS;

    while (received < sizeof(response) - 1) {
        // Check timeout
        uint32_t elapsed = (xTaskGetTickCount() * portTICK_PERIOD_MS) - start_time;
        if (elapsed > s_config.handshake_timeout_ms) {
            ESP_LOGE(TAG, "Handshake timeout");
            return ESP_ERR_TIMEOUT;
        }

        // Set socket timeout
        struct timeval timeout = {
            .tv_sec = 1,
            .tv_usec = 0
        };
        setsockopt(s_socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));

        int len = recv(s_socket, response + received, sizeof(response) - received - 1, 0);
        if (len < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                continue;  // Timeout, retry
            }
            ESP_LOGE(TAG, "Recv error: errno %d", errno);
            return ESP_FAIL;
        } else if (len == 0) {
            ESP_LOGE(TAG, "Connection closed during handshake");
            return ESP_FAIL;
        }

        received += len;

        // Check for READY
        if (strstr(response, "READY") != NULL) {
            ESP_LOGI(TAG, "Handshake successful!");
            return ESP_OK;
        }
    }

    ESP_LOGE(TAG, "Invalid handshake response: %s", response);
    return ESP_FAIL;
}

// =============================================================================
// Public Functions
// =============================================================================

esp_err_t tcp_client_init(const tcp_client_config_t *config)
{
    if (config == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (s_initialized) {
        ESP_LOGW(TAG, "TCP client already initialized");
        return ESP_OK;
    }

    memcpy(&s_config, config, sizeof(tcp_client_config_t));
    s_state = TCP_STATE_DISCONNECTED;
    s_socket = -1;
    s_initialized = true;

    ESP_LOGI(TAG, "TCP client initialized: %s:%d",
             s_config.server_host, s_config.server_port);

    return ESP_OK;
}

esp_err_t tcp_client_connect(void)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (s_state == TCP_STATE_STREAMING) {
        return ESP_OK;  // Already connected
    }

    // Close existing socket if any
    if (s_socket >= 0) {
        close(s_socket);
        s_socket = -1;
    }

    s_state = TCP_STATE_CONNECTING;

    // Resolve host
    struct addrinfo hints = {
        .ai_family = AF_INET,
        .ai_socktype = SOCK_STREAM,
    };
    struct addrinfo *res;
    char port_str[6];
    snprintf(port_str, sizeof(port_str), "%d", s_config.server_port);

    int err = getaddrinfo(s_config.server_host, port_str, &hints, &res);
    if (err != 0 || res == NULL) {
        ESP_LOGE(TAG, "DNS lookup failed: %d", err);
        s_state = TCP_STATE_ERROR;
        return ESP_FAIL;
    }

    // Create socket
    s_socket = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (s_socket < 0) {
        ESP_LOGE(TAG, "Failed to create socket: errno %d", errno);
        freeaddrinfo(res);
        s_state = TCP_STATE_ERROR;
        return ESP_FAIL;
    }

    // Set socket options
    int flag = 1;
    setsockopt(s_socket, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));

    // Set connect timeout
    struct timeval timeout = {
        .tv_sec = s_config.connect_timeout_ms / 1000,
        .tv_usec = (s_config.connect_timeout_ms % 1000) * 1000
    };
    setsockopt(s_socket, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    // Connect
    ESP_LOGI(TAG, "Connecting to %s:%d...", s_config.server_host, s_config.server_port);
    err = connect(s_socket, res->ai_addr, res->ai_addrlen);
    freeaddrinfo(res);

    if (err != 0) {
        ESP_LOGE(TAG, "Connect failed: errno %d", errno);
        close(s_socket);
        s_socket = -1;
        s_state = TCP_STATE_ERROR;
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Connected! Performing handshake...");
    s_state = TCP_STATE_HANDSHAKE;

    // Perform handshake
    esp_err_t ret = tcp_perform_handshake();
    if (ret != ESP_OK) {
        close(s_socket);
        s_socket = -1;
        s_state = TCP_STATE_ERROR;
        return ret;
    }

    s_state = TCP_STATE_STREAMING;
    return ESP_OK;
}

esp_err_t tcp_client_disconnect(void)
{
    if (s_socket >= 0) {
        close(s_socket);
        s_socket = -1;
    }
    s_state = TCP_STATE_DISCONNECTED;
    return ESP_OK;
}

esp_err_t tcp_client_send(const uint8_t *data, size_t len)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    if (s_state != TCP_STATE_STREAMING || s_socket < 0) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Send data
    size_t sent = 0;
    while (sent < len) {
        int ret = send(s_socket, data + sent, len - sent, 0);
        if (ret < 0) {
            ESP_LOGE(TAG, "Send failed: errno %d", errno);
            s_state = TCP_STATE_ERROR;
            return ESP_FAIL;
        }
        sent += ret;
    }

    return ESP_OK;
}

bool tcp_client_is_connected(void)
{
    return s_state == TCP_STATE_STREAMING && s_socket >= 0;
}

tcp_state_t tcp_client_get_state(void)
{
    return s_state;
}
