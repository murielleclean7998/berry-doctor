#pragma once

#include <Arduino.h>

struct SensorSnapshot {
  float tempIndoor;
  float tempOutdoor;
  float humidity;
  float soilMoisture1;
  float soilMoisture2;
  float soilTemp;
  float lightLux;
  float leafWetness;
  float waterLevel;
  float co2ppm;
  float solutionEc;
  float solutionPh;
  float nutrientTemp;
};

class SensorManager {
 public:
  void begin();
  SensorSnapshot read() const;
};
