#include "sensors.h"

void SensorManager::begin() {
  randomSeed(analogRead(0));
}

SensorSnapshot SensorManager::read() const {
  const float wave = static_cast<float>((millis() / 1000UL) % 120UL) / 120.0f;
  SensorSnapshot snapshot{};
  snapshot.tempIndoor = 20.0f + (wave * 8.0f);
  snapshot.tempOutdoor = 12.0f + (wave * 10.0f);
  snapshot.humidity = 72.0f + (wave * 18.0f);
  snapshot.soilMoisture1 = 35.0f - (wave * 10.0f);
  snapshot.soilMoisture2 = 37.0f - (wave * 8.0f);
  snapshot.soilTemp = 16.0f + (wave * 4.0f);
  snapshot.lightLux = 8000.0f + (wave * 9000.0f);
  snapshot.leafWetness = 25.0f + (wave * 20.0f);
  snapshot.waterLevel = 0.2f + (wave * 0.5f);
  snapshot.co2ppm = 420.0f + (wave * 180.0f);
  snapshot.solutionEc = 0.9f + (wave * 0.25f);
  snapshot.solutionPh = 5.8f + (wave * 0.4f);
  snapshot.nutrientTemp = 17.0f + (wave * 3.0f);
  return snapshot;
}
