/*
 * Weather Station Sensor Transmitter
 * Arduino Nano with NRF24L01, BME280, AS5600, and Wind Speed Sensor
 * 
 * Reads sensor data and transmits via NRF24L01 wireless module
 */

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AS5600.h>
#include <avr/wdt.h>
#include <avr/sleep.h>
#include "sensor_data.h"

// NRF24L01 Pin Configuration
#define CE_PIN 9
#define CSN_PIN 8

// Status LED
#define LED_PIN 13

// Analog Sensor Pins
#define WIND_SPEED_PIN A2
#define VOLTAGE_PIN A0
#define LIGHT_PIN A1

// BME280 I2C Address (usually 0x76 or 0x77)
#define BME280_ADDRESS 0x76

#define AS5600_ADDRESS 0x36

// Debug flag: Set to false to disable clock prescaler for serial debugging
// When ENABLE_POWER_SAVING is false, serial communication will work at 9600 baud
// When true, clock is reduced to 2MHz (power savings) and serial is completely disabled
#define ENABLE_POWER_SAVING true

// Serial debugging macros - conditionally compile Serial operations
// When ENABLE_POWER_SAVING is true, these macros expand to nothing (zero overhead)
// When false, they expand to Serial.print/println/begin calls
#if ENABLE_POWER_SAVING
  #define DEBUG_SERIAL_BEGIN(baud) ((void)0)
  #define DEBUG_PRINT(...) ((void)0)
  #define DEBUG_PRINTLN(...) ((void)0)
#else
  #define DEBUG_SERIAL_BEGIN(baud) Serial.begin(baud)
  #define DEBUG_PRINT(...) Serial.print(__VA_ARGS__)
  #define DEBUG_PRINTLN(...) Serial.println(__VA_ARGS__)
#endif

// Transmission Configuration
#define SLEEP_CYCLES 38  // 38 × 8s ≈ 304s (~5 min)
#define MAX_RETRIES 3
#define ONE_SECOND 1000  // milliseconds

volatile uint8_t wdt_count = 0;

ISR(WDT_vect) {
  wdt_count++;
}

// Hardware Calibration Constants
#define WIND_DIRECTION_OFFSET 0        // Raw angle offset for magnet alignment (0-4095 range)
#define WIND_SPEED_RAW_OFFSET 0        // Analog reading offset for sensor zero point (0-1023 range)

// Wind Speed Hardware Constants (adjust based on your circuit)
#define WIND_SPEED_R1 10000.0          // 10K resistor in voltage divider
#define WIND_SPEED_R2 61900.0          // Adjust based on your setup
#define WIND_SPEED_KOR 80.0            // Calibration factor for km/h
#define WIND_SPEED_VIN_REF 5.0         // Reference voltage (5V for Arduino Nano)

// Radio Configuration
const byte address[6] = "00001";  // Pipe address for communication

// Initialize objects
RF24 radio(CE_PIN, CSN_PIN);
Adafruit_BME280 bme;
Adafruit_AS5600 as5600;

// Sensor initialization status (tracks whether begin() succeeded in setup)
bool bmeInitialized = false;
bool as5600Initialized = false;

