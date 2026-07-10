/**
 * @file audio_buffer.c
 * @brief Audio Ring Buffer with PSRAM support - Implementation
 *
 * @copyright IHearYou Research Project
 */

#include "audio_buffer.h"
#include "config/board_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/ringbuf.h"
#include "freertos/queue.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "AUDIO_BUF";

// =============================================================================
// Static Variables
// =============================================================================

// Raw audio ring buffer (I2S -> VAD)
static RingbufHandle_t s_raw_ringbuf = NULL;
static StaticRingbuffer_t *s_raw_ringbuf_struct = NULL;
static uint8_t *s_raw_ringbuf_storage = NULL;

// Speech chunk queue (VAD -> TCP sender)
typedef struct {
    uint8_t *data;
    size_t size;
    audio_quality_metrics_t metrics;
} speech_chunk_t;

static QueueHandle_t s_speech_queue = NULL;
#define SPEECH_QUEUE_LENGTH 4  // Buffer up to 4 chunks (20 seconds)

static uint32_t s_overflow_count = 0;
static bool s_initialized = false;

// =============================================================================
// Initialization
// =============================================================================

esp_err_t audio_buffer_init(void)
{
    if (s_initialized) {
        ESP_LOGW(TAG, "Audio buffer already initialized");
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Initializing audio buffers in PSRAM...");

    // Allocate ring buffer structure in PSRAM
    s_raw_ringbuf_struct = heap_caps_malloc(sizeof(StaticRingbuffer_t), MALLOC_CAP_SPIRAM);
    if (s_raw_ringbuf_struct == NULL) {
        ESP_LOGE(TAG, "Failed to allocate ring buffer struct");
        return ESP_ERR_NO_MEM;
    }

    // Allocate ring buffer storage in PSRAM
    s_raw_ringbuf_storage = heap_caps_malloc(RING_BUFFER_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_raw_ringbuf_storage == NULL) {
        ESP_LOGE(TAG, "Failed to allocate ring buffer storage");
        heap_caps_free(s_raw_ringbuf_struct);
        s_raw_ringbuf_struct = NULL;
        return ESP_ERR_NO_MEM;
    }

    // Create static ring buffer
    s_raw_ringbuf = xRingbufferCreateStatic(RING_BUFFER_SIZE, RINGBUF_TYPE_BYTEBUF,
                                              s_raw_ringbuf_storage, s_raw_ringbuf_struct);
    if (s_raw_ringbuf == NULL) {
        ESP_LOGE(TAG, "Failed to create ring buffer");
        heap_caps_free(s_raw_ringbuf_storage);
        heap_caps_free(s_raw_ringbuf_struct);
        s_raw_ringbuf_storage = NULL;
        s_raw_ringbuf_struct = NULL;
        return ESP_FAIL;
    }

    // Create speech chunk queue
    s_speech_queue = xQueueCreate(SPEECH_QUEUE_LENGTH, sizeof(speech_chunk_t));
    if (s_speech_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create speech queue");
        vRingbufferDelete(s_raw_ringbuf);
        heap_caps_free(s_raw_ringbuf_storage);
        heap_caps_free(s_raw_ringbuf_struct);
        s_raw_ringbuf = NULL;
        s_raw_ringbuf_storage = NULL;
        s_raw_ringbuf_struct = NULL;
        return ESP_FAIL;
    }

    s_initialized = true;
    s_overflow_count = 0;

    ESP_LOGI(TAG, "Audio buffers initialized:");
    ESP_LOGI(TAG, "  Ring buffer: %d KB in PSRAM", RING_BUFFER_SIZE / 1024);
    ESP_LOGI(TAG, "  Speech queue: %d chunks", SPEECH_QUEUE_LENGTH);

    return ESP_OK;
}

esp_err_t audio_buffer_deinit(void)
{
    if (!s_initialized) {
        return ESP_OK;
    }

    // Free any pending speech chunks
    speech_chunk_t chunk;
    while (xQueueReceive(s_speech_queue, &chunk, 0) == pdTRUE) {
        if (chunk.data != NULL) {
            heap_caps_free(chunk.data);
        }
    }
    vQueueDelete(s_speech_queue);
    s_speech_queue = NULL;

    // Free ring buffer
    vRingbufferDelete(s_raw_ringbuf);
    heap_caps_free(s_raw_ringbuf_storage);
    heap_caps_free(s_raw_ringbuf_struct);
    s_raw_ringbuf = NULL;
    s_raw_ringbuf_storage = NULL;
    s_raw_ringbuf_struct = NULL;

    s_initialized = false;
    ESP_LOGI(TAG, "Audio buffers deinitialized");

    return ESP_OK;
}

// =============================================================================
// Raw Audio Buffer Operations
// =============================================================================

esp_err_t audio_buffer_write(const int16_t *data, size_t size)
{
    if (!s_initialized || s_raw_ringbuf == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || size == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Check for high watermark
    size_t free_size = xRingbufferGetCurFreeSize(s_raw_ringbuf);
    if (free_size < RING_BUFFER_HIGH_WATERMARK) {
        ESP_LOGW(TAG, "Ring buffer high watermark reached");
    }

    // Try to send to ring buffer
    BaseType_t ret = xRingbufferSend(s_raw_ringbuf, data, size, pdMS_TO_TICKS(10));
    if (ret != pdTRUE) {
        s_overflow_count++;
        return ESP_ERR_NO_MEM;
    }

    return ESP_OK;
}

esp_err_t audio_buffer_read(int16_t *data, size_t size,
                             size_t *bytes_read, TickType_t timeout)
{
    if (!s_initialized || s_raw_ringbuf == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || bytes_read == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    size_t item_size = 0;
    void *item = xRingbufferReceive(s_raw_ringbuf, &item_size, timeout);

    if (item == NULL) {
        *bytes_read = 0;
        return ESP_ERR_TIMEOUT;
    }

    // Copy data (limit to requested size)
    size_t copy_size = (item_size < size) ? item_size : size;
    memcpy(data, item, copy_size);
    *bytes_read = copy_size;

    // Return item to ring buffer
    vRingbufferReturnItem(s_raw_ringbuf, item);

    return ESP_OK;
}

// =============================================================================
// Speech Chunk Queue Operations
// =============================================================================

esp_err_t audio_buffer_write_speech(const int16_t *data, size_t size,
                                      const audio_quality_metrics_t *metrics)
{
    if (!s_initialized || s_speech_queue == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || metrics == NULL || size == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Allocate chunk data in PSRAM
    uint8_t *chunk_data = heap_caps_malloc(size, MALLOC_CAP_SPIRAM);
    if (chunk_data == NULL) {
        ESP_LOGE(TAG, "Failed to allocate speech chunk");
        return ESP_ERR_NO_MEM;
    }

    // Copy data
    memcpy(chunk_data, data, size);

    // Create chunk descriptor
    speech_chunk_t chunk = {
        .data = chunk_data,
        .size = size,
        .metrics = *metrics
    };

    // Try to queue
    if (xQueueSend(s_speech_queue, &chunk, pdMS_TO_TICKS(10)) != pdTRUE) {
        ESP_LOGW(TAG, "Speech queue full - dropping chunk");
        heap_caps_free(chunk_data);
        return ESP_ERR_NO_MEM;
    }

    return ESP_OK;
}

esp_err_t audio_buffer_read_speech(uint8_t *data, size_t max_size,
                                     size_t *bytes_read,
                                     audio_quality_metrics_t *metrics,
                                     TickType_t timeout)
{
    if (!s_initialized || s_speech_queue == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (data == NULL || bytes_read == NULL || metrics == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    speech_chunk_t chunk;
    if (xQueueReceive(s_speech_queue, &chunk, timeout) != pdTRUE) {
        *bytes_read = 0;
        return ESP_ERR_TIMEOUT;
    }

    // Copy data (limit to max_size)
    size_t copy_size = (chunk.size < max_size) ? chunk.size : max_size;
    memcpy(data, chunk.data, copy_size);
    *bytes_read = copy_size;

    // Copy metrics
    *metrics = chunk.metrics;

    // Free chunk data
    heap_caps_free(chunk.data);

    return ESP_OK;
}

// =============================================================================
// Buffer Statistics
// =============================================================================

uint8_t audio_buffer_get_fill_percent(void)
{
    if (!s_initialized || s_raw_ringbuf == NULL) {
        return 0;
    }

    size_t free_size = xRingbufferGetCurFreeSize(s_raw_ringbuf);
    size_t used_size = RING_BUFFER_SIZE - free_size;

    return (uint8_t)((used_size * 100) / RING_BUFFER_SIZE);
}

bool audio_buffer_is_high_watermark(void)
{
    if (!s_initialized || s_raw_ringbuf == NULL) {
        return false;
    }

    size_t free_size = xRingbufferGetCurFreeSize(s_raw_ringbuf);
    return free_size < (RING_BUFFER_SIZE - RING_BUFFER_HIGH_WATERMARK);
}

void audio_buffer_get_stats(size_t *total_size, size_t *used_size,
                             uint32_t *overflow_count)
{
    if (total_size != NULL) {
        *total_size = RING_BUFFER_SIZE;
    }

    if (used_size != NULL) {
        if (s_initialized && s_raw_ringbuf != NULL) {
            size_t free_size = xRingbufferGetCurFreeSize(s_raw_ringbuf);
            *used_size = RING_BUFFER_SIZE - free_size;
        } else {
            *used_size = 0;
        }
    }

    if (overflow_count != NULL) {
        *overflow_count = s_overflow_count;
    }
}
