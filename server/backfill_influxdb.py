#!/usr/bin/env python3
"""
Backfill all weather station items from JDBC persistence into InfluxDB.

Phase 1 — Copy: fetches each item's history from JDBC and writes to InfluxDB.

Phase 2 — Derive: WeatherStation_AbsoluteHumidity is not stored in JDBC, so it
is computed from the already-fetched Temperature and Humidity data using the
August-Roche-Magnus formula (matching receiver.py) and written to BOTH JDBC and
InfluxDB so the two stores stay in sync going forward.

Items (from influxdb.persist):
  WeatherStation_Temperature, WeatherStation_Pressure, WeatherStation_Humidity,
  WeatherStation_WindDirection, WeatherStation_WindSpeed, WeatherStation_Voltage,
  WeatherStation_Light, WeatherStation_AbsoluteHumidity

Usage examples:
  # Dry run — see what would be written
  python backfill_influxdb.py --dry-run

  # Write via OpenHAB persistence REST (requires influxdb addon registered)
  python backfill_influxdb.py --write-via openhab

  # Write directly to InfluxDB API (recommended for large backfills)
  python backfill_influxdb.py --write-via influx-api

  # Last 7 days, specific items only
  python backfill_influxdb.py --days 7 --items WeatherStation_Temperature,WeatherStation_Humidity
"""

import argparse
import bisect
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

TEMP_ITEM = "WeatherStation_Temperature"
HUMIDITY_ITEM = "WeatherStation_Humidity"
ABS_HUMIDITY_ITEM = "WeatherStation_AbsoluteHumidity"

# Items copied directly from JDBC to InfluxDB (AbsoluteHumidity is derived separately).
COPY_ITEMS = [
    "WeatherStation_Temperature",
    "WeatherStation_Pressure",
    "WeatherStation_Humidity",
    "WeatherStation_WindDirection",
    "WeatherStation_WindSpeed",
    "WeatherStation_Voltage",
    "WeatherStation_Light",
]

ALL_ITEMS = COPY_ITEMS + [ABS_HUMIDITY_ITEM]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def parse_numeric_state(state_str: str) -> Optional[float]:
    """Parse OpenHAB state strings like '22.1 °C' or '65.0 %' into floats."""
    if not state_str:
        return None
    number_part = str(state_str).split(" ")[0]
    try:
        return float(number_part)
    except ValueError:
        return None


def fetch_persistence_data(
    base_url: str,
    token: str,
    item: str,
    service_id: str,
    start_epoch_ms: int,
) -> list[dict]:
    """Fetch historical persistence entries for an item."""
    url = (
        f"{base_url}/rest/persistence/items/{item}"
        f"?serviceId={service_id}&starttime={start_epoch_ms}"
    )
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read())
        return payload.get("data", [])
    except urllib.error.HTTPError as err:
        print(
            f"  HTTP {err.code} reading {item} from {service_id}: {err.reason}",
            file=sys.stderr,
        )
        return []
    except Exception as err:
        print(f"  Error reading {item} from {service_id}: {err}", file=sys.stderr)
        return []


def write_persistence_point(
    base_url: str,
    token: str,
    item: str,
    service_id: str,
    epoch_ms: int,
    value: float,
) -> tuple[bool, Optional[str]]:
    """Write one historical point into a persistence service via OpenHAB REST."""
    encoded_value = urllib.parse.quote(str(value), safe="")
    url = (
        f"{base_url}/rest/persistence/items/{item}"
        f"?serviceId={service_id}&time={epoch_ms}&state={encoded_value}"
    )
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, method="PUT", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = resp.status in (200, 201, 202, 204)
            return ok, None if ok else f"HTTP {resp.status} from OpenHAB"
    except urllib.error.HTTPError as err:
        detail = ""
        try:
            detail = err.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        if err.code == 404:
            raise RuntimeError(
                f"Persistence service '{service_id}' not found when writing {item}."
            ) from err
        message = f"HTTP {err.code} {err.reason}"
        if detail:
            message += f" | {detail}"
        return False, message
    except Exception as err:
        return False, str(err)


def resolve_influx_write_url(config: dict, override: Optional[str]) -> str:
    """InfluxDB base URL for /api/v2/write (default: same host as OpenHAB, port 8086)."""
    if override:
        return override.rstrip("/")
    if config.get("influxdb_url"):
        return str(config["influxdb_url"]).rstrip("/")
    oh = config.get("openhab_url", "http://weatherstation:8080")
    u = urlparse(oh)
    host = u.hostname or "localhost"
    scheme = u.scheme or "http"
    return f"{scheme}://{host}:8086"


