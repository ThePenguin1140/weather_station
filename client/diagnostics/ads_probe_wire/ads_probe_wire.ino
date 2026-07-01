// ads_probe_wire.ino — I2C ADC deep diagnostic (raw Wire.h)
//
// Auto-detects the chip at 0x48 and runs the right probe:
//
//   ADS1115  — 16-bit, config reg reset 0x8583, gain sweep + differential
//   PCF8591  — 8-bit ADC/DAC, single control byte per channel (common clone
//              modules sold as "ADS1115" breakouts)
//
// Signs you have a PCF8591, not an ADS1115:
//   - I2C ACK at 0x48 but "config reg" is not 0x8583
//   - Raw counts stay in 0–255 regardless of gain
//   - ADS1115 register writes time out or fail

#include <Wire.h>

#define ADC_ADDRESS 0x48

enum ChipType : uint8_t { CHIP_UNKNOWN, CHIP_ADS1115, CHIP_PCF8591 };

static ChipType chipType = CHIP_UNKNOWN;

// --- ADS1115 register map ---------------------------------------------------

#define ADS_REG_CONVERT 0x00
#define ADS_REG_CONFIG  0x01

#define MUX_SE_CH0   0x4000
#define MUX_SE_CH1   0x5000
#define MUX_SE_CH2   0x6000
#define MUX_SE_CH3   0x7000
#define MUX_DIFF_0_1 0x0000
#define MUX_DIFF_2_3 0x3000

#define PGA_2_3  0x0000
#define PGA_1    0x0200
#define PGA_2    0x0400
#define PGA_4    0x0600
#define PGA_8    0x0800
#define PGA_16   0x0A00

#define CFG_MODE_SINGLE 0x0100
#define CFG_RATE_128SPS 0x0080
#define CFG_OS_START    0x8000

const struct { uint16_t pga; const char* name; float fs; } adsGains[] = {
  { PGA_2_3, "2/3x (FS=6.144V)", 6.144f },
  { PGA_1,   "1x   (FS=4.096V)", 4.096f },
  { PGA_2,   "2x   (FS=2.048V)", 2.048f },
  { PGA_4,   "4x   (FS=1.024V)", 1.024f },
  { PGA_8,   "8x   (FS=0.512V)", 0.512f },
  { PGA_16,  "16x  (FS=0.256V)", 0.256f },
};

// --- shared I2C helpers -----------------------------------------------------

static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static bool adsWriteReg16(uint8_t addr, uint8_t reg, uint16_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write((uint8_t)(val >> 8));
  Wire.write((uint8_t)(val & 0xFF));
  return Wire.endTransmission() == 0;
}

static bool adsReadReg16(uint8_t addr, uint8_t reg, uint16_t& out) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)2) != 2) return false;
  if (Wire.available() < 2) return false;
  uint8_t hi = Wire.read();
  uint8_t lo = Wire.read();
  out = ((uint16_t)hi << 8) | lo;
  return true;
}

static uint16_t adsBuildConfig(uint16_t mux, uint16_t pga) {
  return (uint16_t)(CFG_OS_START | mux | pga | CFG_MODE_SINGLE | CFG_RATE_128SPS);
}

static uint8_t adsReadRaw(uint8_t addr, uint16_t mux, uint16_t pga, int16_t& raw) {
  if (!adsWriteReg16(addr, ADS_REG_CONFIG, adsBuildConfig(mux, pga))) return 1;
  delay(10);
  uint16_t result = 0;
  if (!adsReadReg16(addr, ADS_REG_CONVERT, result)) return 2;
  raw = (int16_t)result;
  return 0;
}

static float adsVolts(int16_t raw, float fsVolts) {
  return (float)raw * fsVolts / 32768.0f;
}

// --- PCF8591 protocol (8-bit ADC + DAC) -------------------------------------
// Control byte: bits 1-0 = channel (AIN0..AIN3), bit 6 = DAC enable on write.

static bool pcfReadChannel(uint8_t addr, uint8_t ch, uint8_t& out) {
  if (ch > 3) return false;
  Wire.beginTransmission(addr);
  Wire.write(ch);  // 0x00..0x03 select AIN0..AIN3
  if (Wire.endTransmission() != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)1) != 1) return false;
  if (!Wire.available()) return false;
  out = Wire.read();
  return true;
}

