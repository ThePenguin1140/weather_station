---
name: debug-weather-station
description: Debug and troubleshoot weather station services, check service status, view logs, diagnose service failures, and troubleshoot OpenHAB data reception issues. Use when services aren't working, debugging service issues, checking logs, or troubleshooting data flow problems.
---

# Weather Station Debugging

## Service Status Checks

### Check Both Services
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

### Check Individual Services
```powershell
# OpenHAB service
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"

# Weather station receiver service
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
```

Use when: User asks about service status, wants to check if services are running, or needs to verify service health.

## Viewing Logs

### Recent Receiver Logs
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50 --no-pager"
```

### Recent OpenHAB Logs
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -n 50 --no-pager"
```

### Search for Errors
```powershell
# Receiver errors
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"

# OpenHAB errors
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"
```

Use when: User wants to see recent logs, check for errors, or view service output.

## Debugging Service Not Starting

When a service won't start:

1. **Check service status**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
```

2. **View recent logs**:
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 100 --no-pager"
```

3. **Check Python dependencies**:
```powershell
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python -c 'import pyrf24; print(\"OK\")'"
```

4. **Analyze errors and suggest fixes** based on log output

Use when: User reports service failing, service won't start, or service is not running.

## Debugging OpenHAB Not Receiving Data

When OpenHAB isn't getting data:

1. **Check receiver service status**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl is-active weather-station"
```

2. **Check receiver logs for transmission errors**:
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i error"
```

3. **Test OpenHAB REST API**:
```powershell
ssh -F .ssh/config server-deploy "curl -X PUT http://localhost:8080/rest/items/WeatherStation_Temperature/state -H 'Content-Type: text/plain' -d '25.5'"
```

4. **Verify item names match** between receiver and OpenHAB config

Use when: User reports OpenHAB not receiving data, items aren't updating, or data flow issues.

## Service Restart

### Restart Weather Station Service
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl restart weather-station"
ssh -F .ssh/config server-deploy "sleep 2 && sudo systemctl is-active weather-station"
```

### Restart OpenHAB Service
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab"
ssh -F .ssh/config server-deploy "sleep 2 && sudo systemctl is-active openhab"
```

### Restart Both Services
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab weather-station"
```

Use when: User wants to restart services, reboot services, or restart after configuration changes.

## File Permission Checks

```powershell
# Check file permissions
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"

# Test OpenHAB user readability
ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable' || echo 'Not readable'"
```

Use when: User reports permission issues, OpenHAB can't read config files, or file access problems.

## Error Handling Patterns

When encountering errors:

1. **Show the error message** clearly
2. **Suggest common fixes** based on error type:
   - Service not found → Check service name and deployment
   - Permission denied → Check file permissions and sudo access
   - Connection refused → Check service is running
   - Import errors → Check Python dependencies
3. **Reference relevant documentation**:
   - Deployment issues → `server/DEPLOYMENT.md`
   - Debugging issues → `server/DEBUGGING.md`
4. **Provide next steps** to resolve the issue

## Additional Resources

- For example interactions and troubleshooting patterns, see [reference.md](reference.md)
- `server/DEBUGGING.md` - Comprehensive debugging procedures
- `server/DEPLOYMENT.md` - Deployment troubleshooting
- `server/MONITOR_OPENHAB_LOGS.md` - Detailed log viewing methods
