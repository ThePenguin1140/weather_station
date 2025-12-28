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
#include <ArduinoJson.h>

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

// Transmission Configuration
#define TRANSMISSION_INTERVAL 5000  // Transmit every 5 seconds
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

// Timing variables
unsigned long lastTransmission = 0;
unsigned long lastLEDToggle = 0;
bool ledState = false;

// Sensor data structure (packed to match Python struct.unpack format)
struct __attribute__((packed)) SensorData {
  float temperature;         // Raw temperature in Celsius
  float pressure;            // Raw pressure in Pascals
  float humidity;            // Raw humidity in %
  uint16_t windDirection;    // Raw angle (0-4095) with calibration offset applied
  float windSpeed;           // Calculated wind speed in km/h
};

void setup() {
  // Initialize Serial for debugging
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect
  }
  Serial.println(F("Weather Station Transmitter Starting..."));

  // Initialize Status LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize NRF24L01
  if (!radio.begin()) {
    Serial.println(F("NRF24L01 initialization failed!"));
    blinkLED(10);  // Fast blink indicates error
    while (1) {
      delay(1000);
    }
  }
  
  radio.openWritingPipe(address);     // Set the address for transmission
  radio.setPALevel(RF24_PA_LOW);      // Set power amplifier level (LOW for better reliability)
  radio.setDataRate(RF24_250KBPS);    // Set data rate (slower = more reliable)
  radio.setChannel(76);               // Set RF channel (must match receiver!)
  radio.setRetries(15, 15);           // Set auto-retry (delay, count)
  radio.stopListening();              // Set as transmitter
  
  Serial.println(F("NRF24L01 initialized successfully"));
  Serial.print(F("Data Rate: "));
  Serial.println(radio.getDataRate());
  Serial.print(F("PA Level: "));
  Serial.println(radio.getPALevel());
  Serial.print(F("Channel: "));
  Serial.println(radio.getChannel());

  delay(1000);

  Serial.println(F("Starting BME280 initialization..."));

  // Initialize BME280
  if (!bme.begin(BME280_ADDRESS)) {
    Serial.println(F("BME280 initialization failed! Check wiring and I2C address."));
    blinkLED(5);  // Medium blink indicates sensor error
    // Continue anyway - will retry in loop
  } else {
    Serial.println(F("BME280 initialized successfully"));
    // Configure BME280 for weather monitoring
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,     // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,      // Temperature oversampling
                    Adafruit_BME280::SAMPLING_X16,     // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X1,      // Humidity oversampling
                    Adafruit_BME280::FILTER_X16,       // Filtering
                    Adafruit_BME280::STANDBY_MS_500);  // Standby time
  }

  delay(1000);

  Serial.println(F("Starting AS5600 initialization..."));

  // Initialize AS5600 (Wind Direction)
  if (!as5600.begin(AS5600_ADDRESS)) {
    Serial.println(F("AS5600 initialization failed! Check wiring."));
    blinkLED(5);  // Medium blink indicates sensor error
    // Continue anyway - will retry in loop
  } else {
    Serial.println(F("AS5600 initialized successfully"));
    // Check if magnet is detected
    if (!as5600.isMagnetDetected()) {
      Serial.println(F("Warning: AS5600 magnet not detected!"));
    }
  }

    delay(1000);

  // Initialize Wind Speed analog pin
  pinMode(WIND_SPEED_PIN, INPUT);
  
  Serial.println(F("Setup complete. Starting transmission loop..."));
  blinkLED(3);  // Success indicator
}

void loop() {
  unsigned long currentTime = millis();
  
  // Read sensors and transmit at configured interval
  if (currentTime - lastTransmission >= TRANSMISSION_INTERVAL) {
    SensorData data = readSensors();
    transmitData(data);
    lastTransmission = currentTime;
  }
  
  // Toggle LED to indicate activity
  if (currentTime - lastLEDToggle >= 500) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
    lastLEDToggle = currentTime;
  }
  
  delay(10);  // Small delay to prevent watchdog issues
}

SensorData readSensors() {
  SensorData data;
  
  // Read BME280 sensor
  if (bme.begin(BME280_ADDRESS)) {
    data.temperature = bme.readTemperature();  // Raw temperature in Celsius
    data.pressure = bme.readPressure();        // Raw pressure in Pascals (not hPa)
    data.humidity = bme.readHumidity();        // Raw humidity in %
  } else {
    // Set error values if sensor not available
    data.temperature = -999.0;
    data.pressure = -999.0;
    data.humidity = -999.0;
    Serial.println(F("Warning: BME280 read failed"));
  }
  
  // Read AS5600 (Wind Direction)
  if (as5600.begin()) {
    // Apply calibration offset to raw angle
    int rawAngle = as5600.getRawAngle();
    data.windDirection = (rawAngle + WIND_DIRECTION_OFFSET) % 4096;
  } else {
    // Set error value if sensor not available
    data.windDirection = 0;
    Serial.println(F("Warning: AS5600 read failed"));
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
  data.windSpeed = vin * WIND_SPEED_KOR;  // km/h
  
  return data;
}

void transmitData(SensorData data) {
  // Log sensor data in single line format
  Serial.print(F("Sending: Temp="));
  Serial.print(data.temperature, 2);
  Serial.print(F("C | Press="));
  Serial.print(data.pressure, 1);
  Serial.print(F("Pa | Humid="));
  Serial.print(data.humidity, 1);
  Serial.print(F("% | WindDir="));
  Serial.print(data.windDirection);
  Serial.print(F(" | WindSpd="));
  Serial.print(data.windSpeed, 2);
  Serial.println(F("km/h"));
  
  // Create JSON payload
  StaticJsonDocument<128> doc;  // Reduced size since we're sending less data
  
  doc["temp"] = data.temperature;
  doc["pressure"] = data.pressure;
  doc["humidity"] = data.humidity;
  doc["wind_direction"] = data.windDirection;
  doc["wind_speed"] = data.windSpeed;
  
  // Serialize JSON to string
  char payload[128];
  size_t payloadSize = serializeJson(doc, payload);
  
  Serial.print(F("Payload size: "));
  Serial.print(payloadSize);
  Serial.print(F(" bytes | Content: "));
  Serial.println(payload);

  // Transmit data
  const uint8_t binaryPayloadSize = sizeof(SensorData);
  bool success = false;
  for (int i = 0; i < MAX_RETRIES && !success; i++) {
    radio.stopListening();
    // NOTE: Send compact binary struct instead of JSON string to stay under 32-byte NRF24 payload limit
    success = radio.write(&data, binaryPayloadSize);
    
    if (success) {
      Serial.println(F("✓ Transmitted successfully"));
    } else {
      Serial.print(F("Transmission failed (attempt "));
      Serial.print(i + 1);
      Serial.println(F("), retrying..."));
      delay(100);
    }
  }
  
  if (!success) {
    Serial.println(F("✗ Transmission failed after max retries"));
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

