#pragma once

#include <PubSubClient.h>
#include <WiFi.h>

#include "relays.h"
#include "sensors.h"

class MQTTService {
 public:
  void begin(RelayController* relays);
  void ensureConnected();
  void loop();
  void publishSnapshot(const SensorSnapshot& snapshot);
  void publishSecurityMotion(uint8_t photoCount, bool nightMode);

 private:
  static void staticCallback(char* topic, byte* payload, unsigned int length);
  void handleMessage(char* topic, byte* payload, unsigned int length);

  WiFiClient wifiClient_;
  PubSubClient client_{wifiClient_};
  RelayController* relays_ = nullptr;
  unsigned long lastPublishAt_ = 0;

  static MQTTService* instance_;
};
