# Weather Station Server (Raspberry Pi)

Python-based receiver for weather station sensor data with OpenHAB integration.

## Prerequisites

- Raspberry Pi (any model with GPIO)
- NRF24L01 module
- Python 3.7 or newer
- OpenHAB installed and running (optional, for visualization)

## Hardware Setup

### NRF24L01 Connections to Raspberry Pi

| NRF24L01 Pin | Raspberry Pi Pin | GPIO Number |
|--------------|------------------|-------------|
| VCC          | 3.3V             | -           |
| GND          | Ground           | -           |
| CE           | GPIO 22          | 22          |
| CSN          | GPIO 8 (CE0)     | 8           |
| SCK          | GPIO 11 (SCLK)   | 11          |
| MOSI         | GPIO 10 (MOSI)   | 10          |
| MISO         | GPIO 9 (MISO)    | 9           |

**Note**: The default configuration uses GPIO 22 for CE and GPIO 0 (CE0) for CSN. Adjust in `config.json` if using different pins.

### Enable SPI

Enable SPI interface on Raspberry Pi:

```bash
sudo raspi-config
```

Navigate to: **Interfacing Options > SPI > Enable**

Or manually edit `/boot/config.txt`:
```
dtparam=spi=on
```

Reboot after enabling SPI.

## Software Installation

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev python3-setuptools
sudo apt-get install -y build-essential
```

### 2. Install Python Dependencies

```bash
cd server
pip3 install -r requirements.txt
```

**Note**: The `pyRF24` library may require additional system libraries. If installation fails, try:

```bash
sudo apt-get install -y libspidev-dev
pip3 install pyRF24
```

### 3. Install OpenHAB (Optional)

If OpenHAB is not already installed:

**Recommended: openHABian**
```bash
# Use openHABian image for Raspberry Pi
# Download from https://www.openhab.org/download/
```

**Alternative: APT package (OpenHAB 5.x)**
```bash
# Add OpenHAB repository
wget -qO - 'https://openhab.jfrog.io/artifactory/api/gpg/key/public' | sudo gpg --dearmor -o /usr/share/keyrings/openhab.gpg
echo 'deb [signed-by=/usr/share/keyrings/openhab.gpg] https://openhab.jfrog.io/artifactory/openhab-linuxpkg stable main' | sudo tee /etc/apt/sources.list.d/openhab.list

# Install OpenHAB
sudo apt-get update
sudo apt-get install openhab
sudo systemctl enable openhab
sudo systemctl start openhab
```

See [OpenHAB Installation Guide](https://www.openhab.org/docs/installation/) for detailed instructions.

## Configuration

### 1. Edit Configuration File

Edit `src/config.json`:

```json
{
  "radio_ce_pin": 22,
  "radio_csn_pin": 0,
  "radio_channel": 76,
  "openhab_url": "http://localhost:8080",
  "openhab_items": {
    "temp": "WeatherStation_Temperature",
    "pressure": "WeatherStation_Pressure",
    "altitude": "WeatherStation_Altitude",
    "wind_speed": "WeatherStation_WindSpeed"
  }
}
```

**Configuration Options**:
- `radio_ce_pin`: GPIO pin for NRF24L01 CE (default: 22)
- `radio_csn_pin`: GPIO pin for NRF24L01 CSN (default: 0, which is CE0/GPIO 8)
- `radio_channel`: Radio channel (0-125, must match transmitter)
- `openhab_url`: OpenHAB REST API URL
- `openhab_items`: Mapping of sensor keys to OpenHAB item names

### 2. Configure OpenHAB

#### Option A: Use Deployment Script (Recommended)

```bash
cd server
python3 deploy_openhab.py
```

This will automatically deploy configuration files to the correct locations and restart OpenHAB.

#### Option B: Manual Copy

```bash
# For OpenHAB 5.x/4.x/3.x (typical paths)
sudo cp config/openhab_config/weather_station.items /etc/openhab/items/
sudo cp config/openhab_config/weather_station.rules /etc/openhab/rules/
sudo cp config/openhab_config/weather_station.sitemap /etc/openhab/sitemaps/
```

Or add to existing files manually. See [config/openhab_config/README.md](config/openhab_config/README.md) for details.

Restart OpenHAB:
```bash
sudo systemctl restart openhab
```

**Note**: Configuration files are now located directly in `$OPENHAB_CONF/items/`, `$OPENHAB_CONF/rules/`, etc. (not in a `/conf/` subdirectory).

## Running the Receiver

### Manual Execution

```bash
cd server/src
python3 receiver.py
```

Or with custom config:
```bash
python3 receiver.py --config /path/to/config.json
```

### Running as a Service

Create a systemd service file `/etc/systemd/system/weather-station.service`:

```ini
[Unit]
Description=Weather Station Receiver
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/weather_station/server/src
ExecStart=/usr/bin/python3 /home/pi/weather_station/server/src/receiver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable weather-station
sudo systemctl start weather-station
```

Check status:
```bash
sudo systemctl status weather-station
```

View logs:
```bash
sudo journalctl -u weather-station -f
```

## Testing

### 1. Test NRF24L01 Connection

Run the receiver and check for initialization messages:
```bash
python3 receiver.py
```

You should see:
```
INFO - NRF24L01 initialized successfully
INFO - Listening on channel 76
INFO - Starting receiver loop...
```

### 2. Test OpenHAB REST API

Test if OpenHAB is accessible:
```bash
curl http://localhost:8080/rest/items/WeatherStation_Temperature
```

Send test data:
```bash
curl -X PUT --header "Content-Type: text/plain" \
  --data "25.5" \
  http://localhost:8080/rest/items/WeatherStation_Temperature/state