def influx_write_lines(
    influx_base_url: str,
    token: str,
    org: str,
    bucket: str,
    lines: list[str],
) -> tuple[bool, str]:
    """POST line protocol batch to InfluxDB 2."""
    if not lines:
        return True, ""
    params = urllib.parse.urlencode(
        {"org": org, "bucket": bucket, "precision": "ms"}
    )
    url = f"{influx_base_url.rstrip('/')}/api/v2/write?{params}"
    body = "\n".join(lines).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status in (200, 204):
                return True, ""
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace").strip()
        msg = f"HTTP {err.code} {err.reason}"
        if detail:
            msg += f" | {detail}"
        return False, msg
    except Exception as err:
        return False, str(err)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def copy_item_to_influx(
    item: str,
    points: list[dict],
    args,
    base_url: str,
    token: str,
    influx_write_url: str,
    influx_token: str,
    influx_org: str,
    influx_bucket: str,
) -> tuple[int, int, int, list[str]]:
    """
    Write all valid JDBC points for one item to InfluxDB.

    Returns (written, skipped_invalid, write_errors, error_samples).
    """
    written = 0
    skipped_invalid = 0
    write_errors = 0
    error_samples: list[str] = []
    pending_lines: list[str] = []

    def flush_batch() -> None:
        nonlocal written, write_errors, pending_lines
        if not pending_lines:
            return
        ok, err_msg = influx_write_lines(
            influx_write_url, influx_token, influx_org, influx_bucket, pending_lines
        )
        if ok:
            written += len(pending_lines)
        else:
            write_errors += 1
            if len(error_samples) < 5:
                error_samples.append(f"batch of {len(pending_lines)} lines: {err_msg}")
        pending_lines.clear()

    for i, point in enumerate(points):
        value = parse_numeric_state(point.get("state", ""))
        if value is None:
            skipped_invalid += 1
            continue

        epoch_ms: int = point["time"]

        if args.dry_run:
            written += 1
        elif args.write_via == "influx-api":
            pending_lines.append(f"{item} value={value} {epoch_ms}")
            if len(pending_lines) >= args.batch_size:
                flush_batch()
                time.sleep(0.02)
        else:
            ok, err_msg = write_persistence_point(
                base_url, token, item, args.target_service, epoch_ms, value
            )
            if ok:
                written += 1
            else:
                write_errors += 1
                if len(error_samples) < 5:
                    error_samples.append(
                        f"time={epoch_ms}, value={value}: {err_msg or 'unknown error'}"
                    )
            time.sleep(0.005 if i % 100 != 99 else 0.05)

    if not args.dry_run and args.write_via == "influx-api":
        flush_batch()

    return written, skipped_invalid, write_errors, error_samples


def calculate_absolute_humidity(temp_c: float, relative_humidity_pct: float) -> float:
    """August-Roche-Magnus approximation — matches receiver.py exactly."""
    es = 6.1078 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    return round(216.7 * (relative_humidity_pct / 100.0 * es) / (273.15 + temp_c), 2)


def get_nearest_humidity(
    epoch_ms: int,
    humidity_times: list[int],
    humidity_by_time: dict[int, float],
    tolerance_ms: int,
) -> Optional[float]:
    if not humidity_times:
        return None
    pos = bisect.bisect_left(humidity_times, epoch_ms)
    best_time: Optional[int] = None
    best_delta: Optional[int] = None
    for idx in (pos - 1, pos):
        if 0 <= idx < len(humidity_times):
            delta = abs(humidity_times[idx] - epoch_ms)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_time = humidity_times[idx]
    if best_time is None or best_delta is None or best_delta > tolerance_ms:
        return None
    return humidity_by_time[best_time]


