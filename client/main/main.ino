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

// NRF24L01 Pin Configuration
#define CE_PIN 9
#define CSN_PIN 8

// Status LED
#define LED_PIN 13

// Wind Speed Sensor (Analog Pin)
#define WIND_SPEED_PIN A2

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
// Base interval in milliseconds (at 16MHz clock)
// When clock is divided by 8 (2MHz), millis() runs 8x slower, so we need 8x the count
// to achieve the same real-world time interval
const unsigned long TRANSMISSION_INTERVAL_BASE = 5UL * 60UL * 1000UL;  
const unsigned long TIMING_SCALER = 8UL;
const unsigned long ONE_SECOND = 1000 / TIMING_SCALER;
#define MAX_RETRIES 3

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

// Transmission timing (non-blocking)
unsigned long lastTransmissionTime = 0;
unsigned long lastStatusLogTime = 0;
unsigned long transmissionInterval = 0;  // Will be initialized in setup() based on ENABLE_POWER_SAVING
// Base interval in milliseconds (at 16MHz clock)
// When clock is divided by 8 (2MHz), millis() runs 8x slower, so we need 8x the count
const unsigned long STATUS_LOG_INTERVAL_BASE = 30000UL;  // Log status every 30 seconds (at 16MHz)
unsigned long statusLogInterval = 0;  // Will be initialized in setup() based on ENABLE_POWER_SAVING

// Sensor data structure (packed to match Python struct.unpack format)
// struct size representation: <iIHHi
struct __attribute__((packed)) SensorData {
  int32_t temperature;     // Raw temperature in Celsius
  uint32_t pressure;       // Raw pressure in Pascals
  uint16_t humidity;       // Raw humidity in %
  uint16_t windDirection;  // Wind direction in degrees (0-360), rounded to nearest whole degree
  int32_t windSpeed;       // Calculated wind speed in km/h
};