```

### 3. Verify Data Reception

When the Arduino transmitter is running, you should see log messages:
```
INFO - Received sensor data: {'temp': 25.5, 'pressure': 1013.25, ...}
INFO - Data successfully sent to OpenHAB
```

### 4. Check OpenHAB UI

Access OpenHAB UI at `http://raspberry-pi-ip:8080` and verify weather station items are updating.

## Troubleshooting

### NRF24L01 Not Responding

1. **Check SPI is enabled**:
   ```bash
   lsmod | grep spi
   ```
   Should show `spi_bcm2835`.

2. **Check wiring**: Verify all connections, especially power (3.3V, not 5V)

3. **Check GPIO pins**: Verify CE and CSN pins match configuration

4. **Permissions**: Ensure user has GPIO access:
   ```bash
   sudo usermod -a -G gpio $USER
   ```
   Log out and back in.

### No Data Received

1. **Check radio channel**: Must match transmitter (default: 76)

2. **Check radio address**: Must match transmitter (default: "00001")

3. **Check transmitter**: Verify Arduino is powered and transmitting

4. **Check distance**: NRF24L01 range is typically 50-100m line-of-sight

5. **Check logs**: Review `weather_station.log` for errors

### OpenHAB Not Receiving Data

1. **Check OpenHAB is running**:
   ```bash
   sudo systemctl status openhab
   ```

2. **Check REST API**: Test with curl (see Testing section)

3. **Check item names**: Verify item names in `config.json` match OpenHAB items

4. **Check firewall**: Ensure port 8080 is accessible

5. **Check OpenHAB logs**:
   ```bash
   sudo tail -f /var/log/openhab/openhab.log
   ```

### Permission Errors

If you get permission errors accessing GPIO:
```bash
sudo usermod -a -G gpio,spi $USER
```
Log out and back in, or reboot.

## Logging

Logs are written to:
- **File**: `weather_station.log` (in the directory where receiver.py is run)
- **Console**: stdout

Log level can be adjusted in `receiver.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # Change INFO to DEBUG for more details
```

## Performance

- **CPU Usage**: ~1-2% on Raspberry Pi 3/4
- **Memory**: ~20-30MB
- **Network**: Minimal (only REST API calls to OpenHAB)

## Security Considerations

- The receiver runs with user permissions (not root)
- OpenHAB REST API should be secured in production
- Consider using HTTPS for OpenHAB if accessible over network
- Review firewall rules for port 8080

## Alternative: MQTT Integration

To use MQTT instead of REST API:

1. Install MQTT broker (e.g., Mosquitto)
2. Install paho-mqtt: `pip3 install paho-mqtt`
3. Modify `receiver.py` to publish to MQTT instead of REST API
4. Configure OpenHAB MQTT binding

## Support

For issues and questions:
1. Check logs: `weather_station.log` and OpenHAB logs
2. Verify hardware connections
3. Test components individually (SPI, OpenHAB REST API)
4. Review configuration files

