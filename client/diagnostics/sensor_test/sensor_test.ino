/*
 * Sensor Init Test — verbose begin() for each I2C device individually,
 * at full 16 MHz clock (no prescaler), no NRF24, no sleep.
 *
 * Flow:
 *   1) I2C scan
 *   2) Try BME280  @ 0x76 (then 0x77 fallback)
 *   3) Try AS5600  @ 0x36
 *   4) Try ADS1115 @ 0x49 (then 0x48 fallback)
 *   5) Loop reading whatever initialized
 *
 * If any one device begins here but not in main.ino, the difference
 * is the clock prescaler / power-saving config in main.ino, not hardware.
 */

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AS5600.h>
#include <Adafruit_ADS1X15.h>

#define BME280_PRIMARY   0x76
#define BME280_FALLBACK  0x77
#define AS5600_ADDRESS   0x36
#define ADS1115_PRIMARY  0x49
#define ADS1115_FALLBACK 0x48

Adafruit_BME280  bme;
Adafruit_AS5600  as5600;
Adafruit_ADS1115 ads;

bool bmeOk = false, asOk = false, adsOk = false;
uint8_t bmeAddr = 0, adsAddr = 0;

static void scanBus() {
  Serial.println(F("--- I2C scan ---"));
  uint8_t found = 0;
  for (uint8_t addr = 0x03; addr <= 0x77; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("  device @ 0x"));
      if (addr < 0x10) Serial.print('0');
      Serial.println(addr, HEX);
      found++;
    }
  }
  Serial.print(F("Scan complete. devices found: "));
  Serial.println(found);
}

static bool tryBme(uint8_t addr) {
  Serial.print(F("  BME280 begin @ 0x"));
  Serial.print(addr, HEX);
  Serial.print(F(" ... "));
  bool ok = bme.begin(addr);
  Serial.println(ok ? F("OK") : F("FAIL"));
  if (ok) {
    Serial.print(F("    sensorID = 0x"));
    Serial.println(bme.sensorID(), HEX);  // 0x60 = BME280, 0x58 = BMP280, 0x56/0x57 = BMP280 prerelease
  }
  return ok;
}

static bool tryAds(uint8_t addr) {
  Serial.print(F("  ADS1115 begin @ 0x"));
  Serial.print(addr, HEX);
  Serial.print(F(" ... "));
  bool ok = ads.begin(addr);
  Serial.println(ok ? F("OK") : F("FAIL"));
  return ok;
}

void setup() {
  Serial.begin(9600);
  delay(200);
  Serial.println();
  Serial.println(F("==== Sensor Init Test ===="));
  Serial.print(F("F_CPU = "));
  Serial.print((uint32_t)F_CPU);
  Serial.print(F(" Hz | CLKPR = 0x"));
  Serial.println(CLKPR, HEX);

  pinMode(LED_BUILTIN, OUTPUT);

  Wire.begin();
  delay(50);

  scanBus();

  Serial.println(F("\n[BME280]"));
  bmeOk = tryBme(BME280_PRIMARY);
  if (!bmeOk) { bmeOk = tryBme(BME280_FALLBACK); if (bmeOk) bmeAddr = BME280_FALLBACK; }
  else { bmeAddr = BME280_PRIMARY; }
  if (bmeOk) {
    bme.setSampling(Adafruit_BME280::MODE_FORCED,
                    Adafruit_BME280::SAMPLING_X2,
                    Adafruit_BME280::SAMPLING_X16,
                    Adafruit_BME280::SAMPLING_X1,
                    Adafruit_BME280::FILTER_X16);
  }

  Serial.println(F("\n[AS5600]"));
  Serial.print(F("  AS5600 begin @ 0x36 ... "));
  asOk = as5600.begin(AS5600_ADDRESS);
  Serial.println(asOk ? F("OK") : F("FAIL"));
  if (asOk) {
    Serial.print(F("    magnet detected: "));
    Serial.println(as5600.isMagnetDetected() ? F("yes") : F("NO"));
  }

  Serial.println(F("\n[ADS1115]"));
  adsOk = tryAds(ADS1115_PRIMARY);
  if (!adsOk) { adsOk = tryAds(ADS1115_FALLBACK); if (adsOk) adsAddr = ADS1115_FALLBACK; }
  else { adsAddr = ADS1115_PRIMARY; }
  if (adsOk) ads.setGain(GAIN_TWOTHIRDS);

  Serial.println(F("\n---- summary ----"));
  Serial.print(F("BME280  : "));  Serial.println(bmeOk ? F("OK") : F("FAIL"));
  Serial.print(F("AS5600  : "));  Serial.println(asOk  ? F("OK") : F("FAIL"));
  Serial.print(F("ADS1115 : "));  Serial.println(adsOk ? F("OK") : F("FAIL"));
  Serial.println(F("Looping reads every 3s...\n"));
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(50);
  digitalWrite(LED_BUILTIN, LOW);

  if (bmeOk) {
    bme.takeForcedMeasurement();
    Serial.print(F("BME  T="));
    Serial.print(bme.readTemperature(), 2);
    Serial.print(F("C  P="));
    Serial.print(bme.readPressure() / 100.0, 1);
    Serial.print(F("hPa  H="));
    Serial.print(bme.readHumidity(), 1);
    Serial.println(F("%"));
  }
  if (asOk) {
    Serial.print(F("AS5600 raw="));
    Serial.print(as5600.getRawAngle());
    Serial.print(F("  magnet="));
    Serial.println(as5600.isMagnetDetected() ? 1 : 0);
  }
  if (adsOk) {
    Serial.print(F("ADS  ch0="));
    Serial.print(ads.readADC_SingleEnded(0));
    Serial.print(F("  ch1="));
    Serial.print(ads.readADC_SingleEnded(1));
    Serial.print(F("  ch2="));
    Serial.print(ads.readADC_SingleEnded(2));
    Serial.print(F("  ch3="));
    Serial.println(ads.readADC_SingleEnded(3));
  }
  Serial.println();
  delay(3000);
}
