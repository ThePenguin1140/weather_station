# Weather Station Monorepo

A complete weather station system consisting of an Arduino-based sensor transmitter and a Raspberry Pi receiver that displays data in OpenHAB.

## Project Overview

This monorepo contains:
- **Client**: Arduino Nano with NRF24L01, BMP280 sensor, and wind speed sensor
- **Server**: Raspberry Pi Python receiver with OpenHAB integration

## Hardware Components

### Client (Arduino)
- **Microcontroller**: Arduino Nano
- **Wireless Module**: NRF24L01 (2.4GHz SPI)
- **Sensors**:
  - BMP280 (Pressure, Temperature, Altitude via I2C)
  - Wind Speed Sensor (Potentiometer-based, Analog)
- **Power**: 8V input with 3.3V buck converter regulation
- **Status LED**: Visual indication of operation

### Server (Raspberry Pi)
- **Hardware**: Raspberry Pi (any model with GPIO)
- **Wireless Module**: NRF24L01 (2.4GHz SPI)
- **Software**: Python receiver, OpenHAB for visualization

## Project Structure

```
weather_station/
├── client/              # Arduino project
│   ├── main/
│   │   └── main.ino     # Main Arduino sketch
│   ├── libraries/         # Library documentation
│   └── README.md
├── server/              # Raspberry Pi server
│   ├── src/
│   │   ├── receiver.py
│   │   └── config.json
│   ├── config/
│   │   └── openhab_config/
│   ├── requirements.txt
│   └── README.md
└── README.md            # This file
```

## Quick Start

### 1. Client Setup
See [client/README.md](client/README.md) for Arduino setup instructions.

### 2. Server Setup
See [server/README.md](server/README.md) for Raspberry Pi and OpenHAB setup instructions.

## Communication Protocol

- **Wireless Protocol**: NRF24L01 (2.4GHz)
- **Data Format**: JSON
- **Transmission Interval**: 5 seconds (configurable)
- **Channel**: 76 (configurable)

### Data Structure
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

## Features

- Real-time sensor data transmission
- Automatic retry on transmission failure
- Error handling and logging
- OpenHAB integration for visualization
- Configurable transmission intervals
- Status LED indicators

## Documentation

- [Client Documentation](client/README.md) - Arduino setup and configuration
- [Server Documentation](server/README.md) - Raspberry Pi and OpenHAB setup
- [OpenHAB Configuration](server/config/openhab_config/README.md) - OpenHAB setup guide

## License

This project is open source. Feel free to modify and use as needed.

## Credits

- Circuit design: Norbert Wuertz
- Revision: 1.0
- Date: 2025-11-21
