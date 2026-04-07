#include "relays.h"

#include "config.h"

namespace {
void writeRelay(uint8_t pin, bool on) {
  digitalWrite(pin, on ? LOW : HIGH);
}
}

void RelayController::begin() {
  pinMode(PIN_RELAY_VENT, OUTPUT);
  pinMode(PIN_RELAY_CURTAIN, OUTPUT);
  pinMode(PIN_RELAY_LIGHT, OUTPUT);
  pinMode(PIN_RELAY_CO2, OUTPUT);
  pinMode(PIN_PUMP_MAIN, OUTPUT);
  pinMode(PIN_PUMP_DRAIN, OUTPUT);
  writeRelay(PIN_RELAY_VENT, false);
  writeRelay(PIN_RELAY_CURTAIN, false);
  writeRelay(PIN_RELAY_LIGHT, false);
  writeRelay(PIN_RELAY_CO2, false);
  digitalWrite(PIN_PUMP_MAIN, LOW);
  digitalWrite(PIN_PUMP_DRAIN, LOW);
}

void RelayController::setVent(bool on) {
  state_.vent = on;
  writeRelay(PIN_RELAY_VENT, on);
}

void RelayController::setCurtain(bool on) {
  state_.curtain = on;
  writeRelay(PIN_RELAY_CURTAIN, on);
}

void RelayController::setLight(bool on) {
  state_.light = on;
  writeRelay(PIN_RELAY_LIGHT, on);
}

void RelayController::setCo2(bool on) {
  state_.co2 = on;
  writeRelay(PIN_RELAY_CO2, on);
}

void RelayController::pulseIrrigation(unsigned long durationMs) {
  state_.irrigation = true;
  irrigationUntil_ = millis() + durationMs;
  digitalWrite(PIN_PUMP_MAIN, HIGH);
}

void RelayController::pulseDrain(unsigned long durationMs) {
  state_.drain = true;
  drainUntil_ = millis() + durationMs;
  digitalWrite(PIN_PUMP_DRAIN, HIGH);
}

void RelayController::loop() {
  if (state_.irrigation && millis() >= irrigationUntil_) {
    state_.irrigation = false;
    digitalWrite(PIN_PUMP_MAIN, LOW);
  }
  if (state_.drain && millis() >= drainUntil_) {
    state_.drain = false;
    digitalWrite(PIN_PUMP_DRAIN, LOW);
  }
}

RelayState RelayController::state() const {
  return state_;
}
