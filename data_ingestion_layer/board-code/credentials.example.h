// ================= WIFI CREDENTIALS =================
//
// SETUP INSTRUCTIONS:
// 1. Copy this file to 'credentials.h' in the same directory
// 2. Fill in your WiFi and server details below
// 3. DO NOT commit credentials.h to git (it's in .gitignore)
//
// =====================================================

#ifndef CREDENTIALS_H
#define CREDENTIALS_H

// Your WiFi network name
const char* ssid     = "YOUR_WIFI_SSID";

// Your WiFi password
const char* password = "YOUR_WIFI_PASSWORD";

// IP address of the machine running the respeaker_service container
// Find it with: hostname -I (Linux) or ipconfig (Windows)
const char* host     = "YOUR_SERVER_IP";

#endif // CREDENTIALS_H
