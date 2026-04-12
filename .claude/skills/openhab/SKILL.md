---
name: openhab
description: Query and interact with the OpenHAB weather station server via REST API. Use this skill whenever the user asks about sensor readings, current weather data, historical values, min/max/averages, persistence data, item states, voltage readings, temperature, pressure, humidity, wind speed, wind direction, light level, or anything related to the OpenHAB server running on the weather station. Also use when checking if data is arriving at OpenHAB, validating the receiver pipeline, or troubleshooting the server. Trigger even if the user just says "what's the current temp" or "show me the last few readings" — this is the right tool.
---

# OpenHAB Weather Station Skill

This skill handles all interactions with the OpenHAB REST API running on the weather station server.

## Setup

**Config file**: `/mnt/f/Projects/weather_station/server/src/config.json`

Always read the API token from config before making requests:

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/mnt/f/Projects/weather_station/server/src/config.json'))['openhab_api_token'])")
BASE="http://weatherstation:8080"
```

All requests need this header: `Authorization: Bearer $TOKEN`

## Weather Station Items

| Key | OpenHAB Item | Unit |
|-----|-------------|------|
| Temperature | `WeatherStation_Temperature` | °C |
| Pressure | `WeatherStation_Pressure` | hPa |
| Altitude | `WeatherStation_Altitude` | m |
| Humidity | `WeatherStation_Humidity` | % |
| Wind Direction | `WeatherStation_WindDirection` | ° |
| Wind Speed | `WeatherStation_WindSpeed` | km/h |
| Voltage | `WeatherStation_Voltage` | V |
| Light Level | `WeatherStation_Light` | ADC 0–1023 |

## Common Operations

### Get current state of all items

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/mnt/f/Projects/weather_station/server/src/config.json'))['openhab_api_token'])")
BASE="http://weatherstation:8080"

for item in WeatherStation_Temperature WeatherStation_Pressure WeatherStation_Humidity WeatherStation_WindDirection WeatherStation_WindSpeed WeatherStation_Voltage WeatherStation_Light WeatherStation_Altitude; do
  state=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/rest/items/$item/state")
  echo "$item: $state"
done
```

### Get current state of a single item

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/rest/items/WeatherStation_Temperature/state"
```

### Query historical data (last N distinct readings)

RRD4J consolidates to 1-minute intervals, so filter for distinct value changes to find actual Arduino transmissions (~5 min apart).

```bash
# Get last 2 hours of data and extract last 10 distinct readings
START=$(( $(date +%s%3N) - 2*60*60*1000 ))
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE/rest/persistence/items/WeatherStation_Temperature?serviceId=rrd4j&starttime=${START}" \
  | python3 -c "
import json, sys
from datetime import datetime, timezone
data = json.load(sys.stdin)
prev = None
distinct = []
for e in data['data']:
    val = round(float(e['state']), 3)
    if val != prev:
        ts = datetime.fromtimestamp(e['time']/1000, tz=timezone.utc).astimezone()
        distinct.append((ts.strftime('%Y-%m-%d %H:%M:%S %Z'), val))
        prev = val
for ts, val in distinct[-10:]:
    print(f'  {ts}  {val}')
"
```

### Get min, max, and average over a time range

The persistence API supports aggregate queries directly:

```bash
START=$(( $(date +%s%3N) - 24*60*60*1000 ))  # last 24 hours
END=$(date +%s%3N)

for item in WeatherStation_Temperature WeatherStation_Pressure WeatherStation_Humidity WeatherStation_WindSpeed WeatherStation_Voltage WeatherStation_Light; do
  result=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$BASE/rest/persistence/items/$item?serviceId=rrd4j&starttime=${START}&endtime=${END}")
  python3 -c "
