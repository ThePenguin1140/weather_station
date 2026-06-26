#pragma once
#include <stdint.h>

// Sensor data structure (packed to match Python struct.unpack format)
// Python struct format: <iIHHiiHHHHH  (little-endian, no alignment) = 30 bytes
//
// Layout (must stay within the NRF24L01 32-byte payload limit):
//   temperature      int32   BME280            (°C × 100)
//   pressure         uint32  BME280            (Pa)
//   humidity         uint16  BME280            (%)
//   windDirection    uint16  AS5600            (degrees 0-359)
//   windSpeed        int32   anemometer (A2)   (km/h × 100)
//   soilTemperature  int32   DS18B20 (1-Wire)  (°C × 100)
//   soilMoisture     uint16  analog (A0)       (raw ADC 0-1023)
//   light            uint16  ADS1115 ch0       (raw counts)
//   uv               uint16  ADS1115 ch1       (raw counts)
//   voltage          uint16  ADS1115 ch2       (solar battery, mV)
//   current          uint16  ADS1115 ch2-ch3   (load current, mA)
struct __attribute__((packed)) SensorData {
  int32_t temperature;      // BME280 temperature in Celsius * 100
  uint32_t pressure;        // BME280 pressure in Pascals
  uint16_t humidity;        // BME280 humidity in %
  uint16_t windDirection;   // Wind direction in degrees (0-359)
  int32_t windSpeed;        // Anemometer wind speed in km/h * 100
  int32_t soilTemperature;  // DS18B20 soil temperature in Celsius * 100
  uint16_t soilMoisture;    // Soil moisture, raw ADC (0-1023)
  uint16_t light;           // Light level, raw ADS1115 counts (ch0)
  uint16_t uv;              // UV level, raw ADS1115 counts (ch1)
  uint16_t voltage;         // Solar battery voltage in millivolts (ADS1115 ch2)
  uint16_t current;         // Load current in milliamps (ADS1115 ch2-ch3 / R8)
};
