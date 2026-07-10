/**
 * @file watchdog.c
 * @brief Watchdog Manager - Implementation
 *
 * @copyright IHearYou Research Project
 */

#include "watchdog.h"
#include "esp_task_wdt.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <string.h>

static const char *TAG = "WATCHDOG";

// =============================================================================
// Static Variables
// =============================================================================

static bool s_initialized = false;
static SemaphoreHandle_t s_mutex = NULL;

// Task tracking
static wdt_task_info_t s_tasks[WATCHDOG_MAX_TASKS] = {0};
static size_t s_task_count = 0;

// =============================================================================
// Internal Functions
// =============================================================================

static int find_task_index(TaskHandle_t handle)
{
    for (size_t i = 0; i < s_task_count; i++) {
        if (s_tasks[i].handle == handle) {
            return (int)i;
        }
    }
    return -1;
}

// =============================================================================
// Public Functions
// =============================================================================

esp_err_t watchdog_init(void)
{
    if (s_initialized) {
        return ESP_OK;
    }

    // Create mutex for thread safety
    s_mutex = xSemaphoreCreateMutex();
    if (s_mutex == NULL) {
        ESP_LOGE(TAG, "Failed to create mutex");
        return ESP_ERR_NO_MEM;
    }

    // Configure task watchdog
    esp_task_wdt_config_t wdt_config = {
        .timeout_ms = WATCHDOG_TIMEOUT_S * 1000,
        .idle_core_mask = WATCHDOG_IDLE_ENABLE ? ((1 << portNUM_PROCESSORS) - 1) : 0,
        .trigger_panic = true,  // Reset on timeout
    };

    esp_err_t ret = esp_task_wdt_init(&wdt_config);
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        // ESP_ERR_INVALID_STATE means already initialized (by default config)
        ESP_LOGE(TAG, "Failed to init task WDT: %s", esp_err_to_name(ret));
        return ret;
    }

    // If already initialized, reconfigure
    if (ret == ESP_ERR_INVALID_STATE) {
        ESP_LOGW(TAG, "WDT already initialized, reconfiguring...");
        esp_task_wdt_deinit();
        ret = esp_task_wdt_init(&wdt_config);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to reinit task WDT: %s", esp_err_to_name(ret));
            return ret;
        }
    }

    s_initialized = true;
    ESP_LOGI(TAG, "Watchdog initialized: timeout=%ds, idle_wdt=%s",
             WATCHDOG_TIMEOUT_S, WATCHDOG_IDLE_ENABLE ? "on" : "off");

    return ESP_OK;
}

esp_err_t watchdog_register_task(void)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    TaskHandle_t handle = xTaskGetCurrentTaskHandle();

    xSemaphoreTake(s_mutex, portMAX_DELAY);

    // Check if already registered
    int idx = find_task_index(handle);
    if (idx >= 0) {
        xSemaphoreGive(s_mutex);
        return ESP_OK;  // Already registered
    }

    // Check capacity
    if (s_task_count >= WATCHDOG_MAX_TASKS) {
        xSemaphoreGive(s_mutex);
        ESP_LOGE(TAG, "Max tasks reached");
        return ESP_ERR_NO_MEM;
    }

    // Register with ESP task watchdog
    esp_err_t ret = esp_task_wdt_add(handle);
    if (ret != ESP_OK) {
        xSemaphoreGive(s_mutex);
        ESP_LOGE(TAG, "Failed to add task to WDT: %s", esp_err_to_name(ret));
        return ret;
    }

    // Add to our tracking
    s_tasks[s_task_count].handle = handle;
    s_tasks[s_task_count].name = pcTaskGetName(handle);
    s_tasks[s_task_count].state = WDT_TASK_STATE_RUNNING;
    s_tasks[s_task_count].last_feed = xTaskGetTickCount();
    s_tasks[s_task_count].timeout_count = 0;
    s_task_count++;

    xSemaphoreGive(s_mutex);

    ESP_LOGI(TAG, "Task '%s' registered with watchdog", pcTaskGetName(handle));
    return ESP_OK;
}

esp_err_t watchdog_unregister_task(void)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }

    TaskHandle_t handle = xTaskGetCurrentTaskHandle();

    xSemaphoreTake(s_mutex, portMAX_DELAY);

    int idx = find_task_index(handle);
    if (idx < 0) {
        xSemaphoreGive(s_mutex);
        return ESP_ERR_NOT_FOUND;
    }

    // Unregister from ESP task watchdog
    esp_err_t ret = esp_task_wdt_delete(handle);
    if (ret != ESP_OK) {
        xSemaphoreGive(s_mutex);
        ESP_LOGE(TAG, "Failed to remove task from WDT: %s", esp_err_to_name(ret));
        return ret;
    }

    // Remove from our tracking (shift remaining tasks)
    const char *name = s_tasks[idx].name;
    for (size_t i = idx; i < s_task_count - 1; i++) {
        s_tasks[i] = s_tasks[i + 1];
    }
    s_task_count--;

    xSemaphoreGive(s_mutex);

    ESP_LOGI(TAG, "Task '%s' unregistered from watchdog", name);
    return ESP_OK;
}

void watchdog_feed(void)
{
    if (!s_initialized) {
        return;
    }

    TaskHandle_t handle = xTaskGetCurrentTaskHandle();

    // Feed the hardware watchdog
    esp_task_wdt_reset();

    // Update tracking
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    int idx = find_task_index(handle);
    if (idx >= 0) {
        s_tasks[idx].last_feed = xTaskGetTickCount();
    }
    xSemaphoreGive(s_mutex);
}

void watchdog_set_task_state(wdt_task_state_t state)
{
    if (!s_initialized) {
        return;
    }

    TaskHandle_t handle = xTaskGetCurrentTaskHandle();

    xSemaphoreTake(s_mutex, portMAX_DELAY);
    int idx = find_task_index(handle);
    if (idx >= 0) {
        s_tasks[idx].state = state;
    }
    xSemaphoreGive(s_mutex);
}

void watchdog_enter_critical(void)
{
    watchdog_set_task_state(WDT_TASK_STATE_CRITICAL);
}

void watchdog_exit_critical(void)
{
    watchdog_set_task_state(WDT_TASK_STATE_RUNNING);
    watchdog_feed();  // Feed immediately after critical section
}

esp_err_t watchdog_get_stats(wdt_task_info_t *tasks, size_t *count)
{
    if (tasks == NULL || count == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    xSemaphoreTake(s_mutex, portMAX_DELAY);

    size_t copy_count = (*count < s_task_count) ? *count : s_task_count;
    memcpy(tasks, s_tasks, copy_count * sizeof(wdt_task_info_t));
    *count = copy_count;

    xSemaphoreGive(s_mutex);

    return ESP_OK;
}

void watchdog_trigger_restart(const char *reason)
{
    ESP_LOGE(TAG, "Triggering restart: %s", reason ? reason : "unknown");

    // Log task states
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    for (size_t i = 0; i < s_task_count; i++) {
        TickType_t now = xTaskGetTickCount();
        TickType_t age = now - s_tasks[i].last_feed;
        ESP_LOGW(TAG, "Task '%s': state=%d, last_feed=%lu ms ago",
                 s_tasks[i].name, s_tasks[i].state,
                 (unsigned long)(age * portTICK_PERIOD_MS));
    }
    xSemaphoreGive(s_mutex);

    // Short delay to allow logs to flush
    vTaskDelay(pdMS_TO_TICKS(100));

    // Trigger restart
    esp_restart();
}
