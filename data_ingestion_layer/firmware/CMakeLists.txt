# IHearYou Unified Firmware
# Supports: ReSpeaker Lite (XU316) and ReSpeaker XVF3800
# ESP-IDF 5.x Compatible

cmake_minimum_required(VERSION 3.16)

# Board type selection via environment variable
if(DEFINED ENV{BOARD_TYPE})
    set(BOARD_TYPE $ENV{BOARD_TYPE})
else()
    set(BOARD_TYPE "lite")
endif()

message(STATUS "Building for board type: ${BOARD_TYPE}")

# Include board-specific sdkconfig defaults
if(BOARD_TYPE STREQUAL "xvf3800")
    set(SDKCONFIG_DEFAULTS
        "sdkconfig.defaults"
        "sdkconfig.defaults.xvf3800"
    )
    message(STATUS "Using XVF3800 configuration")
else()
    set(SDKCONFIG_DEFAULTS
        "sdkconfig.defaults"
        "sdkconfig.defaults.lite"
    )
    message(STATUS "Using ReSpeaker Lite configuration")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ihearyou_firmware)
