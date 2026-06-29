/*
 * Weather Station Sensor Transmitter
 * Arduino Nano with NRF24L01, BME280, AS5600, DS18B20, ADS1115,
 * wind-speed anemometer and soil-moisture sensor
 *
 * Reads sensor data and transmits via NRF24L01 wireless module
 */

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_AS5600.h>
#include <Adafruit_ADS1X15.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <avr/wdt.h>
#include <avr/sleep.h>
#include "sensor_data.h"

// NRF24L01 Pin Configuration
#define CE_PIN 9
#define CSN_PIN 8

// Status LED
#define LED_PIN 13

// Analog Sensor Pins (Arduino native ADC)
#define WIND_SPEED_PIN A2
// Soil moisture on native analog pin A3 (per Rev 3 schematic, Moisture Sensor
// net 13). A0/A1 were freed when the battery monitor and light sensor moved to
// the ADS1115 in the Solar Battery Case.
#define SOIL_MOISTURE_PIN A3

// DS18B20 soil temperature sensor on the 1-Wire bus (digital pin D2)
#define ONE_WIRE_BUS 2

// BME280 I2C Address (usually 0x76 or 0x77)
#define BME280_ADDRESS 0x76

#define AS5600_ADDRESS 0x36

// ADS1115 4-channel ADC (Solar Battery Case), I2C address 0x49.
// Channel assignment: ch0 = light (LDR), ch1 = UV, ch2 = solar battery (+),
// ch3 = post-shunt node. Load current = (ch2 - ch3) / R8.
#define ADS1115_ADDRESS 0x48
#define ADS_CH_LIGHT 0
#define ADS_CH_UV 1
#define ADS_CH_BATTERY 2
#define ADS_CH_SHUNT 3
// Current-sense shunt R8 in the Solar Battery Case (ohms).
// Ig = (V_ch2 - V_ch3) / R8  (see project current-draw calculation).
#define CURRENT_SHUNT_R8 11.0

// Debug flag: Set to false to disable clock prescaler for serial debugging
// When ENABLE_POWER_SAVING is false, serial communication will work at 9600 baud
// When true, clock is reduced to 2MHz (power savings) and serial is completely disabled
#define ENABLE_POWER_SAVING false

// USART baud divisor is computed from compile-time F_CPU (16MHz) but setup()
// divides the clock by 4, so request 4× the desired PC-side baud rate.
#define DEBUG_BAUD 38400
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

// Wind Speed Hardware Constants (Rev 3 schematic: R3/R4 divider on Gen output)
#define WIND_SPEED_R1 10020.0          // R3: 10.02k resistor in voltage divider
#define WIND_SPEED_R2 62000.0          // R4: 62.0k resistor in voltage divider
#define WIND_SPEED_KOR 80.0            // Calibration factor for km/h
#define WIND_SPEED_VIN_REF 5.0         // Reference voltage (5V for Arduino Nano)

// Battery voltage and load current are read via the ADS1115 in the Solar
// Battery Case (see ADS1115 channel defines above), not a native ADC divider.

// Radio Configuration
const byte address[6] = "00001";  // Pipe address for communication

// Initialize objects
RF24 radio(CE_PIN, CSN_PIN);
Adafruit_BME280 bme;
Adafruit_AS5600 as5600;
Adafruit_ADS1115 ads;
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature soilTempSensor(&oneWire);

// Sensor initialization status (tracks whether begin() succeeded in setup)
bool bmeInitialized = false;
bool as5600Initialized = false;
bool adsInitialized = false;
bool soilTempInitialized = false;

