/*
 * Chip ID Probe — read identifying registers from every device
 * the I2C scanner finds. No sensor libraries.
 *
 * Known chip-ID expectations:
 *   BME280  (0x76/0x77) : register 0xD0 should be 0x60
 *   BMP280  (0x76/0x77) : register 0xD0 is 0x58 (or 0x56/0x57 for prerelease)
 *   AS5600  (0x36)      : registers 0x0C (raw angle hi) etc.
 *   ADS1115 (0x48-0x4B) : register 0x01 (config) reset value 0x8583
 *
 * If 0x76 returns 0x58 the part is a BMP280 (no humidity sensor) —
 * the project schematic calls for a BME280.
 */

#include <Wire.h>

static uint8_t found[16];
static uint8_t foundCount = 0;

static void scanBus() {
  Serial.println(F("--- I2C scan ---"));
  foundCount = 0;
  for (uint8_t addr = 0x03; addr <= 0x77 && foundCount < 16; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("  device @ 0x"));
      if (addr < 0x10) Serial.print('0');
      Serial.println(addr, HEX);
      found[foundCount++] = addr;
    }
  }
}

// Read one byte from an 8-bit register
static bool read8(uint8_t addr, uint8_t reg, uint8_t& out) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 1) != 1) return false;
  out = Wire.read();
  return true;
}

// Read two bytes (big-endian) from an 8-bit register
static bool read16(uint8_t addr, uint8_t reg, uint16_t& out) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 2) != 2) return false;
  uint8_t hi = Wire.read();
  uint8_t lo = Wire.read();
  out = ((uint16_t)hi << 8) | lo;
  return true;
}

static void identifyBmeBmp(uint8_t addr) {
  // Bypass any helper — do the raw 4-step transaction and report each step
  // so we can tell counterfeit (0x58) from NACK (0/0xFF) from a dying chip
  // (endTransmission == 2). See the BME280 research notes.
  Wire.beginTransmission(addr);
  Wire.write(0xD0);
  uint8_t et = Wire.endTransmission(false);   // repeated-start; 0=ACK, 2=addr NACK, 3=data NACK
  uint8_t got = Wire.requestFrom((int)addr, 1);
  uint8_t id = Wire.available() ? Wire.read() : 0xFF;
  Serial.print(F("    raw read 0xD0  endTrans="));
  Serial.print(et);
  Serial.print(F("  requestFrom="));
  Serial.print(got);
  Serial.print(F("  byte=0x"));
  if (id < 0x10) Serial.print('0');
  Serial.print(id, HEX);
  Serial.print(F("  -> "));
  if (et == 0 && got == 1) {
    switch (id) {
      case 0x60: Serial.println(F("BME280 (T/P/H) — real")); break;
      case 0x58: Serial.println(F("BMP280 (T/P only, NO humidity) — counterfeit module")); break;
      case 0x56:
      case 0x57: Serial.println(F("BMP280 pre-release samples — counterfeit")); break;
      case 0x61: Serial.println(F("BME680")); break;
      default:   Serial.println(F("UNKNOWN chip ID — counterfeit / unrelated part")); break;
    }
  } else if (et != 0) {
    Serial.println(F("repeated-start NACK — chip stopped responding mid-transaction (dying/marginal supply)"));
  } else {
    Serial.println(F("no data byte — read path NACKed (bad SDA joint or dead die)"));
  }
}

static void identifyAds(uint8_t addr) {
  // ADS1115 config register reset value is 0x8583
  uint16_t cfg;
  if (!read16(addr, 0x01, cfg)) {
    Serial.println(F("    [ADS1115 probe] register read failed"));
    return;
  }
  Serial.print(F("    config reg (0x01) = 0x"));
  Serial.print(cfg, HEX);
  Serial.print(F(" (reset value should be 0x8583 -> "));
  Serial.println(cfg == 0x8583 ? F("MATCH") : F("non-default, still likely ADS1115)"));
}

static void identifyAs5600(uint8_t addr) {
  // AS5600 status register at 0x0B; raw angle at 0x0C/0x0D
  uint8_t status;
  if (!read8(addr, 0x0B, status)) {
    Serial.println(F("    [AS5600 probe] status read failed"));
    return;
  }
  Serial.print(F("    status (0x0B) = 0x"));
  Serial.println(status, HEX);
}

void setup() {
  Serial.begin(9600);
  delay(200);
  Serial.println();
  Serial.println(F("==== Chip ID Probe ===="));

  // Drive D6/D7 HIGH to power up the switched sensor rails (Q1/Q2 BC517
  // Darlingtons on JP1/JP2). Without this the BME280/AS5600 may be unpowered.
  pinMode(7, OUTPUT);
  pinMode(6, OUTPUT);
  digitalWrite(7, HIGH);
  digitalWrite(6, HIGH);
  delay(200);

  Wire.begin();
  delay(50);

  scanBus();

  Serial.println(F("\n--- probing each device ---"));
  for (uint8_t i = 0; i < foundCount; i++) {
    uint8_t a = found[i];
    Serial.print(F("0x"));
    if (a < 0x10) Serial.print('0');
    Serial.println(a, HEX);
    if (a == 0x76 || a == 0x77) identifyBmeBmp(a);
    else if (a >= 0x48 && a <= 0x4B) identifyAds(a);
    else if (a == 0x36) identifyAs5600(a);
    else Serial.println(F("    (no probe for this address)"));
  }
  Serial.println(F("\nDone. Halting."));
}

void loop() {
  delay(1000);
}
