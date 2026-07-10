// mqtt_client.c — thin esp-mqtt wrapper (auth, LWT, auto-reconnect, pub/sub).
// SDK: components/mqtt ("mqtt" in REQUIRES). The broker requires credentials (PR #81);
// per-node accounts are ACL-restricted to their own topics (PR #88).
#include "net/mqtt_wrapper.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "mqtt_client.h"  // esp-mqtt: local header renamed to mqtt_wrapper.h so this basename is unambiguous

static const char *TAG = "mqtt";
static esp_mqtt_client_handle_t s_client;
static volatile bool s_connected;
static mqtt_msg_cb_t s_cb;
static void *s_user;

// nodes/{id}/config messages are small (<1 KB) and arrive in a single MQTT_EVENT_DATA.
// Fragmented events (data_len < total_data_len) are logged and dropped rather than
// half-parsed; nothing in the offload protocol legitimately exceeds the in-buffer size.
static void event_handler(void *arg, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = event_data;
    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        s_connected = true;
        ESP_LOGI(TAG, "connected");
        break;
    case MQTT_EVENT_DISCONNECTED:
        s_connected = false;  // esp-mqtt keeps retrying on its own
        ESP_LOGW(TAG, "disconnected");
        break;
    case MQTT_EVENT_DATA:
        if (event->current_data_offset == 0 && event->data_len == event->total_data_len) {
            if (s_cb) {
                // topic is not NUL-terminated in the event; copy to a bounded buffer.
                char topic[80];
                int tl = event->topic_len < (int)sizeof(topic) - 1
                             ? event->topic_len : (int)sizeof(topic) - 1;
                memcpy(topic, event->topic, tl);
                topic[tl] = '\0';
                s_cb(topic, event->data, event->data_len, s_user);
            }
        } else {
            ESP_LOGW(TAG, "fragmented message dropped (%d/%d bytes)",
                     event->data_len, event->total_data_len);
        }
        break;
    case MQTT_EVENT_ERROR:
        if (event->error_handle &&
            event->error_handle->error_type == MQTT_ERROR_TYPE_CONNECTION_REFUSED) {
            ESP_LOGE(TAG, "broker refused connection (bad credentials / ACL?)");
        }
        break;
    default:
        break;
    }
}

bool mqtt_client_start(const mqtt_client_cfg_t *cfg) {
    s_cb = cfg->on_message;
    s_user = cfg->user;

    char uri[96];
    snprintf(uri, sizeof(uri), "%s://%s:%d", cfg->tls ? "mqtts" : "mqtt", cfg->host, cfg->port);
    ESP_LOGI(TAG, "connecting %s as %s", uri, cfg->client_id);

    esp_mqtt_client_config_t mc = {
        .broker.address.uri = uri,
        .credentials = {
            .username = cfg->username[0] ? cfg->username : NULL,
            .client_id = cfg->client_id,
            .authentication.password = cfg->password[0] ? cfg->password : NULL,
        },
        .session = {
            .keepalive = 30,
            .last_will = {
                .topic = cfg->lwt_topic[0] ? cfg->lwt_topic : NULL,
                .msg = cfg->lwt_payload,
                .msg_len = (int)strlen(cfg->lwt_payload),
                .qos = 1,
                .retain = true,
            },
        },
        .network.reconnect_timeout_ms = 5000,
        .buffer.size = 8192,          // inbound: config/assignment JSONs are small
        // Outbound must hold one full base64 segment (8 s => ~342 KB). With
        // CONFIG_SPIRAM_USE_MALLOC the allocation lands in PSRAM, not internal RAM.
        .buffer.out_size = 384 * 1024,
    };
    // TODO(TLS): when the broker gains TLS, pin the CA:
    //   mc.broker.verification.certificate = ca_pem;

    s_client = esp_mqtt_client_init(&mc);
    if (!s_client) return false;
    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, event_handler, NULL);
    return esp_mqtt_client_start(s_client) == ESP_OK;
}

bool mqtt_client_is_connected(void) { return s_connected; }

bool mqtt_client_publish(const char *topic, const char *payload, int len, int qos, bool retain) {
    if (!s_client) return false;
    return esp_mqtt_client_publish(s_client, topic, payload, len, qos, retain) >= 0;
}

bool mqtt_client_subscribe(const char *topic, int qos) {
    if (!s_client) return false;
    return esp_mqtt_client_subscribe(s_client, topic, qos) >= 0;
}

void mqtt_client_stop(void) {
    if (s_client) {
        esp_mqtt_client_stop(s_client);
        esp_mqtt_client_destroy(s_client);
        s_client = NULL;
    }
    s_connected = false;
}
