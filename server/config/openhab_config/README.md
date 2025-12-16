# OpenHAB Configuration Files

This directory contains OpenHAB configuration files for the Weather Station project.

## Installation

### OpenHAB 5.0.3 (openHABian)

1. Deploy files using the deployment script (recommended):
   ```bash
   cd server
   python3 deploy_openhab.py
   ```

2. Or manually copy files to your OpenHAB configuration directory:
   - **OpenHAB 5.x/4.x/3.x**: `$OPENHAB_CONF` (typically `/etc/openhab/`)
   - **OpenHAB 2.x**: `$OPENHAB2_CONF` (typically `/etc/openhab2/`)

3. File locations (relative to `$OPENHAB_CONF`):
   - `weather_station.items` → `items/weather_station.items`
   - `weather_station.sitemap` → `sitemaps/weather_station.sitemap`
   - `weather_station.rules` → `rules/weather_station.rules`

4. Restart OpenHAB service:
   ```bash
   sudo systemctl restart openhab
   ```

## Configuration

### Items File (`weather_station.items`)
The items file defines the OpenHAB items that will receive sensor data:
- `WeatherStation_Temperature`: Temperature in °C (Number:Temperature)
- `WeatherStation_Pressure`: Pressure in hPa (Number:Pressure)
- `WeatherStation_Altitude`: Altitude in meters (Number:Length)
- `WeatherStation_Humidity`: Humidity in % (Number:Dimensionless)
- `WeatherStation_WindDirection`: Wind direction in degrees (Number:Angle)
- `WeatherStation_WindSpeed`: Wind speed in km/h (Number:Speed)

**Note**: Items use typed dimensions (e.g., `Number:Temperature`) for OpenHAB 5.0.3 unit support. Items have no channel bindings because the Python receiver updates them directly via REST API.

### Sitemap File (`weather_station.sitemap`)
The sitemap file defines the UI layout for displaying weather station data in OpenHAB.

**Note**: In OpenHAB 5.0.3, the main UI may not display sitemaps by default. Consider customizing your Overview page instead, or access sitemaps via the Basic UI at `http://your-openhab:8080/basicui/app`.

### Rules File (`weather_station.rules`)
Optional automation rules for:
- Logging data updates
- Alerting on extreme values (temperature < -10°C, wind speed > 80 km/h)
- Detecting stale data (no updates in 10 minutes)

## REST API Integration

The Python receiver (`server/src/receiver.py`) sends data directly to OpenHAB items via REST API:
- URL format: `http://localhost:8080/rest/items/{ItemName}/state`
- Method: PUT
- Data: Sensor value as string

Make sure OpenHAB REST API is enabled (enabled by default in OpenHAB 3/4).

## Testing

Test the REST API connection:
```bash
curl -X PUT --header "Content-Type: text/plain" \
  --data "25.5" \
  http://localhost:8080/rest/items/WeatherStation_Temperature/state
```

Check if the value appears in OpenHAB UI.













