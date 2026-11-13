void setup() {
  Serial.begin(9600);
}

void loop() {
  int soilValue = analogRead(A0);
  Serial.print("Soil sensor value: ");
  Serial.println(soilValue);
  delay(1000);
}
