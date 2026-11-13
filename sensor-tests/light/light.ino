void setup() {
  Serial.begin(9600);
}

void loop() {
  int lightValue = analogRead(A0);
  Serial.print("Light sensor value: ");
  Serial.println(lightValue);
  delay(1000);
}
