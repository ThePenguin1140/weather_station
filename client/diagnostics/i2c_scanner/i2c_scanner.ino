/*
 * Minimal I2C Scanner — rules out software as the cause of I2C init failures.
 *
 * No sensor libraries, no clock prescaler, no sleep, no SPI/NRF.
 * Just Wire + Serial. If this sees nothing, the problem is hardware
 * (wiring, power, pull-ups, bus collision, or dead devices).
 *
 * Expected devices for this project:
 *   0x36  AS5600   (wind direction)
 *   0x49  ADS1115  (light/UV/battery/current)
 *   0x76  BME280   (T/P/H)
 *
 * Upload, then open serial monitor at 9600 baud.
 */

#include <Wire.h>

static void scanBus() {
  uint8_t found = 0;
  Serial.println(F("--- I2C scan ---"));
  for (uint8_t addr = 0x03; addr <= 0x77; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print(F("  device @ 0x"));
      if (addr < 0x10) Serial.print('0');
      Serial.println(addr, HEX);
      found++;
    } else if (err == 4) {
      // Unknown error — report; could be bus stuck low / no pull-ups.
      Serial.print(F("  unknown err @ 0x"));
      if (addr < 0x10) Serial.print('0');
      Serial.println(addr, HEX);
    }
  }
  Serial.print(F("Scan complete. devices found: "));
  Serial.println(found);
}

void setup() {
  Serial.begin(9600);
  while (!Serial) { ; }  // No-op on Nano (USB-serial is always present)
  delay(200);

  Serial.println();
  Serial.println(F("==== I2C Scanner ===="));
  Serial.print(F("F_CPU = "));
  Serial.println((uint32_t)F_CPU);
  Serial.print(F("CLKPR = 0x"));
  Serial.println(CLKPR, HEX);

  pinMode(LED_BUILTIN, OUTPUT);

  // Drive D6/D7 HIGH to turn on Q1/Q2 (BC517 Darlingtons) so JP1/JP2 sensor
  // rails come up. Without this the BME280/AS5600 rails are pulled to GND
  // by R10/R12 and the devices never appear on the bus.
  pinMode(7, OUTPUT);  // POWER_SWITCH_JP1_PIN (Q1 → JP1 rail)
  pinMode(6, OUTPUT);  // POWER_SWITCH_JP2_PIN (Q2 → JP2 rail)
  digitalWrite(7, HIGH);
  digitalWrite(6, HIGH);
  delay(100);  // Settling time per SENSOR_POWERUP_DELAY_MS in main.ino

  Wire.begin();
  // Slow the bus to 50 kHz — long-cable / weak-pullup tolerant.
  // Default is 100 kHz; uncomment if 100 kHz is unreliable.
  // Wire.setClock(50000);
  delay(50);
}

void loop() {
  scanBus();
  // Heartbeat blink so you can tell the sketch is alive even if scan is empty.
  digitalWrite(LED_BUILTIN, HIGH);
  delay(150);
  digitalWrite(LED_BUILTIN, LOW);
  delay(2000);
}
