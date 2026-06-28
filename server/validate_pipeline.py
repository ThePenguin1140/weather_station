#!/usr/bin/env python3
"""Validate weather station pipeline: OpenHAB item states and freshness."""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).parent / "src" / "config.json"

ITEMS = [
    ("temp", "WeatherStation_Temperature", "°C", -50, 60),
    ("pressure", "WeatherStation_Pressure", "hPa", 800, 1100),
    ("humidity", "WeatherStation_Humidity", "%", 0, 100),
    ("absolute_humidity", "WeatherStation_AbsoluteHumidity", "g/m³", 0, 50),
    ("wind_direction_deg", "WeatherStation_WindDirection", "°", 0, 360),
    ("wind_speed", "WeatherStation_WindSpeed", "km/h", 0, 200),
    ("soil_temp", "WeatherStation_SoilTemperature", "°C", -40, 80),
    ("soil_moisture", "WeatherStation_SoilMoisture", "ADC", 0, 1023),
    ("light", "WeatherStation_Light", "counts", 0, 65535),
    ("uv", "WeatherStation_UV", "counts", 0, 65535),
    ("voltage", "WeatherStation_Voltage", "V", 0, 20),
    ("current", "WeatherStation_Current", "mA", 0, 5000),
    ("power", "WeatherStation_Power", "W", 0, 100),
]

NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def parse_number(state: str):
    if state in ("NULL", "UNDEF", ""):
        return None
    m = NUM_RE.search(state.replace(",", ""))
    return float(m.group()) if m else None


def fetch_item(session, base_url, token, item_name):
    headers = {"Authorization": f"Bearer {token}"}
    r = session.get(f"{base_url}/rest/items/{item_name}", headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    config = load_config()
    base_url = config.get("openhab_url", "http://weatherstation:8080").rstrip("/")
    token = config["openhab_api_token"]
    session = requests.Session()

    print(f"OpenHAB: {base_url}")
    print(f"Checked at: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    print(f"{'Sensor':<22} {'State':<18} {'Numeric':<12} {'Range OK':<10} {'Updated'}")
    print("-" * 85)

    issues = []
    rows = []

    for key, item_name, unit, lo, hi in ITEMS:
        try:
            data = fetch_item(session, base_url, token, item_name)
        except requests.RequestException as exc:
            issues.append(f"{item_name}: API error — {exc}")
            print(f"{key:<22} {'ERROR':<18} {'—':<12} {'—':<10} —")
            continue

        state = data.get("state", "NULL")
        numeric = parse_number(state)
        in_range = "—"
        if numeric is not None and numeric != -999.0:
            in_range = "OK" if lo <= numeric <= hi else "OUT"
            if in_range == "OUT":
                issues.append(f"{item_name}: {numeric} {unit} outside [{lo}, {hi}]")
        elif numeric == -999.0:
            in_range = "SENTINEL"
            issues.append(f"{item_name}: sensor error sentinel (-999)")

        # OpenHAB 4+/5 may expose lastStateChange on item resource
        updated = data.get("lastStateChange") or data.get("timestamp") or "—"
        if updated and updated != "—":
            try:
                if isinstance(updated, (int, float)):
                    ts = datetime.fromtimestamp(updated / 1000, tz=timezone.utc)
                else:
                    ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                age_s = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
                updated = f"{ts.astimezone().strftime('%H:%M:%S')} ({age_s:.0f}s ago)"
                if age_s > 600:
                    issues.append(f"{item_name}: stale ({age_s:.0f}s since last update)")
            except ValueError:
                pass

        rows.append((key, state, numeric, in_range, updated))
        num_str = f"{numeric:.3g}" if numeric is not None else "—"
        print(f"{key:<22} {state:<18} {num_str:<12} {in_range:<10} {updated}")

    print()
    if issues:
        print("Issues:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("All items present and within expected ranges.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
