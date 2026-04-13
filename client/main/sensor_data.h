#pragma once
#include <stdint.h>

// Sensor data structure (packed to match Python struct.unpack format)
// struct size representation: <iIHHiHH
struct __attribute__((packed)) SensorData {
  int32_t temperature;     // Raw temperature in Celsius * 100
  uint32_t pressure;       // Raw pressure in Pascals
  uint16_t humidity;       // Raw humidity in %
  uint16_t windDirection;  // Wind direction in degrees (0-360)
  int32_t windSpeed;       // Calculated wind speed in km/h * 100
  uint16_t voltage;        // Battery voltage in millivolts (after divider scaling)
  uint16_t light;          // Light level, raw ADC (0-1023)
};
