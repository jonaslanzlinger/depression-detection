// provisioning.c — SoftAP captive-portal Wi-Fi provisioning + NVS persistence.
//
// UX (no app install, any phone): the unprovisioned node broadcasts the open AP
// "IHearYou-Setup-XXXX". Joining it pops the OS captive-portal sheet (a micro-DNS server
// answers every A query with 192.168.4.1), which shows a single form: Wi-Fi SSID +
// password (+ optional room name). Submit -> creds persist to NVS -> reboot -> the node
// joins the site network, mDNS-discovers the sink, and streams. MQTT credentials are NOT
// collected here: the node bootstraps with the low-privilege enrollment account and the
// server pushes per-node credentials after dashboard approval (see EDGE_TRUST_MODEL.md).
//
// SDK: esp_wifi (AP mode), esp_http_server, lwip raw UDP for DNS, nvs_flash.
#include "provisioning/provisioning.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_mac.h"
#include "esp_http_server.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "lwip/sockets.h"

static const char *TAG = "prov";
static const char *NS = "ihy_prov";

// ---------------------------------------------------------------------------- NVS
bool provisioning_load(prov_config_t *out) {
    memset(out, 0, sizeof(*out));
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) return false;
    size_t n = sizeof(out->wifi_ssid);
    bool ok = nvs_get_str(h, "ssid", out->wifi_ssid, &n) == ESP_OK && out->wifi_ssid[0];
    if (ok) {
        n = sizeof(out->wifi_pass);  nvs_get_str(h, "pass", out->wifi_pass, &n);
        n = sizeof(out->mqtt_user);  nvs_get_str(h, "muser", out->mqtt_user, &n);
        n = sizeof(out->mqtt_pass);  nvs_get_str(h, "mpass", out->mqtt_pass, &n);
        n = sizeof(out->broker_host); nvs_get_str(h, "broker", out->broker_host, &n);
        int32_t v = 0;
        if (nvs_get_i32(h, "bport", &v) == ESP_OK) out->broker_port = v;
        if (nvs_get_i32(h, "uid", &v) == ESP_OK)   out->user_id = v;
        n = sizeof(out->environment); nvs_get_str(h, "env", out->environment, &n);
    }
    nvs_close(h);
    return ok;
}

bool provisioning_save(const prov_config_t *c) {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) != ESP_OK) return false;
    nvs_set_str(h, "ssid", c->wifi_ssid);   nvs_set_str(h, "pass", c->wifi_pass);
    nvs_set_str(h, "muser", c->mqtt_user);  nvs_set_str(h, "mpass", c->mqtt_pass);
    nvs_set_str(h, "broker", c->broker_host); nvs_set_i32(h, "bport", c->broker_port);
    nvs_set_i32(h, "uid", c->user_id);      nvs_set_str(h, "env", c->environment);
    bool ok = nvs_commit(h) == ESP_OK;
    nvs_close(h);
    return ok;
}

void provisioning_erase(void) {
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READWRITE, &h) == ESP_OK) { nvs_erase_all(h); nvs_commit(h); nvs_close(h); }
}

