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

#### BME280 Sensor
- **VCC**: 3.3V
- **GND**: Ground
- **SDA**: A4 (I2C)
- **SCL**: A5 (I2C)
- **I2C Address**: 0x76 (default, can be 0x77)
- **Note**: BME280 includes temperature, pressure, and humidity sensing

#### AS5600 Sensor (Wind Direction)
- **VCC**: 5V or 3.3V
- **GND**: Ground
- **SDA**: A4 (I2C)
- **SCL**: A5 (I2C)
- **I2C Address**: 0x36 (fixed)
- **Note**: Requires a magnet attached to the wind vane

#### Wind Speed Sensor (anemometer)
- **Signal**: Analog Pin A2 (via R3/R4 = 10.02k/62.0k divider + C2 filter)
- **VCC**: 5V or 3.3V (depending on sensor)
- **GND**: Ground

#### DS18B20 Soil Temperature Sensor
- **Data (DQ)**: Digital Pin D2 (1-Wire, with 4.7k pullup / R6)
- **VDD**: 3.3V/5V
- **GND**: Ground
- **Note**: Schematic labels it DS1820; DallasTemperature handles DS1820/DS18B20/DS18S20

#### Soil Moisture Sensor
- **Signal**: Analog Pin A0 (native ADC, raw 0-1023) — *verify pin against Rev 3 board*
- **VCC**: 5V
- **GND**: Ground

#### ADS1115 4-Channel ADC (Solar Battery Case)
- **SDA**: A4 (I2C, shared bus via J1 connector)
- **SCL**: A5 (I2C)
- **I2C Address**: 0x49
- **ch0 (A0)**: Light sensor (LDR R7)
- **ch1 (A1)**: UV sensor (LM358 amplified)
- **ch2 (A2)**: Solar battery voltage (~3.7V)
- **ch3 (A3)**: Post-shunt node — load current = (ch2 − ch3) / R8 (R8 = 11Ω)

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

2. **Adafruit BME280 Library**
   - Search for "Adafruit BME280"
   - Install latest version (dependencies will install automatically)

3. **Adafruit AS5600 Library**
   - Search for "Adafruit AS5600"
   - Install latest version (dependencies will install automatically)

4. **ArduinoJson** by Benoit Blanchon
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
#define CSN_PIN 8             // NRF24L01 CSN pin
#define LED_PIN 13            // Status LED pin
#define WIND_SPEED_PIN A2     // Wind speed analog pin (native ADC)
#define SOIL_MOISTURE_PIN A0  // Soil moisture analog pin (native ADC) — verify vs board
#define ONE_WIRE_BUS 2        // DS18B20 soil temperature 1-Wire data pin (D2)
#define BME280_ADDRESS 0x76   // BME280 I2C address (0x76 or 0x77)
#define AS5600_ADDRESS 0x36   // AS5600 I2C address (fixed at 0x36)
#define ADS1115_ADDRESS 0x49  // ADS1115 4-channel ADC I2C address
#define CURRENT_SHUNT_R8 11.0 // Current-sense shunt R8 in ohms
#define SLEEP_CYCLES 38       // 38 × 8s watchdog cycles ≈ 5 min between transmissions
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

### BME280 Altitude

The altitude calculation is performed on the receiver side (Raspberry Pi) using pressure readings. The Arduino sends raw pressure in Pascals, and the receiver calculates altitude using the barometric formula.

### AS5600 Wind Direction

The AS5600 provides a raw angle value (0-4095) that represents the magnet position. The receiver converts this to degrees (0-360). Calibration offset can be applied in the Arduino code using `WIND_DIRECTION_OFFSET`.

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

2. **BME280 not found**
   - Check I2C wiring (SDA/SCL)
   - Try changing I2C address (0x76 or 0x77)
   - Verify power supply

3. **AS5600 not found**
   - Check I2C wiring (SDA/SCL)
   - Verify magnet is properly positioned
   - Check I2C address is 0x36

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
- **LED Blink (5 times)**: Sensor initialization failed (BME280, AS5600, ADS1115, or DS18B20)
- **LED Blink (10 times)**: NRF24L01 initialization failed
- **LED Blink (2 times)**: Transmission failed after retries
- **LED Toggle (500ms)**: Normal operation

## Data Format

The transmitter sends a packed binary struct over NRF24L01 (`<iIHHiiHHHHH`, 30 bytes):
- `temperature` (int32, °C × 100) — BME280
- `pressure` (uint32, Pascals) — BME280
- `humidity` (uint16, %) — BME280
- `windDirection` (uint16, degrees 0-359) — AS5600
- `windSpeed` (int32, km/h × 100) — anemometer (A2)
- `soilTemperature` (int32, °C × 100) — DS18B20 (D2)
- `soilMoisture` (uint16, raw ADC 0-1023) — analog (A0)
- `light` (uint16, raw ADS counts) — ADS1115 ch0
- `uv` (uint16, raw ADS counts) — ADS1115 ch1
- `voltage` (uint16, mV) — solar battery via ADS1115 ch2
- `current` (uint16, mA) — load current via ADS1115 ch2−ch3 / R8

**Note**: JSON format is only used for serial debugging output. The actual wireless transmission uses a compact binary struct to stay within the NRF24L01 32-byte payload limit (30 of 32 bytes used).

## Power Consumption

- **Idle**: ~20mA
- **Transmitting**: ~80-120mA
- **Average**: ~30-40mA (with 5s transmission interval)

Use appropriate power supply and consider battery capacity for portable applications.

