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

static constexpr unsigned long SENSOR_PUBLISH_INTERVAL_MS = 5000;
static constexpr unsigned long WATCHDOG_TIMEOUT_MS = 30UL * 60UL * 1000UL;
