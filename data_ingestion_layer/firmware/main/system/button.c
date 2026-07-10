// button.c — debounced gesture classifier for the user button.
#include "system/button.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "button";

#define POLL_MS        10
#define DEBOUNCE_MS    30
#define LONG_MS        5000
#define DOUBLE_GAP_MS  400

typedef struct {
    int gpio;
    button_cb_t cb;
    void *user;
} button_ctx_t;

static void button_task(void *arg) {
    button_ctx_t ctx = *(button_ctx_t *)arg;
    free(arg);

    gpio_config_t io = {
        .pin_bit_mask = 1ULL << ctx.gpio,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,   // BOOT is active-low
    };
    gpio_config(&io);

    int held_ms = 0;            // how long the button has been down
    int gap_ms = -1;            // ms since last release (-1 = no pending short press)
    bool long_fired = false;

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
        bool down = gpio_get_level(ctx.gpio) == 0;

        if (down) {
            held_ms += POLL_MS;
            if (held_ms >= LONG_MS && !long_fired) {
                long_fired = true;
                gap_ms = -1;                       // cancel any pending short
                ESP_LOGW(TAG, "long press");
                ctx.cb(BUTTON_EVENT_LONG, ctx.user);
            }
            continue;
        }

        // released
        if (held_ms >= DEBOUNCE_MS && !long_fired) {
            if (gap_ms >= 0) {                     // second press inside the double window
                gap_ms = -1;
                ESP_LOGI(TAG, "double press");
                ctx.cb(BUTTON_EVENT_DOUBLE, ctx.user);
            } else {
                gap_ms = 0;                        // start the double-press window
            }
        }
        held_ms = 0;
        long_fired = false;

        if (gap_ms >= 0) {
            gap_ms += POLL_MS;
            if (gap_ms > DOUBLE_GAP_MS) {          // window expired -> it was a short press
                gap_ms = -1;
                ESP_LOGI(TAG, "short press");
                ctx.cb(BUTTON_EVENT_SHORT, ctx.user);
            }
        }
    }
}

void button_start(int gpio, button_cb_t cb, void *user) {
    button_ctx_t *ctx = malloc(sizeof(button_ctx_t));
    ctx->gpio = gpio >= 0 ? gpio : 0;   // default: GPIO0 / BOOT
    ctx->cb = cb;
    ctx->user = user;
    xTaskCreate(button_task, "button", 3072, ctx, 6, NULL);
}
