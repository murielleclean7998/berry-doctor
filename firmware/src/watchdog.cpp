#include "watchdog.h"

#include "config.h"

void RelayWatchdog::begin() {
  lastForceOff_ = millis();
}

void RelayWatchdog::loop(RelayController& relays) {
  const RelayState state = relays.state();
  const bool anyLongRunning = state.vent || state.curtain || state.light || state.co2;
  if (anyLongRunning && millis() - lastForceOff_ > WATCHDOG_TIMEOUT_MS) {
    relays.setVent(false);
    relays.setCurtain(false);
    relays.setLight(false);
    relays.setCo2(false);
    lastForceOff_ = millis();
  }
  if (!anyLongRunning) {
    lastForceOff_ = millis();
  }
}
