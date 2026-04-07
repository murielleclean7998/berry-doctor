#include <Arduino.h>

#include "local_rules.h"
#include "mqtt.h"
#include "relays.h"
#include "sensors.h"
#include "watchdog.h"

namespace {
SensorManager sensors;
RelayController relays;
LocalRuleEngine localRules;
RelayWatchdog watchdogService;
MQTTService mqttService;
}

void setup() {
  Serial.begin(115200);
  sensors.begin();
  relays.begin();
  watchdogService.begin();
  mqttService.begin(&relays);
}

void loop() {
  const SensorSnapshot snapshot = sensors.read();
  localRules.apply(snapshot, relays);
  relays.loop();
  watchdogService.loop(relays);
  mqttService.loop();
  mqttService.publishSnapshot(snapshot);
  delay(200);
}
