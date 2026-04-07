#pragma once

#include <Arduino.h>

class MQTTService;

enum SecurityMode { DAY_MODE, NIGHT_MODE };

class SecurityService {
 public:
  void begin();
  void loop(float lightLux, MQTTService& mqttService);

 private:
  SecurityMode mode_ = DAY_MODE;
  unsigned long lastTriggeredAt_ = 0;
};
