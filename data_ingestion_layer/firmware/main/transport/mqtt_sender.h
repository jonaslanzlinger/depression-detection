// mqtt_sender.h — VAD-gated speech segments -> AudioPayload JSON -> voice/{user}/{node}/{env}.
//
// The offload counterpart of tcp_client: drains the same speech queue the legacy TCP
// sender reads (audio_buffer_read_speech) and publishes each utterance segment as one
// MQTT AudioPayload message, honoring the live assignment (ctx->assignment.mode).
// NP_MODE_FEATURES is a later phase: this sender publishes SEGMENTS; when the assignment
// says FEATURES it computes edge_features over the segment and publishes metrics only.
#pragma once
#include "app/offload_app.h"

#ifdef __cplusplus
extern "C" {
#endif

// Start the sender task (reads ctx->assignment / mqtt connection state live).
void mqtt_sender_start(app_ctx_t *ctx);

// Counters for telemetry/status.
typedef struct {
    uint32_t segments_published;
    uint32_t segments_dropped;      // not connected / mode==RAW-unsupported / overflow
    uint32_t publish_failures;
} mqtt_sender_stats_t;

void mqtt_sender_get_stats(mqtt_sender_stats_t *out);

#ifdef __cplusplus
}
#endif
