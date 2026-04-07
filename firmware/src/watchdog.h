#pragma once

#include <Arduino.h>

#include "relays.h"

class RelayWatchdog {
 public:
  void begin();
  void loop(RelayController& relays);

 private:
  unsigned long lastForceOff_ = 0;
};
