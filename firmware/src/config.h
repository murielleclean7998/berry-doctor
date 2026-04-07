#pragma once

#include <Arduino.h>

static constexpr char WIFI_SSID[] = "";
static constexpr char WIFI_PASSWORD[] = "";
static constexpr char MQTT_HOST[] = "192.168.0.10";
static constexpr uint16_t MQTT_PORT = 1883;
static constexpr uint8_t HOUSE_ID = 1;

static constexpr uint8_t PIN_RELAY_VENT = 12;
static constexpr uint8_t PIN_RELAY_CURTAIN = 13;
static constexpr uint8_t PIN_RELAY_LIGHT = 14;
static constexpr uint8_t PIN_RELAY_CO2 = 27;
static constexpr uint8_t PIN_PUMP_MAIN = 25;
static constexpr uint8_t PIN_PUMP_DRAIN = 26;
static constexpr uint8_t PIN_PUMP_A = 32;
static constexpr uint8_t PIN_PUMP_B = 33;
static constexpr uint8_t PIN_PIR_SENSOR = 2;
static constexpr uint8_t PIN_IR_LED = 16;
static constexpr uint8_t PIN_BUZZER = 17;

static constexpr unsigned long SENSOR_PUBLISH_INTERVAL_MS = 5000;
static constexpr unsigned long WATCHDOG_TIMEOUT_MS = 30UL * 60UL * 1000UL;
static constexpr float SECURITY_NIGHT_LUX_THRESHOLD = 10.0f;
static constexpr float SECURITY_DAY_LUX_THRESHOLD = 50.0f;
static constexpr uint8_t SECURITY_CAPTURE_BURST = 5;
static constexpr unsigned long SECURITY_COOLDOWN_MS = 30UL * 1000UL;
static constexpr bool BUZZER_ENABLED = true;
