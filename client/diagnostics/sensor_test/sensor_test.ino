/*
 * Sensor Init Test — verbose begin() for each I2C device and a
 * 1-Wire bus enumeration, at full 16 MHz clock (no prescaler),
 * no NRF24, no sleep.
 *
 * Flow:
 *   1) I2C scan
 *   2) Try BME280  @ 0x76 (then 0x77 fallback)
 *   3) Try AS5600  @ 0x36
 *   4) Try ADS1115 @ 0x48 (then 0x49 fallback)
 *   5) 1-Wire scan on D2 — list ROM IDs, decode family code
 *   6) DallasTemperature.begin() and confirm DS18B20 count
 *   7) Loop reading whatever initialized
 *
 * If any one device begins here but not in main.ino, the difference
 * is the clock prescaler / power-saving config in main.ino, not hardware.
 */

#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AS5600.h>
#include <Adafruit_ADS1X15.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define BME280_PRIMARY   0x76
#define BME280_FALLBACK  0x77
#define AS5600_ADDRESS   0x36
#define ADS1115_PRIMARY  0x48
#define ADS1115_FALLBACK 0x49

// DS18B20 soil temperature on the 1-Wire bus (D2, matches main.ino).
#define ONE_WIRE_BUS 2

Adafruit_BME280  bme;
Adafruit_AS5600  as5600;
Adafruit_ADS1115 ads;
OneWire          oneWire(ONE_WIRE_BUS);
DallasTemperature dsSensor(&oneWire);

bool bmeOk = false, asOk = false, adsOk = false, dsOk = false;
uint8_t bmeAddr = 0, adsAddr = 0;
uint8_t dsCount = 0;

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

// Enumerate 1-Wire devices and print their 8-byte ROM IDs. Family code
// is the first byte: 0x28 = DS18B20, 0x10 = DS18S20, 0x22 = DS1822.
static uint8_t scanOneWire() {
  Serial.println(F("--- 1-Wire scan (D2) ---"));
  oneWire.reset_search();
  uint8_t rom[8];
  uint8_t found = 0;
  while (oneWire.search(rom)) {
    Serial.print(F("  ROM "));
    for (uint8_t i = 0; i < 8; i++) {
      if (rom[i] < 0x10) Serial.print('0');
      Serial.print(rom[i], HEX);
      if (i < 7) Serial.print(':');
    }
    Serial.print(F("  family=0x"));
    if (rom[0] < 0x10) Serial.print('0');
    Serial.print(rom[0], HEX);
    Serial.print(F("  -> "));
    switch (rom[0]) {
      case 0x28: Serial.println(F("DS18B20")); break;
      case 0x10: Serial.println(F("DS18S20")); break;
      case 0x22: Serial.println(F("DS1822"));  break;
      default:   Serial.println(F("UNKNOWN family")); break;
    }
    if (OneWire::crc8(rom, 7) != rom[7]) {
      Serial.println(F("  ! CRC mismatch — wiring noise or weak pull-up"));
    }
    found++;
  }
  if (found == 0) {
    Serial.println(F("  no devices — check VDD/GND/DQ + 4.7k pull-up on DQ"));
  }
  Serial.print(F("1-Wire scan complete. devices found: "));
  Serial.println(found);
  return found;
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

  // Drive D6/D7 HIGH so the BC517 Darlingtons power up any switched
  // sensor rails (matches the production sketch's sensorPowerOn()).
  pinMode(7, OUTPUT);
  pinMode(6, OUTPUT);
  digitalWrite(7, HIGH);
  digitalWrite(6, HIGH);
  delay(100);

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

  Serial.println(F("\n[1-Wire]"));
  dsCount = scanOneWire();
  dsSensor.begin();
  dsOk = (dsSensor.getDeviceCount() > 0);
  Serial.print(F("  DallasTemperature device count = "));
  Serial.println(dsSensor.getDeviceCount());

  Serial.println(F("\n---- summary ----"));
  Serial.print(F("BME280  : "));  Serial.println(bmeOk ? F("OK") : F("FAIL"));
  Serial.print(F("AS5600  : "));  Serial.println(asOk  ? F("OK") : F("FAIL"));
  Serial.print(F("ADS1115 : "));  Serial.println(adsOk ? F("OK") : F("FAIL"));
  Serial.print(F("DS18B20 : "));  Serial.println(dsOk  ? F("OK") : F("FAIL"));
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
  if (dsOk) {
    dsSensor.requestTemperatures();
    float c = dsSensor.getTempCByIndex(0);
    Serial.print(F("DS18B20 T="));
    if (c == DEVICE_DISCONNECTED_C) {
      Serial.println(F("disconnected"));
    } else {
      Serial.print(c, 2);
      Serial.println(F("C"));
    }
  }
  Serial.println();
  delay(3000);
}
