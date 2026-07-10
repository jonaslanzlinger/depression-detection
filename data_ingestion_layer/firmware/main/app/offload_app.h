// offload_app.h — the plug-and-play boot state machine that ties everything together.
// See docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md §2.
#pragma once
#include "protocol/node_protocol.h"
#include "provisioning/provisioning.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    APP_BOOT = 0,
    APP_PROVISIONING,
    APP_WIFI_CONNECT,
    APP_DISCOVER_SINK,
    APP_MQTT_CONN,
    APP_NEGOTIATE,
    APP_STREAMING,
    APP_RECONNECT,
} app_state_t;

// Shared runtime state owned by the app task; read by the audio/publish tasks.
typedef struct {
    char node_id[40];
    prov_config_t prov;
    np_capabilities_t caps;     // what we advertise
    np_assignment_t assignment; // what the server told us to do (applied live)
    app_state_t state;
    volatile int16_t latest_doa;       // updated by dsp_ctrl (XVF only); INT16_MIN if unknown
    volatile bool config_dirty;        // set when a new nodes/{id}/config arrives
    volatile bool muted;               // privacy mute (button short-press); sender drops audio
} app_ctx_t;

// Build the capability advertisement from board feature flags + which features this build
// computes (board_config.h HAS_* + edge_features availability).
void offload_app_build_capabilities(app_ctx_t *ctx);

// Start the state-machine task. Pulls in wifi_manager, discovery, mqtt_client, node_protocol;
// drives provisioning/discovery/connect/negotiate and applies assignments. The audio pipeline
// (i2s/vad tasks) keeps running; the transport router consults ctx->assignment.mode.
void offload_app_start(app_ctx_t *ctx);

// MQTT message callback (config topic) -> parse assignment into ctx->assignment, set dirty.
void offload_app_on_mqtt(const char *topic, const char *data, size_t len, void *user);

#ifdef __cplusplus
}
#endif
