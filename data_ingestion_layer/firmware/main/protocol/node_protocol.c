// node_protocol.c — build/parse the edge protocol JSON (cJSON, bundled with ESP-IDF).
// Contracts mirror framework/node_capabilities.py + framework/payloads/AudioPayload.py.
#include "protocol/node_protocol.h"
#include <stdio.h>
#include <string.h>
#include "cJSON.h"
#include "esp_mac.h"

size_t np_make_node_id(char *out, size_t out_len) {
    uint8_t mac[6] = {0};
    esp_efuse_mac_get_default(mac);
    return snprintf(out, out_len, "respeaker-%02x%02x%02x%02x%02x%02x",
                    mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

char *np_build_capabilities_json(const np_capabilities_t *c) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "node_id", c->node_id);
    cJSON_AddStringToObject(root, "firmware", c->firmware);
    cJSON_AddStringToObject(root, "hardware", c->hardware);
    cJSON_AddNumberToObject(root, "psram_mb", c->psram_mb);
    cJSON *p = cJSON_AddObjectToObject(root, "provides");
    cJSON_AddBoolToObject(p, "vad", c->provides.vad);
    cJSON_AddBoolToObject(p, "aec", c->provides.aec);
    cJSON_AddBoolToObject(p, "doa", c->provides.doa);
    cJSON_AddBoolToObject(p, "beamforming", c->provides.beamforming);
    cJSON_AddBoolToObject(p, "speaker_gate", c->provides.speaker_gate);
    cJSON *feats = cJSON_AddArrayToObject(p, "features");
    for (int i = 0; i < NP_MAX_FEATURES && c->provides.features[i]; i++)
        cJSON_AddItemToArray(feats, cJSON_CreateString(c->provides.features[i]));
    cJSON_AddNumberToObject(root, "sample_rate", c->sample_rate);
    cJSON_AddNumberToObject(root, "frame_ms", c->frame_ms);
    cJSON_AddNumberToObject(root, "max_payload_bytes", c->max_payload_bytes);
    char *s = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return s;  // caller frees
}

char *np_build_audio_payload_json(const char *audio_b64, const np_payload_meta_t *m) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "type", "audio");
    cJSON_AddStringToObject(root, "data", audio_b64 ? audio_b64 : "");
    cJSON_AddNumberToObject(root, "timestamp", m->timestamp);
    cJSON_AddNumberToObject(root, "sample_rate", m->sample_rate);
    cJSON_AddStringToObject(root, "board_id", m->board_id);
    if (m->user_id > 0) cJSON_AddNumberToObject(root, "user_id", m->user_id);
    if (m->environment_name) cJSON_AddStringToObject(root, "environment_name", m->environment_name);
    if (m->system_mode) cJSON_AddStringToObject(root, "system_mode", m->system_mode);
    if (m->doa_azimuth != INT16_MIN) cJSON_AddNumberToObject(root, "doa_azimuth", m->doa_azimuth);
    if (m->feature_count) {
        cJSON *pf = cJSON_AddObjectToObject(root, "provided_features");
        for (size_t i = 0; i < m->feature_count; i++)
            cJSON_AddNumberToObject(pf, m->feature_names[i], m->feature_values[i]);
        cJSON_AddStringToObject(root, "node_capabilities_version", NP_FW_VERSION);
    }
    char *s = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return s;
}

char *np_build_status_json(const char *node_id, np_mode_t mode, int rssi,
                           uint32_t uptime_s, uint32_t free_heap, int16_t last_doa,
                           bool muted) {
    static const char *MODE_S[] = {"raw", "segments", "features"};
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "node_id", node_id);
    cJSON_AddStringToObject(root, "mode", MODE_S[mode]);
    cJSON_AddNumberToObject(root, "rssi", rssi);
    cJSON_AddNumberToObject(root, "uptime_s", uptime_s);
    cJSON_AddNumberToObject(root, "free_heap", free_heap);
    cJSON_AddBoolToObject(root, "online", true);
    cJSON_AddBoolToObject(root, "muted", muted);
    if (last_doa != INT16_MIN) cJSON_AddNumberToObject(root, "last_doa", last_doa);
    char *s = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return s;
}

bool np_parse_assignment(const char *json, size_t len, np_assignment_t *out) {
    memset(out, 0, sizeof(*out));
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (!root) return false;
    const cJSON *mode = cJSON_GetObjectItem(root, "mode");
    out->mode = NP_MODE_RAW;
    if (cJSON_IsString(mode)) {
        if (!strcmp(mode->valuestring, "features")) out->mode = NP_MODE_FEATURES;
        else if (!strcmp(mode->valuestring, "segments")) out->mode = NP_MODE_SEGMENTS;
    }
    out->vad_gated = cJSON_IsTrue(cJSON_GetObjectItem(root, "vad_gated"));
    out->raw_on_uncertain = cJSON_IsTrue(cJSON_GetObjectItem(root, "raw_on_uncertain"));
    const cJSON *ri = cJSON_GetObjectItem(root, "report_interval_ms");
    out->report_interval_ms = cJSON_IsNumber(ri) ? ri->valueint : 1000;
    const cJSON *feats = cJSON_GetObjectItem(root, "features");
    int i = 0;
    const cJSON *f;
    cJSON_ArrayForEach(f, feats) {
        if (i >= NP_MAX_FEATURES || !cJSON_IsString(f)) break;
        out->features[i++] = strdup(f->valuestring);  // freed by np_assignment_free
    }
    out->valid = true;
    cJSON_Delete(root);
    return true;
}

void np_assignment_free(np_assignment_t *a) {
    for (int i = 0; i < NP_MAX_FEATURES && a->features[i]; i++) {
        free((void *)a->features[i]);
        a->features[i] = NULL;
    }
}

size_t np_topic_capabilities(const char *id, char *o, size_t n) { return snprintf(o, n, "nodes/%s/capabilities", id); }
size_t np_topic_config(const char *id, char *o, size_t n)       { return snprintf(o, n, "nodes/%s/config", id); }
size_t np_topic_status(const char *id, char *o, size_t n)       { return snprintf(o, n, "nodes/%s/status", id); }
size_t np_topic_marker(const char *id, char *o, size_t n)       { return snprintf(o, n, "nodes/%s/marker", id); }
size_t np_topic_attest(const char *id, char *o, size_t n)       { return snprintf(o, n, "nodes/%s/attest", id); }
size_t np_topic_voice(const np_payload_meta_t *m, char *o, size_t n) {
    return snprintf(o, n, "voice/%d/%s/%s", m->user_id > 0 ? m->user_id : 0,
                    m->board_id, m->environment_name ? m->environment_name : "default");
}
