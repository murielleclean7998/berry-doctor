#include "security.h"

#include "config.h"
#include "mqtt.h"

void SecurityService::begin() {
  pinMode(PIN_PIR_SENSOR, INPUT);
  pinMode(PIN_IR_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_IR_LED, LOW);
  digitalWrite(PIN_BUZZER, LOW);
}

void SecurityService::loop(float lightLux, MQTTService& mqttService) {
  if (lightLux < SECURITY_NIGHT_LUX_THRESHOLD) {
    mode_ = NIGHT_MODE;
  } else if (lightLux > SECURITY_DAY_LUX_THRESHOLD) {
    mode_ = DAY_MODE;
  }

  if (mode_ != NIGHT_MODE) {
    return;
  }
  if (millis() - lastTriggeredAt_ < SECURITY_COOLDOWN_MS) {
    return;
  }
  if (digitalRead(PIN_PIR_SENSOR) != HIGH) {
    return;
  }

  digitalWrite(PIN_IR_LED, HIGH);
  delay(200);
  mqttService.publishSecurityMotion(SECURITY_CAPTURE_BURST, true);
  if (BUZZER_ENABLED) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(1000);
    digitalWrite(PIN_BUZZER, LOW);
  }
  digitalWrite(PIN_IR_LED, LOW);
  lastTriggeredAt_ = millis();
}