import json, sys
data = json.loads('$result'.replace(\"'\", '\"')) if False else $(echo $result | python3 -c 'import json,sys; d=json.load(sys.stdin); vals=[float(e[\"state\"]) for e in d[\"data\"]]; print(json.dumps({\"item\": d[\"name\"], \"min\": min(vals), \"max\": max(vals), \"avg\": sum(vals)/len(vals), \"count\": len(vals)}) if vals else json.dumps({\"item\": d[\"name\"], \"error\": \"no data\"}))')
" 2>/dev/null || true
done
```

Use this cleaner approach for min/max/avg across all items:

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/mnt/f/Projects/weather_station/server/src/config.json'))['openhab_api_token'])")
BASE="http://weatherstation:8080"
START=$(( $(date +%s%3N) - 24*60*60*1000 ))

python3 << 'EOF'
import json, subprocess, sys
from datetime import datetime, timezone

config = json.load(open('/mnt/f/Projects/weather_station/server/src/config.json'))
token = config['openhab_api_token']
base = "http://weatherstation:8080"
start = __import__('time').time_ns() // 1_000_000 - 24*60*60*1000

items = [
    ("Temperature", "WeatherStation_Temperature", "°C"),
    ("Pressure",    "WeatherStation_Pressure",    "hPa"),
    ("Humidity",    "WeatherStation_Humidity",    "%"),
    ("Wind Speed",  "WeatherStation_WindSpeed",   "km/h"),
    ("Wind Dir",    "WeatherStation_WindDirection","°"),
    ("Voltage",     "WeatherStation_Voltage",     "V"),
    ("Light",       "WeatherStation_Light",       "ADC"),
]

import urllib.request
for label, item, unit in items:
    url = f"{base}/rest/persistence/items/{item}?serviceId=rrd4j&starttime={start}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        vals = [float(e['state']) for e in data.get('data', [])]
        if vals:
            print(f"{label:12s}: min={min(vals):.2f}  max={max(vals):.2f}  avg={sum(vals)/len(vals):.2f}  {unit}  ({len(vals)} pts)")
        else:
            print(f"{label:12s}: no data")
    except Exception as e:
        print(f"{label:12s}: error - {e}")
EOF
```

### Check receiver status

```bash
# Check if the receiver process is running on the server
ssh -i /tmp/openhab_key -o StrictHostKeyChecking=no admin@192.168.86.45 \
  "systemctl status weather-station-receiver 2>/dev/null || ps aux | grep receiver | grep -v grep"
```

### Check OpenHAB server health

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/mnt/f/Projects/weather_station/server/src/config.json'))['openhab_api_token'])")
curl -s -H "Authorization: Bearer $TOKEN" "http://weatherstation:8080/rest/" | python3 -m json.tool | head -20
```

### Set an item state manually (for testing)

```bash
curl -s -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" \
  -d "23.5" \
  "$BASE/rest/items/WeatherStation_Temperature/state"
```

## Notes

- The Arduino transmits every ~5 minutes via NRF24L01 → Raspberry Pi receiver → OpenHAB REST API
- RRD4J stores data at 1-minute consolidated intervals; consecutive identical values are normal interpolation
- SSH key for server access: copy `/mnt/f/Projects/weather_station/.ssh/openhab_key` to `/tmp/openhab_key` and `chmod 600` (WSL filesystem permissions issue)
- The persistence API requires auth; item state reads/writes work without auth too but use the token anyway

### Known Issue: RRD4J persistence queries return 0 datapoints for UoM items

`WeatherStation_Temperature`, `WeatherStation_Pressure`, `WeatherStation_Humidity`, `WeatherStation_WindDirection`, and `WeatherStation_WindSpeed` are typed as `Number:Temperature`, `Number:Pressure`, etc. (Unit of Measure types). OpenHAB 5's RRD4J service stores data for these correctly (confirmed in logs) but the REST persistence query API returns 0 datapoints for them. This appears to be an OpenHAB 5 / RRD4J compatibility issue with UoM item types.

**Workaround**: Current state is always available via `/rest/items/{item}/state`. For historical data, only `WeatherStation_Voltage` and `WeatherStation_Light` (typed as `Number:ElectricPotential` and `Number:Dimensionless`) return data from the persistence API. The fix would be to change the affected items to plain `Number` type in `weather_station.items`, but this removes unit-aware formatting.
