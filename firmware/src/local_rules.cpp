#include "local_rules.h"

void LocalRuleEngine::apply(const SensorSnapshot& snapshot, RelayController& relays) {
  if (snapshot.humidity >= 88.0f || snapshot.tempIndoor >= 28.0f) {
    relays.setVent(true);
  } else if (snapshot.humidity <= 78.0f && snapshot.tempIndoor <= 24.0f) {
    relays.setVent(false);
  }

  if (snapshot.lightLux < 9000.0f) {
    relays.setLight(true);
  } else if (snapshot.lightLux > 12000.0f) {
    relays.setLight(false);
  }

  if (((snapshot.soilMoisture1 + snapshot.soilMoisture2) / 2.0f) < 24.0f) {
    relays.pulseIrrigation(15000UL);
  }

  if (snapshot.waterLevel > 0.8f) {
    relays.pulseDrain(20000UL);
  }
}
