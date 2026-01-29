---
name: verify-deployment
description: Verify deployments were successful, check if files were deployed correctly, verify OpenHAB configuration is loaded, and confirm services are running properly. Use when verifying deployments, checking deployment success, or validating system configuration.
---

# Verify Deployment

## Verify Full Deployment

Check that both services are running and files are deployed:

```powershell
# Check service status
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"

# Verify receiver file exists
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/receiver.py"

# Verify OpenHAB items file exists
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
```

Use when: User wants to verify deployment, check if deployment was successful, or confirm files were deployed.

## Verify OpenHAB Configuration

### Check Files Exist
```powershell
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
```

### Test REST API
```powershell
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep WeatherStation_Temperature"
```

### Check for Errors
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '5 minutes ago' | grep -i error"
```

Use when: User wants to verify OpenHAB config, check if items are loaded, or validate OpenHAB setup.

## Verify Receiver Deployment

```powershell
# Check file exists
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/receiver.py"

# Check service is active
ssh -F .ssh/config server-deploy "sudo systemctl is-active weather-station"

# Check recent logs for errors
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 20 --no-pager"
```

Use when: User wants to verify receiver deployment or check receiver service status.

## Initial Setup Verification

Complete system verification:

```powershell
# Check SSH connectivity
ssh -F .ssh/config server-deploy "whoami"

# Check both services
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"

# Verify OpenHAB items file
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"

# Test OpenHAB REST API
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep WeatherStation"
```

Use when: User wants to verify entire system setup, check if everything is configured properly, or validate initial installation.

## Verify Service Health

### Check Service Status
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl status openhab weather-station"
```

### Check Service Logs for Errors
```powershell
# OpenHAB errors
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"

# Receiver errors
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"
```

Use when: User wants to verify services are healthy, check for errors, or validate service operation.

## Verify File Permissions

```powershell
# Check OpenHAB config file permissions
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"

# Test OpenHAB user can read file
ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable' || echo 'Not readable'"
```

Use when: User wants to verify file permissions, check if OpenHAB can read config files, or troubleshoot permission issues.

## Related Documentation

- `server/DEPLOYMENT.md` - Deployment verification procedures
- `server/DEBUGGING.md` - Troubleshooting verification issues
- `server/TESTING_OPENHAB.md` - OpenHAB testing procedures
