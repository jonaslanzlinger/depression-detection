/**
 * @file watchdog.h
 * @brief Watchdog Manager - Header
 *
 * Provides watchdog configuration, task registration, and recovery handling
 * for the IHearYou firmware.
 *
 * @copyright IHearYou Research Project
 */

#ifndef WATCHDOG_H
#define WATCHDOG_H

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifdef __cplusplus
extern "C" {
#endif

// =============================================================================
// Configuration
// =============================================================================

/**
 * @brief Watchdog timeout in seconds
 *
 * If a task doesn't feed the watchdog within this time, the system will reset.
 * Set to allow for network delays but catch stuck tasks.
 */
#define WATCHDOG_TIMEOUT_S      30

/**
 * @brief Idle task watchdog enable
 *
 * Enable watchdog for IDLE tasks to detect CPU starvation.
 */
#define WATCHDOG_IDLE_ENABLE    true

/**
 * @brief Maximum number of tasks that can register with watchdog
 */
#define WATCHDOG_MAX_TASKS      8

// =============================================================================
// Types
// =============================================================================

/**
 * @brief Watchdog task state
 */
typedef enum {
    WDT_TASK_STATE_RUNNING,     ///< Task is running normally
    WDT_TASK_STATE_BLOCKED,     ///< Task is blocked waiting
    WDT_TASK_STATE_SUSPENDED,   ///< Task is suspended
    WDT_TASK_STATE_CRITICAL,    ///< Task is in critical section
} wdt_task_state_t;

/**
 * @brief Watchdog task info structure
 */
typedef struct {
    TaskHandle_t handle;
    const char *name;
    wdt_task_state_t state;
    TickType_t last_feed;
    uint32_t timeout_count;
} wdt_task_info_t;

// =============================================================================
// Functions
// =============================================================================

/**
 * @brief Initialize the watchdog subsystem
 *
 * Configures the ESP32 task watchdog timer and sets up task tracking.
 *
 * @return ESP_OK on success
 */
esp_err_t watchdog_init(void);

/**
 * @brief Register current task with the watchdog
 *
 * The task must call watchdog_feed() periodically to prevent reset.
 *
 * @return ESP_OK on success, ESP_ERR_NO_MEM if max tasks reached
 */
esp_err_t watchdog_register_task(void);

/**
 * @brief Unregister current task from the watchdog
 *
 * @return ESP_OK on success
 */
esp_err_t watchdog_unregister_task(void);

/**
 * @brief Feed the watchdog for current task
 *
 * Must be called periodically from each registered task.
 */
void watchdog_feed(void);

/**
 * @brief Set task state (for debug/monitoring)
 *
 * @param state Current task state
 */
void watchdog_set_task_state(wdt_task_state_t state);

/**
 * @brief Enter critical section
 *
 * Marks task as being in a critical section where watchdog timeout
 * is expected (e.g., long network operation).
 */
void watchdog_enter_critical(void);

/**
 * @brief Exit critical section
 */
void watchdog_exit_critical(void);

/**
 * @brief Get watchdog statistics
 *
 * @param[out] tasks Array of task info structures
 * @param[in,out] count On input: max tasks to return, on output: actual count
 * @return ESP_OK on success
 */
esp_err_t watchdog_get_stats(wdt_task_info_t *tasks, size_t *count);

/**
 * @brief Trigger a controlled system restart
 *
 * Logs reason and performs clean shutdown before restart.
 *
 * @param reason Reason string for restart
 */
void watchdog_trigger_restart(const char *reason);

#ifdef __cplusplus
}
#endif

#endif // WATCHDOG_H
