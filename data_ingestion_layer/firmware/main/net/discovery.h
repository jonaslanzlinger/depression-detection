// discovery.h — find the backend MQTT sink on the LAN so the server IP is never compiled in.
//
// Resolution order: mDNS (_iotsensing-mqtt._tcp) -> last-good broker in NVS -> compiled
// CONFIG_SERVER_HOST. Makes the node plug-and-play across sites.
#pragma once
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DISCOVERY_SERVICE "_iotsensing-mqtt"
#define DISCOVERY_PROTO   "_tcp"

typedef struct {
    char host[64];   // resolved broker IP/hostname
    int  port;       // 1883 (or 8883 if tls)
    bool tls;        // from mDNS TXT "tls=1"
    bool from_mdns;  // false => came from NVS/Kconfig fallback
} discovery_result_t;

// One-shot discovery with timeout. fallback_host/port used if mDNS yields nothing
// (pass the NVS broker_host, else "" to fall through to Kconfig). Returns true if a usable
// broker was resolved (mDNS or fallback).
bool discovery_find_sink(int timeout_ms, const char *fallback_host, int fallback_port,
                         discovery_result_t *out);

#ifdef __cplusplus
}
#endif
