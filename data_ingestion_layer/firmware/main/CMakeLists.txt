# IHearYou Firmware - Main Component CMakeLists.txt
#
# This configures all source files for the main firmware component.

# Define source files based on board type
set(SRCS
    "main.c"
    "hal/hal_audio.c"
    "audio/audio_buffer.c"
    "audio/vad.c"
    "audio/audio_quality.c"
    "network/wifi_manager.c"
    "network/tcp_client.c"
    "system/watchdog.c"
    "system/button.c"
    # --- Plug-and-play edge-offload (see docs/firmware/PLUG_AND_PLAY_OFFLOAD_DESIGN.md) ---
    "app/offload_app.c"
    "provisioning/provisioning.c"
    "net/discovery.c"
    "net/mqtt_client.c"
    "protocol/node_protocol.c"
    "features/edge_features.c"
    "transport/mqtt_sender.c"
)

# Add XVF3800 driver for that board variant
if(CONFIG_BOARD_RESPEAKER_XVF3800)
    list(APPEND SRCS
        "drivers/xvf3800/xvf3800.c"
        "drivers/xvf3800/xvf3800_i2c.c"
    )
endif()

# Define include directories
set(INCLUDE_DIRS
    "."
    "config"
    "hal"
    "audio"
    "network"
    "system"
    "drivers"
    "app"
    "provisioning"
    "net"
    "protocol"
    "features"
    "transport"
)

# Register component with ESP-IDF build system
idf_component_register(
    SRCS ${SRCS}
    INCLUDE_DIRS ${INCLUDE_DIRS}
    REQUIRES
        driver
        esp_wifi
        esp_event
        nvs_flash
        lwip
        esp_netif
        esp_timer
        esp_psram
        esp_system
        # Plug-and-play edge-offload deps:
        mqtt                 # esp-mqtt (broker transport)
        mdns                 # sink discovery (_iotsensing-mqtt._tcp); managed component
                             # -> main/idf_component.yml pins espressif/mdns
        esp_http_server      # provisioning captive portal
        json                 # cJSON (protocol payloads)
        mbedtls              # base64 for segment payloads
        # esp-dsp is a managed component: add espressif/esp-dsp to idf_component.yml for
        # on-node feature extraction (features/edge_features.c).
)

# Add compiler warnings
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Werror -Wno-unused-function)
