#pragma once

#include "relays.h"
#include "sensors.h"

class LocalRuleEngine {
 public:
  void apply(const SensorSnapshot& snapshot, RelayController& relays);
};
