#include <DHT.h>
#include <HX711.h>

// PlanTalk Arduino Uno integrated sensor firmware.
// Each valid sample is emitted as one JSON object at 9600 baud.

constexpr uint8_t HX711_DOUT_PIN = 2;
constexpr uint8_t HX711_SCK_PIN = 3;
constexpr uint8_t DHT_PIN = 4;
constexpr uint8_t SOIL_PIN = A0;
constexpr uint8_t LIGHT_PIN = A1;

constexpr uint32_t SERIAL_BAUD = 9600;
constexpr uint32_t SAMPLE_INTERVAL_MS = 2000;
constexpr uint8_t LOAD_CELL_AVERAGE_COUNT = 10;
constexpr uint8_t ANALOG_AVERAGE_COUNT = 10;

DHT dht(DHT_PIN, DHT11);
HX711 scale;

uint32_t lastSampleStartedAt = 0;
uint32_t sequenceNumber = 0;

int readAnalogAverage(uint8_t pin) {
  long total = 0;
  for (uint8_t index = 0; index < ANALOG_AVERAGE_COUNT; ++index) {
    total += analogRead(pin);
    delay(2);
  }
  return static_cast<int>(total / ANALOG_AVERAGE_COUNT);
}

void printOptionalFloat(float value, uint8_t digits) {
  if (isnan(value)) {
    Serial.print(F("null"));
    return;
  }
  Serial.print(value, digits);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  dht.begin();
  scale.begin(HX711_DOUT_PIN, HX711_SCK_PIN);

  // Lines beginning with # are ignored by the PlanTalk JSONL gateway.
  Serial.println(F("# PlanTalk integrated sensor firmware started"));
  Serial.println(F("# HX711=D2/D3 DHT11=D4 SOIL=A0 LIGHT=A1 BAUD=9600"));
}

void loop() {
  const uint32_t now = millis();
  if (now - lastSampleStartedAt < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleStartedAt = now;

  if (!scale.is_ready()) {
    Serial.println(F("# HX711 not ready; sample skipped"));
    return;
  }

  const long loadCellRaw = scale.read_average(LOAD_CELL_AVERAGE_COUNT);
  const int soilRaw = readAnalogAverage(SOIL_PIN);
  const int lightRaw = readAnalogAverage(LIGHT_PIN);
  const float humidity = dht.readHumidity();
  const float temperature = dht.readTemperature();

  ++sequenceNumber;

  Serial.print(F("{\"sequence_no\":"));
  Serial.print(sequenceNumber);
  Serial.print(F(",\"device_uptime_ms\":"));
  Serial.print(now);
  Serial.print(F(",\"raw_sensor_value\":"));
  Serial.print(loadCellRaw);
  Serial.print(F(",\"soil_raw\":"));
  Serial.print(soilRaw);
  Serial.print(F(",\"light_raw\":"));
  Serial.print(lightRaw);
  Serial.print(F(",\"temperature_c\":"));
  printOptionalFloat(temperature, 1);
  Serial.print(F(",\"humidity_percent\":"));
  printOptionalFloat(humidity, 1);
  Serial.println(F("}"));
}
