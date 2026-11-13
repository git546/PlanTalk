#include <HX711.h>

HX711 scale;

void setup() {
  Serial.begin(9600);
  scale.begin(2, 3);  // DT: 2번, SCK: 3번
  Serial.println("Load cell test");
}

void loop() {
  if (scale.is_ready()) {
    Serial.print("Sensor value: ");
    Serial.println(scale.read());
  } else {
    Serial.println("HX711 not found. Check wiring.");
  }

  delay(1000);
}
