---
name: deploy-weather-station
description: Deploy receiver code and OpenHAB configuration to the Raspberry Pi server. Use when deploying receiver.py changes, updating OpenHAB items/rules/sitemaps, performing full deployments, or previewing deployments with dry-run.
---

# Weather Station Deployment

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

**Verification**:
```powershell
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"
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

- `--skip-receiver`: Skip receiver deployment
- `--skip-openhab`: Skip OpenHAB config deployment
- `--no-restart`: Don't restart services after deployment
- `--dry-run`: Show what would be done without deploying
- `--receiver_config`: Deploy config.json alongside receiver.py
- `--host`: Specify SSH host (default: server-deploy)
- `--remote-dir`: Custom OpenHAB config directory (default: /etc/openhab)

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
