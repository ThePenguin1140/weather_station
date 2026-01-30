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
   - `rrd4j.persist` → `persistence/rrd4j.persist`
   - `services/rrd4j.cfg` → `services/rrd4j.cfg`

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

The sitemap file defines a comprehensive dashboard for displaying weather station data in OpenHAB, including:

- Current conditions display (temperature, humidity, pressure, altitude)
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

### Persistence File (`rrd4j.persist`)

Configures time series data storage for all weather station items using RRD4J persistence service. **Tuned for data every 4–30 minutes** (lower-power transmission).

A custom RRD4J datasource in `services/rrd4j.cfg` uses a **60 min heartbeat** so readings up to ~30 min apart are accepted (default RRD4J heartbeat is 10 min and would mark valid readings as missing).

**Persistence Strategies:**

- `everyChange`: Stores data whenever a value changes (primary for sparse 4–30 min data)
- `everyMinute`: Stores data every minute (for consistent time series)
- `everyHour`: Stores data every hour (for daily/weekly trends)
- `everyDay`: Stores data once per day (for long-term storage)

**Accessing Historical Data:**

- **REST API**: `GET /rest/persistence/items/{itemName}?starttime=YYYY-MM-DDTHH:mm:ss&endtime=YYYY-MM-DDTHH:mm:ss`
- **Rules**: Use `itemName.historicState(timestamp)` or `itemName.averageSince(timestamp)`
- **Charts**: Use chart widgets in the OpenHAB UI to visualize historical data

**Note**: RRD4J is included by default in OpenHAB 5.0.3. If persistence is not working, ensure the RRD4J persistence add-on is installed via the OpenHAB UI (Settings → Add-ons → Persistence → RRD4J).

**Verifying Persistence:**

1. After deploying and restarting OpenHAB, wait a few minutes for data to be collected
2. Query historical data via REST API:
   ```bash
   # Get temperature data from the last hour
   curl "http://localhost:8080/rest/persistence/items/WeatherStation_Temperature?starttime=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)&endtime=$(date -u +%Y-%m-%dT%H:%M:%S)"
   ```
3. Check persistence data directory: `/var/lib/openhab/persistence/rrd4j/` (or check OpenHAB logs for the actual location)
4. Create charts in the OpenHAB UI to visualize historical data

**Troubleshooting (existing RRD files):** If items were previously persisted with the default 10 min heartbeat, OpenHAB may keep using those .rrd files. After deploying `services/rrd4j.cfg`, if charts or persistence behave oddly, remove the weather station RRD files and restart OpenHAB so new files are created with the custom datasource:

```bash
sudo systemctl stop openhab
sudo rm /var/lib/openhab/persistence/rrd4j/WeatherStation_*.rrd
sudo systemctl start openhab
```

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
