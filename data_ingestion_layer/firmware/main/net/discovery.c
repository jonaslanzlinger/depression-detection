// discovery.c — mDNS sink discovery with NVS/Kconfig fallback.
// SDK: managed component espressif/mdns (declared in main/idf_component.yml).
// Resolution order: mDNS (_iotsensing-mqtt._tcp, advertised by deploy/mdns on the server,
// PR #86) -> last-good broker from NVS -> compiled CONFIG_SERVER_HOST. The server IP is
// never baked into a deployment: move the node to a new site and it finds the new sink.
#include "net/discovery.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "mdns.h"

static const char *TAG = "discovery";
static bool s_mdns_ready;

static bool query_mdns(int timeout_ms, discovery_result_t *out) {
    if (!s_mdns_ready) {
        // mdns_init() is idempotent-ish but cheap to guard; hostname is set by the app.
        if (mdns_init() != ESP_OK) {
            ESP_LOGW(TAG, "mdns_init failed");
            return false;
        }
        s_mdns_ready = true;
    }

    mdns_result_t *results = NULL;
    esp_err_t err = mdns_query_ptr(DISCOVERY_SERVICE, DISCOVERY_PROTO, timeout_ms,
                                   /*max_results=*/10, &results);
    if (err != ESP_OK || results == NULL) {
        return false;
    }

    bool found = false;
    for (mdns_result_t *r = results; r && !found; r = r->next) {
        // Prefer a result that carries an IPv4 address; fall back to the instance hostname.
        for (mdns_ip_addr_t *a = r->addr; a; a = a->next) {
            if (a->addr.type == ESP_IPADDR_TYPE_V4) {
                esp_ip4addr_ntoa(&a->addr.u_addr.ip4, out->host, sizeof(out->host));
                found = true;
                break;
            }
        }
        if (!found && r->hostname && r->hostname[0]) {
            snprintf(out->host, sizeof(out->host), "%s.local", r->hostname);
            found = true;
        }
        if (found) {
            out->port = r->port > 0 ? r->port : 1883;
            out->tls = false;
            for (size_t i = 0; i < r->txt_count; i++) {
                if (strcmp(r->txt[i].key, "tls") == 0 && r->txt[i].value &&
                    strcmp(r->txt[i].value, "1") == 0) {
                    out->tls = true;
                }
            }
            out->from_mdns = true;
        }
    }
    mdns_query_results_free(results);
    return found;
}

bool discovery_find_sink(int timeout_ms, const char *fallback_host, int fallback_port,
                         discovery_result_t *out) {
    memset(out, 0, sizeof(*out));

    if (query_mdns(timeout_ms, out)) {
        ESP_LOGI(TAG, "mDNS sink %s:%d tls=%d", out->host, out->port, out->tls);
        return true;
    }

    // Fallback 1: last-good broker remembered from a previous successful session (NVS).
    if (fallback_host && fallback_host[0]) {
        strncpy(out->host, fallback_host, sizeof(out->host) - 1);
        out->port = fallback_port > 0 ? fallback_port : 1883;
        out->from_mdns = false;
        ESP_LOGW(TAG, "mDNS empty; using stored broker %s:%d", out->host, out->port);
        return true;
    }

    // Fallback 2: compile-time default (dev convenience only; deployments use mDNS).
#ifdef CONFIG_SERVER_HOST
    if (CONFIG_SERVER_HOST[0]) {
        strncpy(out->host, CONFIG_SERVER_HOST, sizeof(out->host) - 1);
        out->port = 1883;
        out->from_mdns = false;
        ESP_LOGW(TAG, "mDNS empty; using compiled broker %s:%d", out->host, out->port);
        return true;
    }
#endif
    return false;
}
