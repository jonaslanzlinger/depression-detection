// provisioning.h — plug-and-play Wi-Fi (+ broker) provisioning with NVS persistence.
//
// First boot with no stored creds: bring up a SoftAP captive portal (or BLE) via ESP-IDF
// `wifi_provisioning`, collect Wi-Fi SSID/pass (+ optional MQTT user/pass, occupant id), and
// persist to NVS. Subsequent boots read straight from NVS -> no recompile per deployment.
#pragma once
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    char wifi_ssid[33];
    char wifi_pass[65];
    char mqtt_user[33];     // optional; "" => anonymous (broker may reject, see PR #81)
    char mqtt_pass[65];
    char broker_host[64];   // last-good broker; "" => use discovery (mDNS)
    int  broker_port;       // 0 => default 1883
    int  user_id;           // occupant bound at setup; <=0 => server-side recognition
    char environment[33];   // e.g. "livingroom"
} prov_config_t;

// Load creds from NVS. Returns true if a Wi-Fi SSID is present (i.e. already provisioned).
bool provisioning_load(prov_config_t *out);
// Persist creds to NVS (namespace "ihy_prov").
bool provisioning_save(const prov_config_t *cfg);
// Wipe stored creds (factory reset) -> next boot re-enters provisioning.
void provisioning_erase(void);

// Run the provisioning portal until creds are submitted (blocking, with timeout_s; 0 = forever).
// SoftAP SSID is "IHearYou-Setup-XXXX" (XXXX = last 2 MAC bytes). On success fills *out and
// also persists. Returns true if provisioned.
bool provisioning_run_portal(prov_config_t *out, int timeout_s);

// Long-press handler: call from a GPIO0 ISR/task; >=5s held -> provisioning_erase()+reboot.
void provisioning_check_factory_reset(void);

#ifdef __cplusplus
}
#endif