void setup() {
  // Initialize Serial for debugging
  DEBUG_SERIAL_BEGIN(9600);

  DEBUG_PRINTLN(F("Weather Station Transmitter Starting..."));

  // Initialize transmission and status log intervals based on power saving mode
  // When clock is divided by 8 (2MHz), millis() runs 8x slower, so we need 8x the count
  // to achieve the same real-world time interval
  #if ENABLE_POWER_SAVING
    transmissionInterval = TRANSMISSION_INTERVAL_BASE / TIMING_SCALER;
    statusLogInterval = STATUS_LOG_INTERVAL_BASE / TIMING_SCALER;
  #else
    transmissionInterval = TRANSMISSION_INTERVAL_BASE;
    statusLogInterval = STATUS_LOG_INTERVAL_BASE;
  #endif

  // Lower clock frequency for power savings (divide by 8 = 2MHz from 16MHz)
  // This reduces power consumption significantly while maintaining I2C/SPI functionality
  // NOTE: Clock prescaler change breaks serial communication timing
  // Set ENABLE_POWER_SAVING to false above to disable this for debugging
  #if ENABLE_POWER_SAVING
    noInterrupts();
    CLKPR = _BV(CLKPCE); // 0x80
    CLKPR = _BV(CLKPS1 | CLKPS0); // 0x03
    interrupts();
    DEBUG_PRINTLN(F("Power saving mode enabled"));
  #else
    DEBUG_PRINTLN(F("Debug mode: Full speed"));
  #endif

  // Print actual clock frequency
  // F_CPU is defined at compile-time by Arduino build system based on board selection
  // It represents the base CPU frequency before any prescaler changes
  noInterrupts();
  uint8_t clkpr = CLKPR & 0x0F;  // Read prescaler bits (CLKPS3:0)
  interrupts();
  
  // Calculate frequency based on prescaler
  // Prescaler divides by 2^(CLKPS value)
  unsigned long baseFreq = F_CPU;  // Use compile-time F_CPU constant
  unsigned long divider = 1UL << clkpr;  // 2^clkpr
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
  radio.setRetries(30, 5);          // Disable auto-retry and ACK (fire and forget)
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

void loop() {
  // Non-blocking transmission interval using millis()
  unsigned long currentTime = millis();
  
  // Check if enough time has passed since last transmission
  // Handle millis() overflow properly
  bool shouldTransmit = false;
  unsigned long elapsedForTransmit = 0;
  
  if (lastTransmissionTime == 0) {
    // First transmission - always transmit
    shouldTransmit = true;
    elapsedForTransmit = 0;
  } else if (currentTime >= lastTransmissionTime) {
    // Normal case: no overflow
    elapsedForTransmit = currentTime - lastTransmissionTime;
    shouldTransmit = (elapsedForTransmit >= transmissionInterval);
  } else {
    // Overflow occurred - enough time has definitely passed
    shouldTransmit = true;
    elapsedForTransmit = ((unsigned long)-1 - lastTransmissionTime) + currentTime + 1;
  }
  
  if (shouldTransmit) {
    DEBUG_PRINT(F("Transmission triggered (elapsed: "));
    DEBUG_PRINT(elapsedForTransmit);
    DEBUG_PRINT(F("ms >= interval: "));
    DEBUG_PRINT(transmissionInterval);
    DEBUG_PRINTLN(F("ms)"));
    SensorData data = readSensors();
    transmitData(data);
    lastTransmissionTime = currentTime;  // Update last transmission time
    lastStatusLogTime = currentTime;     // Reset status log timer after transmission
  }
  
  // Log time remaining until next transmission (every statusLogInterval)
  // Handle overflow in status log interval check
  bool shouldLogStatus = false;
  if (lastStatusLogTime == 0) {
    shouldLogStatus = true;
  } else if (currentTime >= lastStatusLogTime) {
    shouldLogStatus = (currentTime - lastStatusLogTime >= statusLogInterval);
  } else {
    // Overflow occurred - log status
    shouldLogStatus = true;
  }
  
  if (shouldLogStatus) {
    // Handle millis() overflow and initial state
    unsigned long elapsed;
    if (lastTransmissionTime == 0) {
      // First transmission hasn't happened yet
      elapsed = 0;
    } else if (currentTime >= lastTransmissionTime) {
      // Normal case: no overflow
      elapsed = currentTime - lastTransmissionTime;
    } else {
      // Overflow occurred - elapsed wraps around
      // This means we're very close to next transmission (or past it)
      elapsed = ((unsigned long)-1 - lastTransmissionTime) + currentTime + 1;
    }
    
    // Calculate remaining time, handling overflow/underflow
    unsigned long remaining;
    if (elapsed >= transmissionInterval) {
      // Time has passed - should transmit
      remaining = 0;
    } else {
      remaining = transmissionInterval - elapsed;
    }
    
    // Calculate minutes and seconds remaining
    unsigned long minutesRemaining = remaining / 60000;
    unsigned long secondsRemaining = (remaining % 60000) / 1000;
    
    DEBUG_PRINT(F("Next transmission in: "));
    DEBUG_PRINT(minutesRemaining);
    DEBUG_PRINT(F("m "));
    DEBUG_PRINT(secondsRemaining);
    DEBUG_PRINT(F("s (elapsed: "));
    DEBUG_PRINT(elapsed);
    DEBUG_PRINT(F("ms, interval: "));
    DEBUG_PRINT(transmissionInterval);
    DEBUG_PRINTLN(F("ms)"));
  
    lastStatusLogTime = currentTime;
  }
  
  // Small delay to prevent tight loop (optional, but good practice)
  delay(1000);
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

  // Read Wind Speed (analog sensor)
  // Apply calibration offset to raw analog reading
  int rawReading = analogRead(WIND_SPEED_PIN);
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
  radio.stopListening();
  DEBUG_PRINT(F("Transmitting | "));
  DEBUG_PRINT(data.temperature);
  DEBUG_PRINT(F(" | "));
  DEBUG_PRINT(data.pressure);
  DEBUG_PRINT(F(" | "));
  DEBUG_PRINT(data.humidity);
  DEBUG_PRINT(F(" | "));
  DEBUG_PRINT(data.windDirection);
  DEBUG_PRINT(F(" | "));
  DEBUG_PRINTLN(data.windSpeed);
  // NOTE: Send compact binary struct instead of JSON string to stay under 32-byte NRF24 payload limit
  success = radio.write(&data, data_size);

  if (success) {
    DEBUG_PRINT(F("✓ Transmitted "));
    DEBUG_PRINT(data_size);
    DEBUG_PRINTLN(" bytes successfully");
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
