/*
 * xvf3800_driver.h
 *
 *  Created on: 15 Jul 2024
 *      Author: a.g.meyer
 */

#ifndef XVF3800_DRIVER_H_
#define XVF3800_DRIVER_H_

#include <stdint.h>
#include <stdbool.h>

// XVF3800 Configuration Modes
typedef enum {
    XVF_MODE_NEARFIELD,
    XVF_MODE_FARFIELD,
    XVF_MODE_KEYWORD
} xvf_mode_t;

/**
 * @brief Initializes the XVF3800 device.
 *
 * @param mode The desired operational mode.
 * @return 0 on success, -1 on failure.
 */
int xvf_init(xvf_mode_t mode);

/**
 * @brief Reads a single frame of audio data.
 *
 * @param buffer Pointer to the buffer to store the audio data.
 * @param size The size of the buffer.
 * @return Number of bytes read, or -1 on failure.
 */
int xvf_read_frame(int16_t *buffer, uint32_t size);

/**
 * @brief Sets the gain of the microphone input.
 *
 * @param gain The desired gain level.
 * @return 0 on success, -1 on failure.
 */
int xvf_set_gain(uint8_t gain);

/**
 * @brief Gets the Voice Activity Detection (VAD) status.
 *
 * @return true if voice is detected, false otherwise.
 */
bool xvf_get_vad_status(void);

#endif /* XVF3800_DRIVER_H_ */
