---
name: deploy-weather-station
description: Deploy receiver code and OpenHAB configuration to the Raspberry Pi server. Use when deploying receiver.py changes, updating OpenHAB items/rules/sitemaps, performing full deployments, or previewing deployments with dry-run.
---

# Weather Station Deployment

## Deployment Coordination (CRITICAL)

**Only one deploy or service restart on the Pi at a time.** Concurrent `deploy_openhab.py` runs or `systemctl restart` commands cause race conditions (partial writes, conflicting restarts, broken service state).

- **Parent agents**: Serialize all deploy/restart work across subagents. Do not launch parallel subagents that each run deploy or restart commands.
- **Subagents**: Never run `deploy_openhab.py` or `systemctl restart` on `openhab`, `weather-station`, or `grafana-server` unless the parent has confirmed no other deploy/restart is in progress.
- **Batch changes**: If multiple config or code changes are pending, combine them into a single deploy instead of several back-to-back runs.
- **Dry runs are safe**: `--dry-run` does not touch the server and can run in parallel with other read-only checks.

## Quick Start

Always activate the virtual environment before deployment:
```powershell
.\venv\Scripts\Activate.ps1
```

## Deployment Types

### Deploy Receiver Code Only
```powershell
python server/deploy_openhab.py --skip-openhab
```
Use when: User wants to deploy receiver.py changes, update receiver application, or deploy receiver code to server.

**Verification**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
```

### Deploy OpenHAB Configuration Only
```powershell
python server/deploy_openhab.py --skip-receiver
```
Use when: User wants to deploy OpenHAB items, rules, sitemaps, or other OpenHAB config files.

**OpenHAB restart is skipped by default** for config-only deploys. OpenHAB 5 watches `/etc/openhab` and hot-reloads items, rules, sitemaps, persistence, jsondb UI components, and widgets without a full service restart. Add `--restart-openhab` only when changes are not picked up (e.g. `services/*.cfg` add-on config) or for troubleshooting.

**Force OpenHAB restart** (when hot-reload is insufficient):
```powershell
python server/deploy_openhab.py --skip-receiver --restart-openhab
```

**Verification**:
```powershell
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -n 20 --no-pager | grep -i refresh"
```

### Full Deployment
```powershell
python server/deploy_openhab.py
```
Use when: User wants to deploy everything, deploy both OpenHAB config and receiver, or do a complete deployment.

**Verification**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

### Preview Deployment (Dry Run)
```powershell
python server/deploy_openhab.py --dry-run
```
Use when: User wants to see what would be deployed, preview deployment, or do a dry run.

## Deployment Options

- `--skip-receiver`: Skip receiver deployment (OpenHAB restart also skipped by default)
- `--skip-openhab`: Skip OpenHAB config deployment
- `--no-restart`: Don't restart any services (OpenHAB, receiver, Grafana)
- `--restart-openhab`: Force OpenHAB restart after config deploy (overrides config-only default)
- `--dry-run`: Show what would be done without deploying
- `--receiver_config`: Deploy config.json alongside receiver.py
- `--host`: Specify SSH host (default: server-deploy)
- `--remote-dir`: Custom OpenHAB config directory (default: /etc/openhab)

## OpenHAB Hot Reload vs Restart

| File type | Hot reload? | Notes |
|-----------|-------------|-------|
| `*.items`, `*.rules`, `*.sitemap` | Yes | File watcher reloads on save |
| `*.persist` | Yes | Persistence model reloads |
| `jsondb/uicomponents_*.json` | Yes | Main UI pages |
| `ui/widgets/*.yaml` | Yes | Custom widgets |
| `services/*.cfg` | Sometimes | Add-on config may need `--restart-openhab` |
| Receiver code (`receiver.py`) | N/A | Always restart `weather-station` service |

Config-only deploys (`--skip-receiver`) skip OpenHAB restart by default. Use `--restart-openhab` if changes do not appear after deploy.

## Context Information

**Service Names**:
- `openhab` - OpenHAB service
- `weather-station` - Receiver service

**SSH Configuration**:
- Use `server-deploy` host for deployments
- Use `-F .ssh/config` flag for SSH commands

**File Paths**:
- Local: `server/src/receiver.py`, `server/config/openhab_config/`
- Remote: `~/weather_station/server/src/receiver.py`, `/etc/openhab/items/`

## Error Handling

When deployment fails:
1. Show the error message clearly
2. Check SSH connectivity: `ssh -F .ssh/config server-deploy "whoami"`
3. Verify service status
4. Reference `server/DEPLOYMENT.md` for detailed troubleshooting
5. Check logs if services fail to start

## Additional Resources

- For context-aware information and example interactions, see [reference.md](reference.md)
- `server/DEPLOYMENT.md` - Detailed deployment procedures
- `server/SETUP_DEPLOY_USER.md` - Initial server setup (required before first deployment)
