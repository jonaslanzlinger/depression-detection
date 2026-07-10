// button.h — user-button gestures on the node (BOOT/GPIO0 on both board variants).
//
// One physical button, three gestures:
//   short press  (<1 s)              -> privacy MUTE toggle (pause/resume capture)
//   double press (2 within 400 ms)   -> EVENT MARKER (participant flags "this moment")
//   long press   (>=5 s)             -> factory reset (wipe provisioning, reboot to portal)
// While the node is still unapproved, a short press doubles as an ENROLLMENT ATTESTATION
// (proof of physical presence) published to nodes/{id}/attest.
#pragma once
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BUTTON_EVENT_SHORT = 0,
    BUTTON_EVENT_DOUBLE,
    BUTTON_EVENT_LONG,
} button_event_t;

typedef void (*button_cb_t)(button_event_t event, void *user);

// Start the button task (10 ms poll, debounced). gpio < 0 uses the default (GPIO0/BOOT).
void button_start(int gpio, button_cb_t cb, void *user);

#ifdef __cplusplus
}
#endif