void setup() {
  // Initialize Serial for debugging
  DEBUG_SERIAL_BEGIN(9600);

  // Lower clock frequency for power savings (divide by 4 = 4MHz from 16MHz)
  // 4MHz improves I2C/SPI reliability over 2MHz while still saving power
  noInterrupts();
  CLKPR = (1 << CLKPCE);  // Enable clock prescaler change
  CLKPR = (1 << CLKPS1);  // Divide by 4 (4MHz)
  interrupts();
  
  // Calculate frequency based on prescaler
  // Prescaler divides by 2^(CLKPS value)
  unsigned long baseFreq = F_CPU;  // Use compile-time F_CPU constant
  unsigned long divider = 1UL << (CLKPR & 0x0F);  // 2^CLKPS bits
  unsigned long actualFreq = baseFreq / divider;
  
  DEBUG_PRINT(F("Base CPU frequency (F_CPU): "));
  DEBUG_PRINT(baseFreq);
  DEBUG_PRINT(F(" Hz ("));
  if (baseFreq >= 1000000) {
    DEBUG_PRINT(baseFreq / 1000000.0, 1);
    DEBUG_PRINT(F(" MHz)"));
  } else if (baseFreq >= 1000) {
    DEBUG_PRINT(baseFreq / 1000.0, 1);
    DEBUG_PRINT(F(" kHz)"));
  } else {
    DEBUG_PRINT(F(" Hz)"));
  }
  DEBUG_PRINT(F(" | Prescaler: 1/"));
  DEBUG_PRINT(divider);
  DEBUG_PRINT(F(" | Actual frequency: "));
  DEBUG_PRINT(actualFreq);
  DEBUG_PRINT(F(" Hz ("));
  if (actualFreq >= 1000000) {
    DEBUG_PRINT(actualFreq / 1000000.0, 1);
    DEBUG_PRINTLN(F(" MHz)"));
  } else if (actualFreq >= 1000) {
    DEBUG_PRINT(actualFreq / 1000.0, 1);
    DEBUG_PRINTLN(F(" kHz)"));
  } else {
    DEBUG_PRINTLN(F(" Hz)"));
  }

  // Initialize Status LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize NRF24L01
  if (!radio.begin()) {
    DEBUG_PRINTLN(F("NRF24L01 initialization failed!"));
    blinkLED(10);  // Fast blink indicates error
    while (1) {
      delay(ONE_SECOND);
    }
  }

  radio.openWritingPipe(address);   // Set the address for transmission
  radio.setPALevel(RF24_PA_LOW);    // Set power amplifier level (LOW for better reliability)
  radio.setDataRate(RF24_250KBPS);  // Set data rate (slower = more reliable)
  radio.setChannel(76);             // Set RF channel (must match receiver!)
  radio.setRetries(30, 5);          // Retry up to 5 times with 7.5ms (30×250µs) between attempts
  radio.stopListening();            // Set as transmitter

  DEBUG_PRINTLN(F("NRF24L01 initialized successfully"));
  DEBUG_PRINT(F("Data Rate: "));
  DEBUG_PRINTLN(radio.getDataRate());
  DEBUG_PRINT(F("PA Level: "));
  DEBUG_PRINTLN(radio.getPALevel());
  DEBUG_PRINT(F("Channel: "));
  DEBUG_PRINTLN(radio.getChannel());

  delay(ONE_SECOND);

  DEBUG_PRINTLN(F("Starting BME280 initialization..."));

  // Initialize BME280
  if (!bme.begin(BME280_ADDRESS)) {
    DEBUG_PRINTLN(F("BME280 initialization failed! Check wiring and I2C address."));
    blinkLED(5);  // Medium blink indicates sensor error
    bmeInitialized = false;
  } else {
    DEBUG_PRINTLN(F("BME280 initialized successfully"));
    bmeInitialized = true;
    // Configure BME280 for weather monitoring
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,      // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,      // Temperature oversampling
                    Adafruit_BME280::SAMPLING_X16,     // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X1,      // Humidity oversampling
                    Adafruit_BME280::FILTER_X16,       // Filtering
                    Adafruit_BME280::STANDBY_MS_500);  // Standby time
  }

  delay(ONE_SECOND);

  DEBUG_PRINTLN(F("Starting AS5600 initialization..."));

  // Initialize AS5600 (Wind Direction)
  if (!as5600.begin(AS5600_ADDRESS)) {
    DEBUG_PRINTLN(F("AS5600 initialization failed! Check wiring."));
    blinkLED(5);  // Medium blink indicates sensor error
    as5600Initialized = false;
  } else {
    DEBUG_PRINTLN(F("AS5600 initialized successfully"));
    as5600Initialized = true;
    // Check if magnet is detected
    if (!as5600.isMagnetDetected()) {
      DEBUG_PRINTLN(F("Warning: AS5600 magnet not detected!"));
    }
  }

  delay(ONE_SECOND);

  // Initialize Wind Speed analog pin
  pinMode(WIND_SPEED_PIN, INPUT);

  DEBUG_PRINTLN(F("Setup complete. Starting transmission loop..."));
  blinkLED(3);  // Success indicator
}

void sleepWatchdog(uint8_t cycles) {
  // Configure WDT: interrupt mode only, 8-second timeout
  MCUSR &= ~(1 << WDRF);
  WDTCSR |= (1 << WDCE) | (1 << WDE);
  WDTCSR = (1 << WDIE) | (1 << WDP3) | (1 << WDP0);  // 8s, interrupt only (no reset)

  set_sleep_mode(SLEEP_MODE_PWR_DOWN);
  sleep_enable();

  wdt_count = 0;
  while (wdt_count < cycles) {
    sei();
    sleep_cpu();  // Wakes on WDT interrupt, loops back to sleep
  }

  sleep_disable();
  wdt_disable();
}

