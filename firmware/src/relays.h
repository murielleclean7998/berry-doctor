#pragma once

#include <Arduino.h>

struct RelayState {
  bool vent = false;
  bool curtain = false;
  bool light = false;
  bool co2 = false;
  bool irrigation = false;
  bool drain = false;
};

class RelayController {
 public:
  void begin();
  void setVent(bool on);
  void setCurtain(bool on);
  void setLight(bool on);
  void setCo2(bool on);
  void pulseIrrigation(unsigned long durationMs);
  void pulseDrain(unsigned long durationMs);
  void loop();
  RelayState state() const;

 private:
  RelayState state_;
  unsigned long irrigationUntil_ = 0;
  unsigned long drainUntil_ = 0;
};
