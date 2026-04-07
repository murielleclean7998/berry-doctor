#include "mqtt.h"

#include <ArduinoJson.h>

#include "config.h"

MQTTService* MQTTService::instance_ = nullptr;

void MQTTService::begin(RelayController* relays) {
  relays_ = relays;
  instance_ = this;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  client_.setServer(MQTT_HOST, MQTT_PORT);
  client_.setCallback(MQTTService::staticCallback);
  client_.setBufferSize(512);
}

void MQTTService::ensureConnected() {
  if (!client_.connected()) {
    const String clientId = String("berrydoctor-esp32-") + String(HOUSE_ID);
    if (client_.connect(clientId.c_str())) {
      client_.subscribe("control/+/+");
    }
  }
}

void MQTTService::loop() {
  ensureConnected();
  client_.loop();
}

void MQTTService::publishSnapshot(const SensorSnapshot& snapshot) {
  if (!client_.connected()) {
    return;
  }
  if (millis() - lastPublishAt_ < SENSOR_PUBLISH_INTERVAL_MS) {
    return;
  }

  StaticJsonDocument<512> doc;
  doc["house_id"] = HOUSE_ID;
  doc["temp_indoor"] = snapshot.tempIndoor;
  doc["temp_outdoor"] = snapshot.tempOutdoor;
  doc["humidity"] = snapshot.humidity;
  doc["soil_moisture_1"] = snapshot.soilMoisture1;
  doc["soil_moisture_2"] = snapshot.soilMoisture2;
  doc["soil_temp"] = snapshot.soilTemp;
  doc["light_lux"] = snapshot.lightLux;
  doc["leaf_wetness"] = snapshot.leafWetness;
  doc["water_level"] = snapshot.waterLevel;
  doc["co2_ppm"] = snapshot.co2ppm;
  doc["solution_ec"] = snapshot.solutionEc;
  doc["solution_ph"] = snapshot.solutionPh;
  doc["nutrient_temp"] = snapshot.nutrientTemp;

  char payload[512];
  const size_t written = serializeJson(doc, payload);
  const String topic = String("sensor/") + String(HOUSE_ID) + "/state";
  client_.publish(topic.c_str(), payload, written);
  lastPublishAt_ = millis();
}

void MQTTService::publishSecurityMotion(uint8_t photoCount, bool nightMode) {
  if (!client_.connected()) {
    return;
  }

  StaticJsonDocument<384> doc;
  doc["house_id"] = HOUSE_ID;
  doc["timestamp"] = millis();
  doc["mode"] = nightMode ? "night" : "day";
  JsonArray photos = doc.createNestedArray("photos");
  for (uint8_t index = 0; index < photoCount; ++index) {
    String name = String("security_") + String(HOUSE_ID) + "_" + String(millis()) + "_" + String(index + 1) + ".jpg";
    photos.add(name);
  }

  char payload[384];
  const size_t written = serializeJson(doc, payload);
  const String topic = String("security/") + String(HOUSE_ID) + "/motion";
  client_.publish(topic.c_str(), payload, written);
}

void MQTTService::staticCallback(char* topic, byte* payload, unsigned int length) {
  if (instance_ != nullptr) {
    instance_->handleMessage(topic, payload, length);
  }
}

void MQTTService::handleMessage(char* topic, byte* payload, unsigned int length) {
  if (relays_ == nullptr) {
    return;
  }
  StaticJsonDocument<256> doc;
  const DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    return;
  }

  const String commandTopic(topic);
  if (!commandTopic.startsWith("control/")) {
    return;
  }

  const String device = doc["device"] | "";
  const String action = doc["action"] | "";

  if (device == "ventilation") {
    relays_->setVent(action == "on" || action == "boost");
  } else if (device == "curtain") {
    relays_->setCurtain(action == "close");
  } else if (device == "supplemental_light") {
    relays_->setLight(action == "on");
  } else if (device == "co2") {
    relays_->setCo2(action == "on");
  } else if (device == "irrigation") {
    relays_->pulseIrrigation((doc["duration_seconds"] | 20) * 1000UL);
  } else if (device == "drain_pump") {
    relays_->pulseDrain((doc["duration_minutes"] | 1) * 60000UL);
  }
}
