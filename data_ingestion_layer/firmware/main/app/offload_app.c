// offload_app.c — plug-and-play boot state machine.
// See docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md. Wires provisioning -> wifi ->
// discovery -> mqtt -> negotiate -> stream, and applies live config.
//
// Zero-config chain (the clinic scenario): a factory-fresh node first tries the DEFAULT
// SITE network (CONFIG_DEFAULT_SITE_SSID — the SSID the central node's AP broadcasts, or
// a site-standard IoT SSID). If that network exists, the node needs NO per-device setup
// at all: power it on, it joins, mDNS-finds the sink, advertises itself, and shows up in
// the dashboard's Edge Nodes -> Pending list for one-click approval. Only when no default
// network is reachable does it fall back to the SoftAP captive portal.
#include "app/offload_app.h"
#include "net/discovery.h"
#include "system/button.h"
#include "net/mqtt_wrapper.h"
#include "transport/mqtt_sender.h"
#include "wifi_manager.h"        // existing STA manager
#include "board_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "esp_system.h"
#include <string.h>
#include <stdio.h>

static const char *TAG = "offload_app";

#ifndef CONFIG_DEFAULT_SITE_SSID
#define CONFIG_DEFAULT_SITE_SSID "IHearYou-Net"
#endif
#ifndef CONFIG_DEFAULT_SITE_PASS
#define CONFIG_DEFAULT_SITE_PASS "ihearyou-setup"
#endif
// Low-privilege bootstrap MQTT account: may ONLY publish nodes/{id}/capabilities|status
// and subscribe nodes/{id}/config|provision (broker ACL). Per-node credentials are minted
// by the server at dashboard approval and pushed on nodes/{id}/provision (retained); the
// node persists them and reconnects with its own identity. See EDGE_TRUST_MODEL.md.
#ifndef CONFIG_BOOTSTRAP_MQTT_USER
#define CONFIG_BOOTSTRAP_MQTT_USER "node-bootstrap"
#endif
#ifndef CONFIG_BOOTSTRAP_MQTT_PASS
#define CONFIG_BOOTSTRAP_MQTT_PASS ""
#endif

#ifndef CONFIG_BUTTON_GPIO
#define CONFIG_BUTTON_GPIO 0
#endif

#define WIFI_TRY_DEFAULT_TIMEOUT_MS 15000
#define STATUS_DEFAULT_INTERVAL_MS  30000

static bool s_sender_started;

void offload_app_build_capabilities(app_ctx_t *ctx) {
    np_capabilities_t *c = &ctx->caps;
    np_make_node_id(c->node_id, sizeof(c->node_id));
    strncpy(ctx->node_id, c->node_id, sizeof(ctx->node_id));
    c->firmware = NP_FW_VERSION;
#if BOARD_TYPE_XVF3800   // was '#if HAS_XVF3800' — an undefined macro, silently 0: the XVF advertised as a Lite
    c->hardware = NP_HARDWARE_XVF;
    c->provides.aec = true; c->provides.doa = true; c->provides.beamforming = true;
#else
    c->hardware = NP_HARDWARE_LITE;
#endif
    c->provides.vad = true;                  // energy VAD always available
    c->provides.speaker_gate = false;        // not yet (server recognizes)
    c->psram_mb = 8; c->sample_rate = 16000; c->frame_ms = 20; c->max_payload_bytes = 8192;
    // Advertise only the features this build actually computes (edge_features). Start
    // conservative; expand after on-device validation vs server extractors.
    int i = 0;
#ifdef CONFIG_EDGE_FEATURE_SNR
    c->provides.features[i++] = NP_FEAT_SNR;
#endif
#ifdef CONFIG_EDGE_FEATURE_SPECTRAL_FLATNESS
    c->provides.features[i++] = NP_FEAT_SPECTRAL_FLATNESS;
#endif
    c->provides.features[i] = NULL;
}

