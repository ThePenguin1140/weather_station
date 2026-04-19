# Plan: Add InfluxDB + Grafana Persistence

## Context
RRD4J persistence is broken for UoM items in OpenHAB 5 — data is stored but the REST query API returns 0 points for `Number:Temperature` etc., causing all charts to be blank. InfluxDB replaces it as the time-series backend, Grafana replaces OpenHAB's built-in chart widgets with a dedicated UI that includes native aggregation/smoothing (fixing the noisy wind speed chart). RRD4J will be removed entirely.

---

## Step 1: One-Time Manual Server Setup (not scripted)

Run on the Pi via SSH:
```bash
sudo openhabian-config   # → option 52: InfluxDB + Grafana
```

After install:
1. Open InfluxDB UI at `http://weatherstation:8086`, complete initial setup:
   - Org: `openhab`
   - Bucket: `weatherstation`
   - Generate an All Access token → copy it
2. Install OpenHAB InfluxDB persistence addon: OpenHAB UI → Add-ons → Persistence → InfluxDB 2
3. Add Grafana to the deploy user's sudoers (see Step 5)

---

## Step 2: New Config Files

### `server/config/openhab_config/influxdb.cfg`
```
url=http://localhost:8086
token=PLACEHOLDER_REPLACE_WITH_TOKEN
organization=openhab
bucket=weatherstation
```
Token is populated by the deploy script from `config.json` (see Step 4).

### `server/config/openhab_config/influxdb.persist`
```
Strategies {
    everyHour : "0 0 * * * ?"
    default = everyChange
}
Items {
    WeatherStation_* : strategy = everyChange, everyHour
}
```
Wildcards work in OpenHAB persist files and cover all 7+ items cleanly.

### `server/config/grafana/provisioning/datasources/influxdb.yaml`
Grafana datasource config. Token injected by deploy script at deploy time.
```yaml
apiVersion: 1
datasources:
  - name: InfluxDB
    type: influxdb
    url: http://localhost:8086
    jsonData:
      version: Flux
      organization: openhab
      defaultBucket: weatherstation
    secureJsonData:
      token: PLACEHOLDER_REPLACE_WITH_TOKEN
```

### `server/config/grafana/provisioning/dashboards/provider.yaml`
```yaml
apiVersion: 1
providers:
  - name: Weather Station
    folder: Weather Station
    type: file
    options:
      path: /etc/grafana/dashboards
```

### `server/config/grafana/dashboards/weather_station.json`
Pre-built Grafana dashboard JSON with panels for all 7 metrics. Wind speed panel uses:
```flux
aggregateWindow(every: 5m, fn: mean, createEmpty: false)
```
Other panels use raw data (or same 5m smoothing where appropriate). Dashboard includes
a variable for the time range. All panels query the `weatherstation` bucket.

---

## Step 3: Remove RRD4J Files

Delete from repo:
- `server/config/openhab_config/rrd4j.persist`
- `server/config/openhab_config/services/rrd4j.cfg`

---

## Step 4: Update `config.json` Schema

Add InfluxDB credentials to `server/src/config.json`:
```json
{
  "openhab_api_token": "...",
  "influxdb_token": "PLACEHOLDER_REPLACE_WITH_TOKEN",
  "influxdb_org": "openhab",
  "influxdb_bucket": "weatherstation"
}
```

---

## Step 5: Modify `server/deploy_openhab.py`

**File mapping changes** (in both dry-run and live `file_map` dicts, lines ~432-435 and ~597-599):
- Remove: `rrd4j.persist` and `services/rrd4j.cfg` entries
- Add: `influxdb.persist` → `{actual_config_base}/persistence/influxdb.persist`
- Add: `influxdb.cfg` → `{actual_config_base}/services/influxdb.cfg` (token substituted from config.json before upload)

**New `deploy_grafana(ssh, config, project_root, dry_run, restart_service)` function**:
1. Read token from `config.json`
2. For each Grafana file:
   - Read local file, substitute `PLACEHOLDER_REPLACE_WITH_TOKEN` with real token
   - Write to temp file, SCP to server (`/etc/grafana/provisioning/datasources/`, `/etc/grafana/provisioning/dashboards/`, `/etc/grafana/dashboards/`)
3. If not dry_run: `sudo systemctl restart grafana-server`
4. Print status similar to existing deployment output

**Wire into `deploy_files()`**:
- Add `--skip-grafana` CLI flag (default: deploy Grafana)
- Call `deploy_grafana()` after OpenHAB config deployment

**Token substitution for `influxdb.cfg`**:
Same pattern as above — read file, substitute placeholder, SCP the substituted content.

---

## Step 6: Update `server/SETUP_DEPLOY_USER.md`

Add step to extend sudoers for the deploy user:
```
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart grafana-server
openhab-deploy ALL=(ALL) NOPASSWD: /bin/systemctl is-active grafana-server
```
Also document: how to get the InfluxDB token and where to put it in config.json.

---

## Files Modified / Created

| Action | Path |
|--------|------|
| CREATE | `server/config/openhab_config/influxdb.cfg` |
| CREATE | `server/config/openhab_config/influxdb.persist` |
| CREATE | `server/config/grafana/provisioning/datasources/influxdb.yaml` |
| CREATE | `server/config/grafana/provisioning/dashboards/provider.yaml` |
| CREATE | `server/config/grafana/dashboards/weather_station.json` |
| MODIFY | `server/deploy_openhab.py` |
| MODIFY | `server/src/config.json` |
| MODIFY | `server/SETUP_DEPLOY_USER.md` |
| DELETE | `server/config/openhab_config/rrd4j.persist` |
| DELETE | `server/config/openhab_config/services/rrd4j.cfg` |

---

## Verification

1. `python deploy_openhab.py --dry-run` — verify InfluxDB files appear, RRD4J files don't
2. Manual: run openHABian option 52, set up InfluxDB bucket/token, update `config.json`
3. `python deploy_openhab.py` — deploy all files, restart OpenHAB + Grafana
4. Check OpenHAB logs: `sudo grep -i influx /var/log/openhab/openhab.log | tail -20` — should show "Stored 'WeatherStation_Temperature'" entries
5. Open `http://weatherstation:3000` → Weather Station dashboard should appear provisioned
6. Verify wind speed panel shows smoothed 5-minute averages (not raw noisy readings)
7. Verify temperature, pressure, humidity panels all show data (the fix for the UoM bug)