void setup() {
  // 4MHz improves I2C/SPI reliability; Serial must init after this prescaler.
  noInterrupts();
  CLKPR = (1 << CLKPCE);
  CLKPR = (1 << CLKPS1);
  interrupts();

  DEBUG_SERIAL_BEGIN(DEBUG_BAUD);

#if !ENABLE_POWER_SAVING
  DEBUG_PRINTLN(F("Debug mode: watchdog sleep disabled, serial enabled"));
#endif

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
    // MODE_FORCED: sensor takes one measurement then returns to sleep,
    // saving ~633 µA vs MODE_NORMAL which samples continuously at 500ms intervals.
    // Call bme.takeForcedMeasurement() before each read in readSensors().
    bme.setSampling(Adafruit_BME280::MODE_FORCED,      // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,      // Temperature oversampling
                    Adafruit_BME280::SAMPLING_X16,     // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X1,      // Humidity oversampling
                    Adafruit_BME280::FILTER_X16,       // Filtering
                    Adafruit_BME280::STANDBY_MS_500);  // Standby time (unused in FORCED mode)
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
    // Set LPM3: 100ms polling, 1.5mA vs 6.5mA in normal mode.
    // 100ms update rate is more than sufficient for wind direction at 5-min intervals.
    as5600.setPowerMode(AS5600_POWER_MODE_LPM3);
    // Check if magnet is detected
    if (!as5600.isMagnetDetected()) {
      DEBUG_PRINTLN(F("Warning: AS5600 magnet not detected!"));
    }
  }

  delay(ONE_SECOND);

  DEBUG_PRINTLN(F("Starting ADS1115 initialization..."));

  // Initialize ADS1115 (light, UV, battery voltage and current shunt)
  if (!ads.begin(ADS1115_ADDRESS)) {
    DEBUG_PRINTLN(F("ADS1115 initialization failed! Check wiring and I2C address."));
    blinkLED(5);  // Medium blink indicates sensor error
    adsInitialized = false;
  } else {
    DEBUG_PRINTLN(F("ADS1115 initialized successfully"));
    adsInitialized = true;
    // GAIN_TWOTHIRDS: ±6.144V full scale, suitable for the ~3.7V solar
    // battery and 5V-referenced light/UV signals.
    ads.setGain(GAIN_TWOTHIRDS);
  }

  delay(ONE_SECOND);

  DEBUG_PRINTLN(F("Starting DS18B20 initialization..."));

  // Initialize DS18B20 soil temperature sensor (1-Wire)
  soilTempSensor.begin();
  if (soilTempSensor.getDeviceCount() == 0) {
    DEBUG_PRINTLN(F("DS18B20 not found on 1-Wire bus! Check wiring and pullup."));
    blinkLED(5);  // Medium blink indicates sensor error
    soilTempInitialized = false;
  } else {
    DEBUG_PRINTLN(F("DS18B20 initialized successfully"));
    soilTempInitialized = true;
    // Blocking conversion: requestTemperatures() waits for the sensor, which
    // is fine since the MCU sleeps between transmissions anyway.
    soilTempSensor.setWaitForConversion(true);
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
    bme.takeForcedMeasurement();  // Trigger one measurement; sensor sleeps again after
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
    int calibratedRaw = ((rawAngle + WIND_DIRECTION_OFFSET) % 4096 + 4096) % 4096;
    // Convert to degrees (0-360) and round to nearest whole degree
    float degrees = (calibratedRaw / 4096.0) * 360.0;
    data.windDirection = (uint16_t)round(degrees) % 360;  // Wind direction in degrees, 0-359
  } else {
    // Set error value if sensor not available
    data.windDirection = 0;
    DEBUG_PRINTLN(F("Warning: AS5600 read failed"));
  }

  // Read DS18B20 (Soil Temperature, 1-Wire)
  if (soilTempInitialized) {
    soilTempSensor.requestTemperatures();  // Trigger + wait for conversion
    float soilTempC = soilTempSensor.getTempCByIndex(0);
    if (soilTempC == DEVICE_DISCONNECTED_C) {
      data.soilTemperature = -99900;  // Error sentinel (-999.00 °C)
      DEBUG_PRINTLN(F("Warning: DS18B20 read failed (disconnected)"));
    } else {
      data.soilTemperature = (int32_t)round(soilTempC * 100);
    }
  } else {
    data.soilTemperature = -99900;  // Error sentinel (-999.00 °C)
    DEBUG_PRINTLN(F("Warning: DS18B20 not initialized"));
  }

  // Read Soil Moisture (native analog pin) - raw ADC value (0-1023)
  data.soilMoisture = (uint16_t)analogRead(SOIL_MOISTURE_PIN);

  // Read ADS1115 channels (light, UV, solar battery voltage, current shunt)
  if (adsInitialized) {
    // Light (ch0) and UV (ch1) as raw single-ended counts (clamp negatives)
    int16_t lightRaw = ads.readADC_SingleEnded(ADS_CH_LIGHT);
    int16_t uvRaw = ads.readADC_SingleEnded(ADS_CH_UV);
    data.light = (uint16_t)constrain(lightRaw, 0, 32767);
    data.uv = (uint16_t)constrain(uvRaw, 0, 32767);

    // Solar battery voltage (ch2) in millivolts
    float batteryV = ads.computeVolts(ads.readADC_SingleEnded(ADS_CH_BATTERY));
    data.voltage = (uint16_t)constrain(batteryV * 1000.0f, 0, 65535);

    // Load current from the shunt: Ig = (V_ch2 - V_ch3) / R8.
    // Read differentially across ch2-ch3 for better small-signal accuracy.
    float shuntV = ads.computeVolts(ads.readADC_Differential_2_3());
    float currentA = shuntV / CURRENT_SHUNT_R8;
    data.current = (uint16_t)constrain(currentA * 1000.0f, 0, 65535);
  } else {
    data.light = 0;
    data.uv = 0;
    data.voltage = 0;
    data.current = 0;
    DEBUG_PRINTLN(F("Warning: ADS1115 not initialized"));
  }

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
  data.windSpeed = (int32_t)(constrain(vin * WIND_SPEED_KOR, 0, 1000.0f) * 100);

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
    DEBUG_PRINT(F(" soilT="));       DEBUG_PRINT(data.soilTemperature);
    DEBUG_PRINT(F(" soilM="));       DEBUG_PRINT(data.soilMoisture);
    DEBUG_PRINT(F(" light="));       DEBUG_PRINT(data.light);
    DEBUG_PRINT(F(" uv="));          DEBUG_PRINT(data.uv);
    DEBUG_PRINT(F(" vcc="));         DEBUG_PRINT(data.voltage);
    DEBUG_PRINT(F(" curr="));        DEBUG_PRINTLN(data.current);
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