// --------------------------------------------------------------------------- mqtt in
void offload_app_on_mqtt(const char *topic, const char *data, size_t len, void *user) {
    app_ctx_t *ctx = (app_ctx_t *)user;
    char cfg_topic[64];
    np_topic_config(ctx->node_id, cfg_topic, sizeof(cfg_topic));
    if (strcmp(topic, cfg_topic) == 0) {
        np_assignment_free(&ctx->assignment);
        if (np_parse_assignment(data, len, &ctx->assignment)) {
            ctx->config_dirty = true;
            ESP_LOGI(TAG, "assignment: mode=%d vad_gated=%d", ctx->assignment.mode,
                     ctx->assignment.vad_gated);
        }
    }
    // TODO(P2, per-node creds): handle nodes/{id}/provision here -- parse the minted
    // mqtt_user/mqtt_pass, provisioning_save(), mqtt_client_stop(), state = APP_RECONNECT
    // so the node comes back under its own ACL'd identity.
}

// --------------------------------------------------------------------------- wifi
static bool wifi_join(const char *ssid, const char *pass, int timeout_ms) {
    wifi_manager_config_t wc = {0};
    strncpy(wc.ssid, ssid, sizeof(wc.ssid) - 1);
    strncpy(wc.password, pass, sizeof(wc.password) - 1);
    wc.max_retry_count = 3;
    wc.retry_interval_ms = 2000;
    if (wifi_manager_init(&wc) != ESP_OK || wifi_manager_start() != ESP_OK) return false;
    for (int waited = 0; waited < timeout_ms; waited += 250) {
        if (wifi_manager_is_connected()) return true;
        vTaskDelay(pdMS_TO_TICKS(250));
    }
    wifi_manager_stop();
    return false;
}

