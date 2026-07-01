#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <stdint.h>

// 4-channel I²C ADC in the Solar Battery Case (ADS1115 or common PCF8591 clone @ 0x48).
// Auto-detects chip type at adcBegin(); see client/diagnostics/ads_probe_wire/README.md.

#define ADC_I2C_ADDRESS 0x48

enum AdcChipType : uint8_t { ADC_NONE = 0, ADC_ADS1115, ADC_PCF8591 };

// --- ADS1115 register map ---------------------------------------------------

#define ADS_REG_CONVERT 0x00
#define ADS_REG_CONFIG  0x01

#define MUX_SE_CH0   0x4000
#define MUX_SE_CH1   0x5000
#define MUX_SE_CH2   0x6000
#define MUX_SE_CH3   0x7000
#define MUX_DIFF_2_3 0x3000

#define PGA_2_3 0x0000

#define CFG_MODE_SINGLE 0x0100
#define CFG_RATE_128SPS 0x0080
#define CFG_OS_START    0x8000

static const float ADS_FS_2_3 = 6.144f;
static const float PCF_VREF   = 5.0f;

static AdcChipType s_adcChip = ADC_NONE;
static uint8_t s_adcAddr = ADC_I2C_ADDRESS;

static bool adcI2cPresent(uint8_t addr) {
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

static bool adsReadRaw(uint8_t addr, uint16_t mux, uint16_t pga, int16_t& raw) {
  if (!adsWriteReg16(addr, ADS_REG_CONFIG, adsBuildConfig(mux, pga))) return false;
  delay(10);
  uint16_t result = 0;
  if (!adsReadReg16(addr, ADS_REG_CONVERT, result)) return false;
  raw = (int16_t)result;
  return true;
}

static float adsVolts(int16_t raw, float fsVolts) {
  return (float)raw * fsVolts / 32768.0f;
}

// PCF8591: stop-then-read after control byte (not repeated-start).
static bool pcfReadChannel(uint8_t addr, uint8_t ch, uint8_t& out) {
  if (ch > 3) return false;
  Wire.beginTransmission(addr);
  Wire.write(ch);
  if (Wire.endTransmission() != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)1) != 1) return false;
  if (!Wire.available()) return false;
  out = Wire.read();
  return true;
}

static float pcfVolts(uint8_t raw) {
  return (float)raw * PCF_VREF / 255.0f;
}

static float pcfVoltsDelta(int16_t delta) {
  return (float)delta * PCF_VREF / 255.0f;
}

static AdcChipType adcIdentifyChip(uint8_t addr) {
  uint16_t cfg = 0;
  if (adsReadReg16(addr, ADS_REG_CONFIG, cfg) && cfg == 0x8583) {
    return ADC_ADS1115;
  }

  uint8_t ok = 0;
  uint8_t sample = 0;
  for (uint8_t ch = 0; ch < 4; ch++) {
    if (pcfReadChannel(addr, ch, sample)) ok++;
  }
  if (ok == 4) {
    return ADC_PCF8591;
  }

  return ADC_NONE;
}

inline AdcChipType adcChipType() {
  return s_adcChip;
}

// Detect chip at addr and cache type. PCF8591 needs no further setup.
inline bool adcBegin(uint8_t addr = ADC_I2C_ADDRESS) {
  s_adcAddr = addr;
  s_adcChip = ADC_NONE;

  if (!adcI2cPresent(addr)) {
    return false;
  }

  s_adcChip = adcIdentifyChip(addr);
  return s_adcChip != ADC_NONE;
}

// ch0 = light, ch1 = UV, ch2 = solar battery (+), ch3 = post-shunt node.
// current_ma = (V_ch2 - V_ch3) / shunt_ohms × 1000; PCF8591 uses software delta.
inline bool adcReadSensors(uint16_t& light, uint16_t& uv, uint16_t& voltage_mv,
                           uint16_t& current_ma, float shunt_ohms) {
  if (s_adcChip == ADC_NONE) {
    return false;
  }

  if (s_adcChip == ADC_ADS1115) {
    int16_t lightRaw = 0;
    int16_t uvRaw = 0;
    int16_t battRaw = 0;
    int16_t shuntRaw = 0;
    if (!adsReadRaw(s_adcAddr, MUX_SE_CH0, PGA_2_3, lightRaw)) return false;
    if (!adsReadRaw(s_adcAddr, MUX_SE_CH1, PGA_2_3, uvRaw)) return false;
    if (!adsReadRaw(s_adcAddr, MUX_SE_CH2, PGA_2_3, battRaw)) return false;
    if (!adsReadRaw(s_adcAddr, MUX_DIFF_2_3, PGA_2_3, shuntRaw)) return false;

    light = (uint16_t)constrain(lightRaw, 0, 32767);
    uv = (uint16_t)constrain(uvRaw, 0, 32767);
    float batteryV = adsVolts(battRaw, ADS_FS_2_3);
    voltage_mv = (uint16_t)constrain(batteryV * 1000.0f, 0.0f, 65535.0f);
    float currentA = adsVolts(shuntRaw, ADS_FS_2_3) / shunt_ohms;
    current_ma = (uint16_t)constrain(currentA * 1000.0f, 0.0f, 65535.0f);
    return true;
  }

  uint8_t vals[4];
  for (uint8_t ch = 0; ch < 4; ch++) {
    if (!pcfReadChannel(s_adcAddr, ch, vals[ch])) return false;
  }

  light = vals[0];
  uv = vals[1];
  float batteryV = pcfVolts(vals[2]);
  voltage_mv = (uint16_t)constrain(batteryV * 1000.0f, 0.0f, 65535.0f);
  int16_t delta = (int16_t)vals[2] - (int16_t)vals[3];
  float currentA = pcfVoltsDelta(delta) / shunt_ohms;
  current_ma = (uint16_t)constrain(currentA * 1000.0f, 0.0f, 65535.0f);
  return true;
}
