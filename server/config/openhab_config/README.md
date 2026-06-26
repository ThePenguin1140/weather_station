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
   - `jdbc.persist` → `persistence/jdbc.persist`
   - `jdbc.cfg` → `services/jdbc.cfg`
   - `influxdb.persist` → `persistence/influxdb.persist`
   - `influxdb.cfg` → `services/influxdb.cfg`

4. Restart OpenHAB service:
   ```bash
   sudo systemctl restart openhab
   ```

## Configuration

### Items File (`weather_station.items`)

The items file defines the OpenHAB items that will receive sensor data:

- `WeatherStation_Temperature`: Temperature in °C (Number:Temperature)
- `WeatherStation_Pressure`: Pressure in hPa (Number:Pressure)
- `WeatherStation_Humidity`: Humidity in % (Number:Dimensionless)
- `WeatherStation_AbsoluteHumidity`: Absolute humidity in g/m³ (Number:Dimensionless)
- `WeatherStation_WindDirection`: Wind direction in degrees (Number:Angle)
- `WeatherStation_WindSpeed`: Wind speed in km/h (Number:Speed)
- `WeatherStation_SoilTemperature`: Soil temperature in °C from DS18B20 (Number:Temperature)
- `WeatherStation_SoilMoisture`: Soil moisture, raw ADC 0-1023 (Number:Dimensionless)
- `WeatherStation_Light`: Light level, raw ADS1115 counts (Number:Dimensionless)
- `WeatherStation_UV`: UV level, raw ADS1115 counts (Number:Dimensionless)
- `WeatherStation_Voltage`: Solar battery voltage in V via ADS1115 (Number:ElectricPotential)
- `WeatherStation_Current`: Load current in mA via ADS1115 shunt (Number:ElectricCurrent)
- `WeatherStation_Power`: Derived power draw in W (Number:Power)

**Note**: Items use typed dimensions (e.g., `Number:Temperature`) for OpenHAB 5.0.3 unit support. Items have no channel bindings because the Python receiver updates them directly via REST API.

### Sitemap File (`weather_station.sitemap`)

The sitemap file defines a comprehensive dashboard for displaying weather station data in OpenHAB, including:

- Current conditions display (temperature, humidity, pressure)
- Wind information (speed and direction)
- Historical charts for all sensors (24 hours, 7 days, 30 days)
- Combined multi-sensor charts for correlation analysis

**Access the Dashboard:**

- **Basic UI**: `http://your-openhab:8080/basicui/app?sitemap=weather_station`
- **Main UI**: Create a custom dashboard using the Main UI (see `DASHBOARD_GUIDE.md` for detailed instructions)

**Note**: In OpenHAB 5.0.3, the main UI may not display sitemaps by default. Consider customizing your Overview page instead, or access sitemaps via the Basic UI.

**For detailed dashboard usage and customization, see [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)**

### Rules File (`weather_station.rules`)

Optional automation rules for:

- Logging data updates
- Alerting on extreme values (temperature < -10°C, wind speed > 80 km/h)
- Detecting stale data (no updates in 35 minutes; data normally every 4–30 min)

### Persistence Files (`jdbc.persist` + `influxdb.persist`)

Time series data is stored by **two persistence services running in parallel**:

- **JDBC (SQLite)** — the default service, used for OpenHAB's own historical
  queries (`historicState`, `averageSince`, the stale-data rule, etc.).
- **InfluxDB 2** — feeds the Grafana dashboards (see
  `server/config/grafana/`). The receiver's derived `WeatherStation_AbsoluteHumidity`
  is persisted here too.

RRD4J was removed: it stores `Number:Temperature` and other UoM item types but
the REST query API returns 0 points for them, so all charts were blank. See
`server/INFLUXDB_GRAFANA_PLAN.md` for the migration details.

**Persistence Strategies** (both `jdbc.persist` and `influxdb.persist`):

- `everyChange`: Stores data whenever a value changes (primary for sparse 4–30 min data)
- `everyHour`: Stores data every hour (for daily/weekly trends)

**Accessing Historical Data:**

- **Grafana**: open the Weather Station dashboard at `http://your-openhab:3000`
- **REST API (JDBC)**: `GET /rest/persistence/items/{itemName}?serviceId=jdbc&starttime=...&endtime=...`
- **Rules**: Use `itemName.historicState(timestamp)` or `itemName.averageSince(timestamp)`

**Note**: Install both persistence add-ons via the OpenHAB UI
(Settings → Add-ons → Persistence → **JDBC** and **InfluxDB 2**). The InfluxDB
service additionally needs `services/influxdb.cfg` with a valid token (injected
by `deploy_openhab.py` from `config.json`).

**Verifying Persistence:**

1. After deploying and restarting OpenHAB, wait a few minutes for data to be collected
2. Query historical data via REST API:
   ```bash
   # Get temperature data from the last hour (JDBC service)
   curl "http://localhost:8080/rest/persistence/items/WeatherStation_Temperature?serviceId=jdbc&starttime=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)&endtime=$(date -u +%Y-%m-%dT%H:%M:%S)"
   ```
3. Confirm InfluxDB is receiving points: `sudo grep -i influx /var/log/openhab/openhab.log | tail` should show `Stored 'WeatherStation_Temperature'` entries
4. Open the Grafana dashboard to visualize historical data

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