// --------------------------------------------------------------------------- connect
static bool connect_and_negotiate(app_ctx_t *ctx) {
    // DISCOVER_SINK: mDNS -> NVS broker -> Kconfig host.
    discovery_result_t sink;
    if (!discovery_find_sink(5000, ctx->prov.broker_host, ctx->prov.broker_port, &sink)) {
        ESP_LOGW(TAG, "no broker found");
        return false;
    }
    ESP_LOGI(TAG, "sink %s:%d (mdns=%d)", sink.host, sink.port, sink.from_mdns);

    // MQTT_CONN — per-node creds from NVS when provisioned, else the bootstrap account.
    mqtt_client_cfg_t mc = {0};
    strncpy(mc.host, sink.host, sizeof(mc.host) - 1);
    mc.port = sink.port; mc.tls = sink.tls;
    strncpy(mc.client_id, ctx->node_id, sizeof(mc.client_id) - 1);
    if (ctx->prov.mqtt_user[0]) {
        strncpy(mc.username, ctx->prov.mqtt_user, sizeof(mc.username) - 1);
        strncpy(mc.password, ctx->prov.mqtt_pass, sizeof(mc.password) - 1);
    } else {
        strncpy(mc.username, CONFIG_BOOTSTRAP_MQTT_USER, sizeof(mc.username) - 1);
        strncpy(mc.password, CONFIG_BOOTSTRAP_MQTT_PASS, sizeof(mc.password) - 1);
    }
    // LWT: broker marks us offline (retained) if we die uncleanly.
    np_topic_status(ctx->node_id, mc.lwt_topic, sizeof(mc.lwt_topic));
    snprintf(mc.lwt_payload, sizeof(mc.lwt_payload), "{\"node_id\":\"%s\",\"online\":false}",
             ctx->node_id);
    mc.on_message = offload_app_on_mqtt; mc.user = ctx;
    if (!mqtt_client_start(&mc)) return false;
    for (int i = 0; i < 50 && !mqtt_client_is_connected(); i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (!mqtt_client_is_connected()) { mqtt_client_stop(); return false; }

    // Remember the broker so the next boot skips straight past an empty mDNS window.
    if (sink.from_mdns && (strcmp(ctx->prov.broker_host, sink.host) != 0 ||
                           ctx->prov.broker_port != sink.port)) {
        strncpy(ctx->prov.broker_host, sink.host, sizeof(ctx->prov.broker_host) - 1);
        ctx->prov.broker_port = sink.port;
        provisioning_save(&ctx->prov);
    }

    // NEGOTIATE: subscribe config, publish capabilities (retained), wait for assignment.
    char t_cfg[64], t_cap[64];
    np_topic_config(ctx->node_id, t_cfg, sizeof(t_cfg));
    np_topic_capabilities(ctx->node_id, t_cap, sizeof(t_cap));
    mqtt_client_subscribe(t_cfg, 1);
    char *adv = np_build_capabilities_json(&ctx->caps);
    if (!adv) return false;
    mqtt_client_publish(t_cap, adv, strlen(adv), 1, /*retain=*/true);
    free(adv);
    for (int i = 0; i < 100 && !ctx->assignment.valid; i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (!ctx->assignment.valid) {
        // No registry answer yet: the node is likely UNAPPROVED. Stay connected and keep
        // waiting -- the retained capabilities advert sits in the broker, the dashboard
        // shows the node under Pending, and approval pushes the config at any time.
        ESP_LOGW(TAG, "no assignment yet; waiting for dashboard approval");
    }
    return true;  // connected; streaming starts once an assignment arrives
}

// --------------------------------------------------------------------------- status
static void publish_status(app_ctx_t *ctx) {
    char topic[64];
    np_topic_status(ctx->node_id, topic, sizeof(topic));
    char *json = np_build_status_json(
        ctx->node_id, ctx->assignment.valid ? ctx->assignment.mode : NP_MODE_SEGMENTS,
        wifi_manager_get_rssi(), (uint32_t)(esp_timer_get_time() / 1000000ULL),
        esp_get_free_heap_size(), ctx->latest_doa, ctx->muted);
    if (json) {
        mqtt_client_publish(topic, json, strlen(json), 1, /*retain=*/true);
        free(json);
    }
}

// --------------------------------------------------------------------------- button
// One button, three gestures (see system/button.h). All MQTT publishes are best-effort:
// gestures must work identically whether or not the broker is reachable.
static void on_button(button_event_t event, void *user) {
    app_ctx_t *ctx = (app_ctx_t *)user;
    char topic[64];
    char payload[128];
    switch (event) {
    case BUTTON_EVENT_SHORT:
        if (!ctx->assignment.valid) {
            // Unapproved node: short press = enrollment attestation (physical proof of
            // presence). The dashboard can require a fresh attest before Approve.
            np_topic_attest(ctx->node_id, topic, sizeof(topic));
            snprintf(payload, sizeof(payload),
                     "{\"node_id\":\"%s\",\"uptime_s\":%u}",
                     ctx->node_id, (unsigned)(esp_timer_get_time() / 1000000ULL));
            mqtt_client_publish(topic, payload, strlen(payload), 1, false);
            ESP_LOGI(TAG, "enrollment attestation published");
            break;
        }
        // Privacy mute toggle: capture keeps running, but nothing leaves the node.
        ctx->muted = !ctx->muted;
        ESP_LOGW(TAG, "privacy mute %s", ctx->muted ? "ON" : "OFF");
        publish_status(ctx);   // retained -> dashboard reflects it immediately
        break;
    case BUTTON_EVENT_DOUBLE:
        // Event marker: the participant flags "this moment" for ground-truth annotation.
        np_topic_marker(ctx->node_id, topic, sizeof(topic));
        snprintf(payload, sizeof(payload),
                 "{\"node_id\":\"%s\",\"uptime_s\":%u,\"muted\":%s}",
                 ctx->node_id, (unsigned)(esp_timer_get_time() / 1000000ULL),
                 ctx->muted ? "true" : "false");
        mqtt_client_publish(topic, payload, strlen(payload), 1, false);
        ESP_LOGI(TAG, "event marker published");
        break;
    case BUTTON_EVENT_LONG:
        ESP_LOGW(TAG, "factory reset: erasing provisioning");
        provisioning_erase();
        esp_restart();
        break;
    }
}

// --------------------------------------------------------------------------- task
static void app_task(void *arg) {
    app_ctx_t *ctx = (app_ctx_t *)arg;
    int64_t last_status_ms = 0;
    for (;;) {
        switch (ctx->state) {
        case APP_BOOT:
            if (provisioning_load(&ctx->prov)) { ctx->state = APP_WIFI_CONNECT; break; }
            // Factory-fresh: try the zero-config site network before bothering a human.
            ESP_LOGI(TAG, "unprovisioned; trying default site SSID '%s'", CONFIG_DEFAULT_SITE_SSID);
            if (wifi_join(CONFIG_DEFAULT_SITE_SSID, CONFIG_DEFAULT_SITE_PASS,
                          WIFI_TRY_DEFAULT_TIMEOUT_MS)) {
                strncpy(ctx->prov.wifi_ssid, CONFIG_DEFAULT_SITE_SSID, sizeof(ctx->prov.wifi_ssid) - 1);
                strncpy(ctx->prov.wifi_pass, CONFIG_DEFAULT_SITE_PASS, sizeof(ctx->prov.wifi_pass) - 1);
                strcpy(ctx->prov.environment, "unassigned");
                provisioning_save(&ctx->prov);
                ctx->state = APP_DISCOVER_SINK;
                break;
            }
            ctx->state = APP_PROVISIONING;
            break;
        case APP_PROVISIONING:
            ESP_LOGI(TAG, "entering provisioning portal");
            provisioning_run_portal(&ctx->prov, /*timeout_s=*/0);  // restarts on success
            break;
        case APP_WIFI_CONNECT:
            if (wifi_manager_is_connected()) { ctx->state = APP_DISCOVER_SINK; break; }
            if (wifi_join(ctx->prov.wifi_ssid, ctx->prov.wifi_pass, 20000)) {
                ctx->state = APP_DISCOVER_SINK;
            } else {
                ESP_LOGW(TAG, "cannot join '%s'; retrying", ctx->prov.wifi_ssid);
                vTaskDelay(pdMS_TO_TICKS(5000));
            }
            break;
        case APP_DISCOVER_SINK:  // DISCOVER_SINK + MQTT_CONN + NEGOTIATE
            ctx->state = connect_and_negotiate(ctx) ? APP_STREAMING : APP_RECONNECT;
            break;
        case APP_STREAMING: {
            if (!mqtt_client_is_connected()) { ctx->state = APP_RECONNECT; break; }
            if (!s_sender_started && ctx->assignment.valid) {
                s_sender_started = true;
                mqtt_sender_start(ctx);   // audio pipeline (i2s/vad) is already running
            }
            if (ctx->config_dirty) { ctx->config_dirty = false; /* mode read live by sender */ }
            int64_t now_ms = esp_timer_get_time() / 1000;
            int interval = ctx->assignment.valid && ctx->assignment.report_interval_ms > 0
                               ? ctx->assignment.report_interval_ms : STATUS_DEFAULT_INTERVAL_MS;
            if (now_ms - last_status_ms >= interval) {
                last_status_ms = now_ms;
                publish_status(ctx);
            }
            vTaskDelay(pdMS_TO_TICKS(100));
            break;
        }
        case APP_RECONNECT:
            ESP_LOGW(TAG, "reconnecting");
            mqtt_client_stop();
            vTaskDelay(pdMS_TO_TICKS(2000));
            ctx->state = wifi_manager_is_connected() ? APP_DISCOVER_SINK : APP_WIFI_CONNECT;
            break;
        default:
            vTaskDelay(pdMS_TO_TICKS(200));
        }
    }
}

void offload_app_start(app_ctx_t *ctx) {
    ctx->state = APP_BOOT;
    ctx->latest_doa = INT16_MIN;
    ctx->muted = false;
    offload_app_build_capabilities(ctx);
    button_start(CONFIG_BUTTON_GPIO, on_button, ctx);   // Usr/BUT_A (Kconfig): mute / marker / factory-reset
    xTaskCreatePinnedToCore(app_task, "offload_app", 6144, ctx, 9, NULL, 0);
}
