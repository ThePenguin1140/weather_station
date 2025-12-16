# Weather Station Client (Arduino)

Arduino-based sensor transmitter for the weather station system.

## Hardware Setup

### Pin Connections

#### NRF24L01 Module
- **VCC**: 3.3V (via buck converter)
- **GND**: Ground
- **CE**: Digital Pin 9
- **CSN**: Digital Pin 10
- **SCK**: Digital Pin 13 (SPI)
- **MOSI**: Digital Pin 11 (SPI)
- **MISO**: Digital Pin 12 (SPI)

#### BMP280 Sensor
- **VCC**: 3.3V
- **GND**: Ground
- **SDA**: A4 (I2C)
- **SCL**: A5 (I2C)
- **I2C Address**: 0x76 (default, can be 0x77)

#### Wind Speed Sensor
- **Signal**: Analog Pin A0
- **VCC**: 5V or 3.3V (depending on sensor)
- **GND**: Ground

#### Status LED
- **Anode**: Digital Pin 13 (via resistor)
- **Cathode**: Ground

### Power Supply
- **Input Voltage**: 8V (7-12V range)
- **Buck Converter**: Steps down to 3.3V for NRF24L01 and BMP280
- Ensure adequate current capacity (recommended: 500mA+)

## Software Setup

### Prerequisites
- Arduino IDE (1.8.x or newer, or Arduino IDE 2.0)
- Arduino Nano board support installed

### Library Installation

Install the following libraries via Arduino IDE Library Manager:

1. **RF24** by TMRh20, Avamander
   - Sketch > Include Library > Manage Libraries
   - Search for "RF24"
   - Install latest version

2. **Adafruit BMP280 Library**
   - Search for "Adafruit BMP280"
   - Install latest version (dependencies will install automatically)

3. **ArduinoJson** by Benoit Blanchon
   - Search for "ArduinoJson"
   - Install version 6.x or newer

See [libraries/library_dependencies.txt](libraries/library_dependencies.txt) for detailed instructions.

### Uploading the Sketch

1. Open `main/main.ino` in Arduino IDE
2. Select board: **Tools > Board > Arduino Nano**
3. Select processor: **Tools > Processor > ATmega328P (Old Bootloader)** or **ATmega328P** (try both if one doesn't work)
4. Select port: **Tools > Port > [Your Arduino Port]**
5. Click **Upload**

### Configuration

Edit the following constants in `main.ino` if needed:

```cpp
#define CE_PIN 9              // NRF24L01 CE pin
#define CSN_PIN 10            // NRF24L01 CSN pin
#define LED_PIN 13            // Status LED pin
#define WIND_SPEED_PIN A0     // Wind speed analog pin
#define BMP280_ADDRESS 0x76   // BMP280 I2C address (0x76 or 0x77)
#define TRANSMISSION_INTERVAL 5000  // Milliseconds between transmissions
```

### Radio Configuration

The radio is configured with:
- **Channel**: 76 (0-125 range)
- **Data Rate**: 250KBPS
- **Power Level**: MAX
- **Address**: "00001" (must match receiver)

To change these settings, modify the `setup()` function in the sketch.

## Calibration

### Wind Speed Sensor

The wind speed sensor uses a potentiometer-based design. Calibrate the mapping in the `readSensors()` function:

```cpp
// Current mapping: 0-1023 analog → 0-100 km/h
data.windSpeed = map(data.windSpeedRaw, 0, 1023, 0, 10000) / 100.0;
```

Adjust the range values based on your specific sensor and potentiometer configuration.

### BMP280 Altitude

The altitude calculation uses sea level pressure. Adjust if needed:

```cpp
data.altitude = bmp.readAltitude(1013.25);  // 1013.25 hPa = standard sea level pressure
```

Use your local sea level pressure for more accurate readings.

## Troubleshooting

### Serial Monitor
Open Serial Monitor (Tools > Serial Monitor) at 9600 baud to see debug messages:
- Initialization status
- Transmission confirmations
- Error messages

### Common Issues

1. **NRF24L01 not responding**
   - Check power supply (must be 3.3V, not 5V)
   - Verify SPI connections
   - Check CE and CSN pins

2. **BMP280 not found**
   - Check I2C wiring (SDA/SCL)
   - Try changing I2C address (0x76 or 0x77)
   - Verify power supply

3. **No data received on server**
   - Verify radio channel matches receiver
   - Check radio address matches receiver
   - Ensure both devices are powered
   - Check transmission interval (may be too fast)

4. **LED not blinking**
   - Check LED pin connection
   - Verify LED polarity
   - Check if sketch is running (check Serial Monitor)

## Testing

1. Upload the sketch
2. Open Serial Monitor
3. Verify initialization messages
4. Check for "Transmission successful" messages
5. Verify LED is blinking (indicates activity)

## Status Indicators

- **LED Blink (3 times)**: Successful initialization
- **LED Blink (5 times)**: BMP280 initialization failed
- **LED Blink (10 times)**: NRF24L01 initialization failed
- **LED Blink (2 times)**: Transmission failed after retries
- **LED Toggle (500ms)**: Normal operation

## Data Format

The transmitter sends JSON data:
```json
{
  "temp": 25.5,
  "pressure": 1013.25,
  "altitude": 100.0,
  "wind_speed": 15.5,
  "wind_speed_raw": 158,
  "timestamp": 1234567890
}
```

## Power Consumption

- **Idle**: ~20mA
- **Transmitting**: ~80-120mA
- **Average**: ~30-40mA (with 5s transmission interval)

Use appropriate power supply and consider battery capacity for portable applications.