static bool pcfWriteDac(uint8_t addr, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(0x40);  // DAC enable
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

static float pcfVolts(uint8_t raw) {
  // PCF8591 is ratiometric to VDD; assume 5 V Nano rail unless measured.
  return (float)raw * 5.0f / 255.0f;
}

// --- chip identification ----------------------------------------------------

static ChipType identifyChip(uint8_t addr) {
  uint16_t cfg = 0;
  if (adsReadReg16(addr, ADS_REG_CONFIG, cfg) && cfg == 0x8583) {
    return CHIP_ADS1115;
  }

  // ADS1115 config wrong or missing — try PCF8591 channel reads.
  uint8_t samples[4];
  uint8_t ok = 0;
  for (uint8_t ch = 0; ch < 4; ch++) {
    if (pcfReadChannel(addr, ch, samples[ch])) ok++;
  }
  if (ok == 4) {
    Serial.print(F("ADS config was 0x"));
    if (adsReadReg16(addr, ADS_REG_CONFIG, cfg)) Serial.println(cfg, HEX);
    else Serial.println(F("(unreadable)"));
    Serial.print(F("PCF8591 channels read OK: "));
    for (uint8_t ch = 0; ch < 4; ch++) {
      Serial.print(samples[ch]);
      if (ch < 3) Serial.print(' ');
    }
    Serial.println();
    return CHIP_PCF8591;
  }

  return CHIP_UNKNOWN;
}

// --- probe loops ------------------------------------------------------------

static void loopAds1115() {
  Serial.println(F("\n---- gain sweep on ch0 (ADS1115) ----"));
  for (auto& gx : adsGains) {
    int16_t raw = 0;
    uint8_t err = adsReadRaw(ADC_ADDRESS, MUX_SE_CH0, gx.pga, raw);
    if (err) {
      Serial.print(F("  gain="));
      Serial.print(gx.name);
      Serial.print(F("  READ FAILED ("));
      Serial.print(err);
      Serial.println(F(")"));
      continue;
    }
    Serial.print(F("  gain="));
    Serial.print(gx.name);
    Serial.print(F("  raw="));
    Serial.print(raw);
    Serial.print(F("  V="));
    Serial.println(adsVolts(raw, gx.fs), 5);
  }

  Serial.println(F("---- single-ended (all 4 channels) ----"));
  const uint16_t seMux[] = { MUX_SE_CH0, MUX_SE_CH1, MUX_SE_CH2, MUX_SE_CH3 };
  for (uint8_t ch = 0; ch < 4; ch++) {
    int16_t raw = 0;
    uint8_t err = adsReadRaw(ADC_ADDRESS, seMux[ch], PGA_2_3, raw);
    if (err) {
      Serial.print(F("  ch"));
      Serial.print(ch);
      Serial.print(F("  READ FAILED ("));
      Serial.print(err);
      Serial.println(F(")"));
      continue;
    }
    Serial.print(F("  ch"));
    Serial.print(ch);
    Serial.print(F("  raw="));
    Serial.print(raw);
    Serial.print(F("  V="));
    Serial.println(adsVolts(raw, 6.144f), 5);
  }

  Serial.println(F("---- differential ----"));
  int16_t d01 = 0;
  int16_t d23 = 0;
  uint8_t e01 = adsReadRaw(ADC_ADDRESS, MUX_DIFF_0_1, PGA_2_3, d01);
  uint8_t e23 = adsReadRaw(ADC_ADDRESS, MUX_DIFF_2_3, PGA_2_3, d23);
  if (!e01) {
    Serial.print(F("  d(0-1) raw="));
    Serial.print(d01);
    Serial.print(F("  V="));
    Serial.println(adsVolts(d01, 6.144f), 5);
  } else {
    Serial.println(F("  d(0-1) READ FAILED"));
  }
  if (!e23) {
    Serial.print(F("  d(2-3) raw="));
    Serial.print(d23);
    Serial.print(F("  V="));
    Serial.println(adsVolts(d23, 6.144f), 5);
  } else {
    Serial.println(F("  d(2-3) READ FAILED"));
  }
}

static void loopPcf8591() {
  Serial.println(F("\n---- PCF8591: 8-bit reads (no PGA) ----"));
  Serial.println(F("(clone modules often mislabeled as ADS1115)"));

  uint8_t vals[4];
  for (uint8_t ch = 0; ch < 4; ch++) {
    if (!pcfReadChannel(ADC_ADDRESS, ch, vals[ch])) {
      Serial.print(F("  ch"));
      Serial.print(ch);
      Serial.println(F("  READ FAILED"));
      vals[ch] = 0;
      continue;
    }
    Serial.print(F("  ch"));
    Serial.print(ch);
    Serial.print(F("  raw="));
    Serial.print(vals[ch]);
    Serial.print(F("  V~"));
    Serial.println(pcfVolts(vals[ch]), 3);
  }

  Serial.println(F("---- software delta (ch0-ch1, ch2-ch3) ----"));
  Serial.print(F("  d(0-1) = "));
  Serial.println((int)vals[0] - (int)vals[1]);
  Serial.print(F("  d(2-3) = "));
  Serial.println((int)vals[2] - (int)vals[3]);

  Serial.println(F("---- DAC mirror (AIN0 -> OUT) ----"));
  if (pcfWriteDac(ADC_ADDRESS, vals[0])) {
    Serial.print(F("  wrote DAC "));
    Serial.println(vals[0]);
  } else {
    Serial.println(F("  DAC write failed"));
  }
}

void setup() {
  Serial.begin(9600);
  delay(200);

  pinMode(6, OUTPUT);
  pinMode(7, OUTPUT);
  digitalWrite(6, HIGH);
  digitalWrite(7, HIGH);
  delay(200);

  Wire.begin();
  delay(50);

  Serial.println(F("\n==== I2C ADC probe (Wire.h) ===="));
  if (!i2cPresent(ADC_ADDRESS)) {
    Serial.println(F("No device @ 0x48 — halting"));
    while (true) { delay(1000); }
  }

  chipType = identifyChip(ADC_ADDRESS);
  switch (chipType) {
    case CHIP_ADS1115:
      Serial.println(F("Identified: ADS1115"));
      break;
    case CHIP_PCF8591:
      Serial.println(F("Identified: PCF8591 (8-bit ADC/DAC)"));
      Serial.println(F("main.ino Adafruit_ADS1X15 driver will NOT work with this chip"));
      break;
    default:
      Serial.println(F("Identified: UNKNOWN — trying PCF8591 reads"));
      chipType = CHIP_PCF8591;
      break;
  }
}

void loop() {
  if (chipType == CHIP_ADS1115) {
    loopAds1115();
  } else {
    loopPcf8591();
  }
  delay(3000);
}