def derive_and_write_abs_humidity(
    temp_points: list[dict],
    humidity_points: list[dict],
    args,
    base_url: str,
    token: str,
    influx_write_url: str,
    influx_token: str,
    influx_org: str,
    influx_bucket: str,
) -> None:
    """
    Phase 2: compute AbsoluteHumidity from Temperature + Humidity and write to
    both JDBC and InfluxDB.
    """
    print(f"[{ABS_HUMIDITY_ITEM}] (derived)")

    humidity_by_time: dict[int, float] = {}
    for point in humidity_points:
        value = parse_numeric_state(point.get("state", ""))
        if value is not None:
            humidity_by_time[point["time"]] = value
    humidity_times = sorted(humidity_by_time.keys())
    tolerance_ms = int(args.tolerance_seconds * 1000)

    computed = 0
    missing_humidity = 0
    invalid_temp = 0

    jdbc_written = 0
    jdbc_errors = 0
    jdbc_error_samples: list[str] = []

    influx_written = 0
    influx_errors = 0
    influx_error_samples: list[str] = []
    pending_lines: list[str] = []

    def flush_influx_batch() -> None:
        nonlocal influx_written, influx_errors, pending_lines
        if not pending_lines:
            return
        ok, err_msg = influx_write_lines(
            influx_write_url, influx_token, influx_org, influx_bucket, pending_lines
        )
        if ok:
            influx_written += len(pending_lines)
        else:
            influx_errors += 1
            if len(influx_error_samples) < 5:
                influx_error_samples.append(f"batch of {len(pending_lines)} lines: {err_msg}")
        pending_lines.clear()

    for i, temp_point in enumerate(temp_points):
        epoch_ms: int = temp_point["time"]
        temp_c = parse_numeric_state(temp_point.get("state", ""))
        if temp_c is None:
            invalid_temp += 1
            continue

        rh = get_nearest_humidity(epoch_ms, humidity_times, humidity_by_time, tolerance_ms)
        if rh is None:
            missing_humidity += 1
            continue

        abs_humidity = calculate_absolute_humidity(temp_c, rh)
        computed += 1

        if args.dry_run:
            jdbc_written += 1
            influx_written += 1
            continue

        # Write to JDBC
        ok, err_msg = write_persistence_point(
            base_url, token, ABS_HUMIDITY_ITEM, args.source_service, epoch_ms, abs_humidity
        )
        if ok:
            jdbc_written += 1
        else:
            jdbc_errors += 1
            if len(jdbc_error_samples) < 5:
                jdbc_error_samples.append(
                    f"time={epoch_ms}, value={abs_humidity}: {err_msg or 'unknown error'}"
                )

        # Write to InfluxDB
        if args.write_via == "influx-api":
            pending_lines.append(f"{ABS_HUMIDITY_ITEM} value={abs_humidity} {epoch_ms}")
            if len(pending_lines) >= args.batch_size:
                flush_influx_batch()
                time.sleep(0.02)
        else:
            ok, err_msg = write_persistence_point(
                base_url, token, ABS_HUMIDITY_ITEM, args.target_service, epoch_ms, abs_humidity
            )
            if ok:
                influx_written += 1
            else:
                influx_errors += 1
                if len(influx_error_samples) < 5:
                    influx_error_samples.append(
                        f"time={epoch_ms}, value={abs_humidity}: {err_msg or 'unknown error'}"
                    )

        time.sleep(0.005 if i % 100 != 99 else 0.05)

    if not args.dry_run and args.write_via == "influx-api":
        flush_influx_batch()

    verb = "Would write" if args.dry_run else "Wrote"
    print(f"  Computed: {computed}  |  Missing humidity match: {missing_humidity}  |  Invalid temp: {invalid_temp}")
    print(f"  JDBC   — {verb}: {jdbc_written}  |  Errors: {jdbc_errors}")
    if jdbc_error_samples:
        for s in jdbc_error_samples:
            print(f"    - {s}")
    print(f"  InfluxDB — {verb}: {influx_written}  |  Errors: {influx_errors}")
    if influx_error_samples:
        for s in influx_error_samples:
            print(f"    - {s}")
    print()

    return jdbc_errors + influx_errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill weather station items from JDBC into InfluxDB. "
            f"{ABS_HUMIDITY_ITEM} is derived from Temperature + Humidity and "
            "written to both JDBC and InfluxDB."
        )
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days back to process (default: 30)",
    )
    parser.add_argument(
        "--config",
        default="src/config.json",
        help="Path to receiver config.json (default: src/config.json)",
    )
    parser.add_argument(
        "--items",
        default=None,
        help=(
            "Comma-separated item names to process (default: all). "
            f"Available: {', '.join(ALL_ITEMS)}"
        ),
    )
    parser.add_argument(
        "--source-service",
        default="jdbc",
        help="Persistence service to read from and write AbsoluteHumidity back to (default: jdbc)",
    )
    parser.add_argument(
        "--target-service",
        default="influxdb",
        help="OpenHAB persistence service id when using --write-via openhab (default: influxdb)",
    )
    parser.add_argument(
        "--write-via",
        choices=("openhab", "influx-api"),
        default="openhab",
        help=(
            "openhab: PUT to OpenHAB persistence REST (needs influxdb addon registered). "
            "influx-api: POST line protocol directly to InfluxDB /api/v2/write."
        ),
    )
    parser.add_argument(
        "--influx-url",
        default=None,
        help="InfluxDB base URL for influx-api (default: influxdb_url from config or openhab host:8086)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=400,
        help="Line-protocol lines per POST when using influx-api (default: 400)",
    )
    parser.add_argument(
        "--tolerance-seconds",
        type=float,
        default=5.0,
        help="Max timestamp gap when matching humidity to temperature for AbsoluteHumidity (default: 5.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and count points but do not write any data",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Config file not found: {args.config}", file=sys.stderr)
        print("Run from `server/` or pass `--config server/src/config.json`.", file=sys.stderr)
        sys.exit(1)

    base_url = config.get("openhab_url", "http://weatherstation:8080").rstrip("/")
    token = config.get("openhab_api_token", "")
    if not token:
        print("Warning: no openhab_api_token found in config.", file=sys.stderr)

    influx_write_url = resolve_influx_write_url(config, args.influx_url)
    influx_token = config.get("influxdb_token", "")
    influx_org = config.get("influxdb_org", "openhab")
    influx_bucket = config.get("influxdb_bucket", "weatherstation")

    if args.write_via == "influx-api" and not args.dry_run:
        if not influx_token or "PLACEHOLDER" in influx_token:
            print(
                "influxdb_token missing or placeholder in config; required for --write-via influx-api.",
                file=sys.stderr,
            )
            sys.exit(1)

    requested = set(args.items.split(",")) if args.items else set(ALL_ITEMS)
    requested = {i.strip() for i in requested}
    copy_items = [i for i in COPY_ITEMS if i in requested]
    do_abs_humidity = ABS_HUMIDITY_ITEM in requested

    start_dt = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    start_epoch_ms = int(start_dt.timestamp() * 1000)

    print(f"Backfilling {'(DRY RUN) ' if args.dry_run else ''}— {len(copy_items)} copy item(s)" + (f" + {ABS_HUMIDITY_ITEM} (derived)" if do_abs_humidity else ""))
    print(f"  Source service: {args.source_service}")
    print(f"  Write via:      {args.write_via}")
    if args.write_via == "openhab":
        print(f"  OH persist id:  {args.target_service}")
    else:
        print(f"  Influx URL:     {influx_write_url}")
        print(f"  Influx bucket:  {influx_bucket} (org={influx_org})")
    print(f"  Range start:    {start_dt.strftime('%Y-%m-%d %H:%M UTC')} ({args.days} days ago)")
    print(f"  OpenHAB:        {base_url}")
    print()

    wall_start = time.time()
    totals = {"fetched": 0, "written": 0, "invalid": 0, "errors": 0}
    fetched_cache: dict[str, list[dict]] = {}

    # Phase 1: copy each item JDBC → InfluxDB
    for item in copy_items:
        print(f"[{item}]")
        points = fetch_persistence_data(
            base_url, token, item, args.source_service, start_epoch_ms
        )
        fetched_cache[item] = points
        print(f"  Fetched {len(points)} points from {args.source_service}")
        totals["fetched"] += len(points)

        if not points:
            print("  Skipping — no data.")
            print()
            continue

        written, skipped_invalid, write_errors, error_samples = copy_item_to_influx(
            item=item,
            points=points,
            args=args,
            base_url=base_url,
            token=token,
            influx_write_url=influx_write_url,
            influx_token=influx_token,
            influx_org=influx_org,
            influx_bucket=influx_bucket,
        )

        verb = "Would write" if args.dry_run else "Wrote"
        print(f"  {verb}: {written}  |  Invalid/skipped: {skipped_invalid}  |  Errors: {write_errors}")
        if error_samples:
            for s in error_samples:
                print(f"    - {s}")

        totals["written"] += written
        totals["invalid"] += skipped_invalid
        totals["errors"] += write_errors
        print()

    # Phase 2: derive and write AbsoluteHumidity to both JDBC and InfluxDB
    if do_abs_humidity:
        temp_points = fetched_cache.get(TEMP_ITEM)
        humidity_points = fetched_cache.get(HUMIDITY_ITEM)

        if temp_points is None:
            print(f"  Fetching {TEMP_ITEM} for AbsoluteHumidity derivation...")
            temp_points = fetch_persistence_data(
                base_url, token, TEMP_ITEM, args.source_service, start_epoch_ms
            )
        if humidity_points is None:
            print(f"  Fetching {HUMIDITY_ITEM} for AbsoluteHumidity derivation...")
            humidity_points = fetch_persistence_data(
                base_url, token, HUMIDITY_ITEM, args.source_service, start_epoch_ms
            )

        if not temp_points or not humidity_points:
            print(f"[{ABS_HUMIDITY_ITEM}] Skipping — missing Temperature or Humidity source data.")
        else:
            abs_errors = derive_and_write_abs_humidity(
                temp_points=temp_points,
                humidity_points=humidity_points,
                args=args,
                base_url=base_url,
                token=token,
                influx_write_url=influx_write_url,
                influx_token=influx_token,
                influx_org=influx_org,
                influx_bucket=influx_bucket,
            )
            totals["errors"] += abs_errors

    elapsed = time.time() - wall_start
    print("=" * 56)
    print(f"Completed in {elapsed:.1f}s")
    verb = "Would write" if args.dry_run else "Wrote"
    print(f"  Copy items processed:  {len(copy_items)}")
    print(f"  Total fetched:         {totals['fetched']}")
    print(f"  {verb}:              {totals['written']}")
    print(f"  Invalid/skipped:       {totals['invalid']}")
    if not args.dry_run:
        print(f"  Write errors:          {totals['errors']}")

    if totals["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
