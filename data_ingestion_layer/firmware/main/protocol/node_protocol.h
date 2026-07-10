// node_protocol.h — edge capability/offload protocol (firmware side).
//
// Mirrors the server contracts:
//   framework/node_capabilities.py  (NodeCapabilities / NodeAssignment / OFFLOADABLE_FEATURES)
//   framework/payloads/AudioPayload.py (+ provided_features)
//   node_registry_service.py  (topics nodes/{id}/capabilities, nodes/{id}/config)
//
// Builds the JSON the node publishes and parses the assignment it receives (cJSON).
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define NP_FW_VERSION "ihearyou-fw/2.0.0"
#define NP_HARDWARE_XVF "esp32-s3+xvf3800"
#define NP_HARDWARE_LITE "esp32-s3"

// Transport modes (must match MODE_RAW/MODE_SEGMENTS/MODE_FEATURES server-side).
typedef enum { NP_MODE_RAW = 0, NP_MODE_SEGMENTS, NP_MODE_FEATURES } np_mode_t;

// The server's OFFLOADABLE_FEATURES allow-list. Advertise ONLY a subset the build computes;
// anything else is ignored by negotiate_assignment().
#define NP_FEAT_SNR "snr"
#define NP_FEAT_SPECTRAL_FLATNESS "spectral_flatness"
#define NP_FEAT_TEMPORAL_MODULATION "temporal_modulation"
#define NP_FEAT_SPECTRAL_MODULATION "spectral_modulation"
#define NP_MAX_FEATURES 8

// What this node can do (-> "provides" in the advertisement).
typedef struct {
    bool vad, aec, doa, beamforming, speaker_gate;
    const char *features[NP_MAX_FEATURES];  // names from NP_FEAT_* ; NULL-terminated
} np_provides_t;

typedef struct {
    char node_id[40];          // "respeaker-aabbccddeeff" (eFuse MAC)
    const char *firmware;      // NP_FW_VERSION
    const char *hardware;      // NP_HARDWARE_*
    int psram_mb;
    np_provides_t provides;
    int sample_rate;           // 16000
    int frame_ms;              // 20
    int max_payload_bytes;     // 8192
} np_capabilities_t;

// The assignment received on nodes/{id}/config.
typedef struct {
    np_mode_t mode;
    bool vad_gated;
    const char *features[NP_MAX_FEATURES];  // names; NULL-terminated (heap-owned copy)
    bool raw_on_uncertain;
    int report_interval_ms;
    bool valid;                // false until a config message was successfully parsed
} np_assignment_t;

// Per-chunk metadata + optional node-computed features for an AudioPayload.
typedef struct {
    int user_id;               // <=0 => omit (server recognizes)
    const char *board_id;      // == node_id
    const char *environment_name;
    const char *system_mode;   // "live"
    double timestamp;          // unix seconds
    int sample_rate;
    int16_t doa_azimuth;       // from XVF3800; INT16_MIN => unknown
    // feature mode only: parallel arrays of name/value
    const char *feature_names[NP_MAX_FEATURES];
    float feature_values[NP_MAX_FEATURES];
    size_t feature_count;
} np_payload_meta_t;

// --- Identity ---------------------------------------------------------------
// Fills node_id with "respeaker-<mac12>" from the eFuse MAC. Returns bytes written.
size_t np_make_node_id(char *out, size_t out_len);

// --- Build (returns malloc'd JSON string; caller frees) ---------------------
// Advertisement for nodes/{id}/capabilities (retained).
char *np_build_capabilities_json(const np_capabilities_t *caps);
// AudioPayload for voice/{user}/{board}/{env}. For NP_MODE_FEATURES pass NULL audio_b64 and
// set meta->feature_*; for raw/segments pass the base64 audio and feature_count = 0.
char *np_build_audio_payload_json(const char *audio_b64, const np_payload_meta_t *meta);
// Heartbeat for nodes/{id}/status (retained).
char *np_build_status_json(const char *node_id, np_mode_t mode, int rssi,
                           uint32_t uptime_s, uint32_t free_heap, int16_t last_doa,
                           bool muted);

// --- Parse ------------------------------------------------------------------
// Parse a nodes/{id}/config message into *out. Returns true on success; *out owns heap copies
// of feature names (free with np_assignment_free).
bool np_parse_assignment(const char *json, size_t len, np_assignment_t *out);
void np_assignment_free(np_assignment_t *a);

// Topic helpers (write into caller buffer). Return bytes written.
size_t np_topic_capabilities(const char *node_id, char *out, size_t n);  // nodes/{id}/capabilities
size_t np_topic_config(const char *node_id, char *out, size_t n);        // nodes/{id}/config
size_t np_topic_status(const char *node_id, char *out, size_t n);        // nodes/{id}/status
size_t np_topic_marker(const char *node_id, char *out, size_t n);        // nodes/{id}/marker
size_t np_topic_attest(const char *node_id, char *out, size_t n);        // nodes/{id}/attest
size_t np_topic_voice(const np_payload_meta_t *m, char *out, size_t n);  // voice/{user}/{board}/{env}

#ifdef __cplusplus
}
#endif