// ---------------------------------------------------------------------------- micro-DNS
// Captive-portal detection: answer EVERY DNS A query with the SoftAP gateway (192.168.4.1).
// Phones probe a known URL on join; hijacked DNS + HTTP 302 pops the portal sheet.
static void dns_hijack_task(void *arg) {
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    struct sockaddr_in addr = {
        .sin_family = AF_INET, .sin_port = htons(53), .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (sock < 0 || bind(sock, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        ESP_LOGE(TAG, "dns bind failed");
        vTaskDelete(NULL);
        return;
    }
    uint8_t buf[512];
    for (;;) {
        struct sockaddr_in src;
        socklen_t slen = sizeof(src);
        int len = recvfrom(sock, buf, sizeof(buf), 0, (struct sockaddr *)&src, &slen);
        if (len < 12) continue;
        // Minimal DNS response: copy the query, set QR|AA flags, ANCOUNT=1, append one
        // A record pointing at 192.168.4.1 via a name pointer to the question (0xC00C).
        buf[2] = 0x84; buf[3] = 0x00;          // QR=1, AA=1, RCODE=0
        buf[6] = 0x00; buf[7] = 0x01;          // ANCOUNT = 1
        buf[8] = buf[9] = buf[10] = buf[11] = 0;  // NSCOUNT/ARCOUNT = 0
        static const uint8_t answer[] = {
            0xC0, 0x0C,             // name: pointer to offset 12 (the question)
            0x00, 0x01, 0x00, 0x01, // TYPE A, CLASS IN
            0x00, 0x00, 0x00, 0x3C, // TTL 60s
            0x00, 0x04,             // RDLENGTH 4
            192, 168, 4, 1,         // RDATA: the SoftAP gateway
        };
        if (len + (int)sizeof(answer) <= (int)sizeof(buf)) {
            memcpy(buf + len, answer, sizeof(answer));
            sendto(sock, buf, len + sizeof(answer), 0, (struct sockaddr *)&src, slen);
        }
    }
}

// ---------------------------------------------------------------------------- portal HTTP
static prov_config_t *s_pending;
static EventGroupHandle_t s_events;
#define PROV_DONE_BIT BIT0

static const char PORTAL_HTML[] =
    "<!doctype html><html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>IHearYou Setup</title><style>body{font-family:sans-serif;max-width:22rem;margin:2rem auto;padding:0 1rem}"
    "input,button{width:100%;padding:.6rem;margin:.3rem 0;box-sizing:border-box}button{background:#2563eb;color:#fff;border:0;border-radius:4px}</style>"
    "</head><body><h2>IHearYou node setup</h2>"
    "<p>Connect this sensor to your Wi-Fi. It will find the IHearYou server on the network automatically.</p>"
    "<form method=POST action=/save>"
    "<input name=ssid placeholder='Wi-Fi network name' required maxlength=32>"
    "<input name=pass type=password placeholder='Wi-Fi password' maxlength=64>"
    "<input name=env placeholder='Room (e.g. livingroom)' maxlength=32>"
    "<button type=submit>Save &amp; connect</button></form></body></html>";

static const char DONE_HTML[] =
    "<!doctype html><html><body style='font-family:sans-serif;text-align:center;margin-top:3rem'>"
    "<h2>&#10003; Saved</h2><p>The node reboots and joins your network now.<br>"
    "Approve it in the IHearYou dashboard (Edge Nodes &rarr; Pending).</p></body></html>";

// Tiny x-www-form-urlencoded extractor (values are SSIDs/passwords, no '+ '&' edge magic
// beyond %XX and '+').
static void form_get(const char *body, const char *key, char *out, size_t out_len) {
    out[0] = '\0';
    char pat[24];
    snprintf(pat, sizeof(pat), "%s=", key);
    const char *p = strstr(body, pat);
    if (!p) return;
    p += strlen(pat);
    size_t i = 0;
    while (*p && *p != '&' && i < out_len - 1) {
        if (*p == '+') { out[i++] = ' '; p++; }
        else if (*p == '%' && p[1] && p[2]) {
            char hex[3] = { p[1], p[2], 0 };
            out[i++] = (char)strtol(hex, NULL, 16);
            p += 3;
        } else out[i++] = *p++;
    }
    out[i] = '\0';
}

static esp_err_t root_get(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, PORTAL_HTML, HTTPD_RESP_USE_STRLEN);
}

// Any unknown URL (the phone's connectivity probe) redirects to the portal -> OS shows it.
static esp_err_t redirect_handler(httpd_req_t *req, httpd_err_code_t err) {
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://192.168.4.1/");
    return httpd_resp_send(req, NULL, 0);
}

static esp_err_t save_post(httpd_req_t *req) {
    char body[512] = {0};
    int len = httpd_req_recv(req, body, sizeof(body) - 1);
    if (len <= 0) return httpd_resp_send_500(req);
    form_get(body, "ssid", s_pending->wifi_ssid, sizeof(s_pending->wifi_ssid));
    form_get(body, "pass", s_pending->wifi_pass, sizeof(s_pending->wifi_pass));
    form_get(body, "env", s_pending->environment, sizeof(s_pending->environment));
    if (!s_pending->environment[0]) strcpy(s_pending->environment, "unassigned");
    if (!s_pending->wifi_ssid[0]) return httpd_resp_send_500(req);
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, DONE_HTML, HTTPD_RESP_USE_STRLEN);
    vTaskDelay(pdMS_TO_TICKS(200));  // let the response flush before signaling
    xEventGroupSetBits(s_events, PROV_DONE_BIT);
    return ESP_OK;
}

// ---------------------------------------------------------------------------- portal
bool provisioning_run_portal(prov_config_t *out, int timeout_s) {
    s_pending = out;
    s_events = xEventGroupCreate();

    // SoftAP "IHearYou-Setup-XXXX" (XXXX = last 2 MAC bytes), open, channel 1.
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP);
    wifi_config_t ap = {0};
    snprintf((char *)ap.ap.ssid, sizeof(ap.ap.ssid), "IHearYou-Setup-%02X%02X", mac[4], mac[5]);
    ap.ap.ssid_len = strlen((char *)ap.ap.ssid);
    ap.ap.authmode = WIFI_AUTH_OPEN;
    ap.ap.max_connection = 2;

    esp_netif_create_default_wifi_ap();
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_LOGI(TAG, "portal AP up: %s", ap.ap.ssid);

    TaskHandle_t dns_task;
    xTaskCreate(dns_hijack_task, "prov_dns", 3072, NULL, 5, &dns_task);

    httpd_handle_t server = NULL;
    httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
    hc.max_uri_handlers = 4;
    ESP_ERROR_CHECK(httpd_start(&server, &hc));
    httpd_uri_t u_root = { .uri = "/", .method = HTTP_GET, .handler = root_get };
    httpd_uri_t u_save = { .uri = "/save", .method = HTTP_POST, .handler = save_post };
    httpd_register_uri_handler(server, &u_root);
    httpd_register_uri_handler(server, &u_save);
    httpd_register_err_handler(server, HTTPD_404_NOT_FOUND, redirect_handler);

    TickType_t wait = timeout_s > 0 ? pdMS_TO_TICKS((uint32_t)timeout_s * 1000) : portMAX_DELAY;
    EventBits_t bits = xEventGroupWaitBits(s_events, PROV_DONE_BIT, pdTRUE, pdTRUE, wait);
    bool ok = (bits & PROV_DONE_BIT) != 0;

    httpd_stop(server);
    vTaskDelete(dns_task);
    esp_wifi_stop();
    vEventGroupDelete(s_events);

    if (ok) {
        provisioning_save(out);
        ESP_LOGI(TAG, "provisioned for SSID '%s' (env '%s'); restarting",
                 out->wifi_ssid, out->environment);
        esp_restart();  // clean boot into STA mode with the fresh creds
    }
    return ok;
}

// ---------------------------------------------------------------------------- factory reset
// Poll BOOT (GPIO0): held >=5 s -> wipe provisioning + reboot into the portal.
#include "driver/gpio.h"
void provisioning_check_factory_reset(void) {
    static int held_ms;
    if (gpio_get_level(GPIO_NUM_0) == 0) {
        held_ms += 100;
        if (held_ms >= 5000) {
            ESP_LOGW(TAG, "factory reset: erasing provisioning");
            provisioning_erase();
            esp_restart();
        }
    } else {
        held_ms = 0;
    }
}