void loop() {
  SensorData data = readSensors();
  transmitData(data);
  sleepWatchdog(SLEEP_CYCLES);
}

SensorData readSensors() {
  SensorData data;

  // Read BME280 sensor
  if (bmeInitialized) {
    data.temperature = (int32_t)round(
      bme.readTemperature() * 100);

    data.pressure = (uint32_t)constrain(
      bme.readPressure(),
      0,
      200000);
    data.humidity = (uint16_t)constrain(
      bme.readHumidity(),
      0,
      100);
  } else {
    // Set error values if sensor not available
    data.temperature = -999;
    data.pressure = 0;
    data.humidity = 0;
    DEBUG_PRINTLN(F("Warning: BME280 read failed"));
  }

  // Read AS5600 (Wind Direction)
  if (as5600Initialized) {
    // Apply calibration offset to raw angle
    int rawAngle = as5600.getRawAngle();
    int calibratedRaw = (rawAngle + WIND_DIRECTION_OFFSET) % 4096;
    // Convert to degrees (0-360) and round to nearest whole degree
    float degrees = (calibratedRaw / 4096.0) * 360.0;
    data.windDirection = (uint16_t)round(degrees) % 360;  // Perfect angle: 0-360 degrees, rounded
  } else {
    // Set error value if sensor not available
    data.windDirection = 0;
    DEBUG_PRINTLN(F("Warning: AS5600 read failed"));
  }

  // Read Voltage (A0) - convert ADC reading to millivolts (0-5000 mV)
  data.voltage = (uint16_t)((analogRead(VOLTAGE_PIN) * 5000UL) / 1024);

  // Read Light Level (A1) - raw ADC value (0-1023)
  data.light = (uint16_t)analogRead(LIGHT_PIN);

  // Read Wind Speed (analog sensor)
  // Apply calibration offset to raw analog reading
  int rawReading = analogRead(WIND_SPEED_PIN);
  // NOTE: A negative WIND_SPEED_RAW_OFFSET will be clipped to 0 for low-wind readings
  // due to the constrain() below — inherent limit of offset-before-clamp ordering.
  int calibratedRaw = rawReading + WIND_SPEED_RAW_OFFSET;
  // Constrain to valid analog range
  calibratedRaw = constrain(calibratedRaw, 0, 1023);

  // Calculate wind speed using voltage divider formula with hardware constants
  float vout = (calibratedRaw * WIND_SPEED_VIN_REF) / 1024.0;
  float vin = vout / (WIND_SPEED_R2 / (WIND_SPEED_R1 + WIND_SPEED_R2));
  data.windSpeed = (int32_t)constrain(vin * WIND_SPEED_KOR, 0, 1000) * 100;

  return data;
}

void transmitData(SensorData data) {
  const size_t data_size = sizeof(data);
  bool success = false;
  // NOTE: Send compact binary struct instead of JSON string to stay under 32-byte NRF24 payload limit
  success = radio.write(&data, data_size);

  if (success) {
    DEBUG_PRINT(F("✓ Transmitted "));
    DEBUG_PRINT(data_size);
    DEBUG_PRINTLN(F(" bytes successfully"));
    DEBUG_PRINT(F("  temp="));       DEBUG_PRINT(data.temperature);
    DEBUG_PRINT(F(" pres="));        DEBUG_PRINT(data.pressure);
    DEBUG_PRINT(F(" hum="));         DEBUG_PRINT(data.humidity);
    DEBUG_PRINT(F(" wdir="));        DEBUG_PRINT(data.windDirection);
    DEBUG_PRINT(F(" wspd="));        DEBUG_PRINT(data.windSpeed);
    DEBUG_PRINT(F(" vcc="));         DEBUG_PRINT(data.voltage);
    DEBUG_PRINT(F(" light="));       DEBUG_PRINTLN(data.light);
    blinkLED(1);
  } else {
    DEBUG_PRINTLN(F("✗ Transmission failed"));
    blinkLED(2);  // Error indicator
  }
}

void blinkLED(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(100);
  }
}
