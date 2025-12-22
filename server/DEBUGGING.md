# Debugging Guide

This guide provides comprehensive debugging procedures for the weather station system, including local debugging, remote debugging via SSH, and OpenHAB troubleshooting.

## Quick Access

### Server Information
- **Host**: Raspberry Pi 4 Model B
- **SSH Config**: `.ssh/config` (use `server-deploy` host)
- **OpenHAB UI**: http://weatherstation:8080
- **Deployment User**: `openhab-deploy` (via SSH config)
- **Services**: `openhab`, `weather-station`

## Local Debugging (Windows/PowerShell)

### Check Deployment Script Status

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run deployment with dry-run to see what would happen
python server/deploy_openhab.py --dry-run

# Check deployment script logs (if debug logging enabled)
Get-Content .cursor\debug.log -Tail 50
```

### Test SSH Connection

```powershell
# Test basic connectivity
ssh -F .ssh/config server-deploy "echo 'Connected'"

# Test sudo access
ssh -F .ssh/config server-deploy "sudo -n systemctl status openhab"

# Test whoami
ssh -F .ssh/config server-deploy "whoami"
```

Expected output for whoami: `openhab-deploy`

### Verify Local Files

```powershell
# Check deployment script exists
Test-Path server/deploy_openhab.py

# Check receiver code exists
Test-Path server/src/receiver.py

# Check OpenHAB config files exist
Test-Path server/config/openhab_config/weather_station.items
Test-Path server/config/openhab_config/weather_station.rules
Test-Path server/config/openhab_config/weather_station.sitemap
Test-Path server/config/openhab_config/rrd4j.persist
```

## Remote Debugging (via SSH)

### Connect to Server

```powershell
# Interactive SSH session
ssh -F .ssh/config server-deploy

# Once connected, you can run commands interactively:
# sudo journalctl -u weather-station -f
# sudo systemctl status openhab
# cd ~/weather_station/server/src
# .venv/bin/python receiver.py
```

### Check Service Status

```powershell
# OpenHAB service
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"

# Weather station receiver service
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"

# Both services at once
ssh -F .ssh/config server-deploy "sudo systemctl status openhab weather-station"

# Check if services are active
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

Expected output: `active` for both services.

### View Service Logs

#### Real-Time Log Monitoring

```powershell
# OpenHAB logs (real-time, press Ctrl+C to stop)
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -f"

# Weather station receiver logs (real-time)
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -f"

# Both services simultaneously
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -u weather-station -f"
```

#### View Recent Logs

```powershell
# Last 100 lines of OpenHAB logs
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -n 100 --no-pager"

# Last 100 lines of receiver logs
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 100 --no-pager"

# Last 50 lines with timestamps
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50"
```

#### Filter Logs by Time

```powershell
# Logs from last hour
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago'"

# Logs from today
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since today"

# Logs from specific time
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '2025-01-15 10:00:00'"
```

#### Search Logs

```powershell
# Search for errors in OpenHAB logs
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"

# Search for errors in receiver logs
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"

# Search for specific text
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station | grep -i 'NRF24L01'"

# Search for warnings
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -p warning --since '1 hour ago'"
```

#### View Logs by Priority

```powershell
# Show only errors
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -p err"

# Show errors and warnings
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -p warning"

# Show all priority levels
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -p debug"
```

### Check File Deployment

```powershell
# Verify OpenHAB config files exist
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/rules/weather_station.rules"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/sitemaps/weather_station.sitemap"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/persistence/rrd4j.persist"

# Verify receiver files exist
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/receiver.py"
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/config.json"

# Check file permissions
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/ | grep weather_station"

# Verify OpenHAB user can read files
ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable' || echo 'Not readable'"
```

### Check OpenHAB Items

```powershell
# List weather station items (requires OpenHAB REST API access)
# Note: May require authentication
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep -i weatherstation"

# Check specific item
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items/WeatherStation_Temperature"
```

### Restart Services

```powershell
# Restart OpenHAB
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab"

# Restart weather station receiver
ssh -F .ssh/config server-deploy "sudo systemctl restart weather-station"

# Restart both
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab weather-station"

# Verify services are active after restart
ssh -F .ssh/config server-deploy "sleep 2 && sudo systemctl is-active openhab weather-station"
```

### Check Python Environment

```powershell
# Verify virtual environment exists
ssh -F .ssh/config server-deploy "test -x ~/weather_station/server/src/.venv/bin/python && echo 'Virtual env exists'"

# Check Python version
ssh -F .ssh/config server-deploy "~/weather_station/server/src/.venv/bin/python --version"

# Test Python imports
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python -c 'import pyrf24; print(\"OK\")'"

# List installed packages
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/pip list"
```

### Manual Receiver Execution

```powershell
# Run receiver manually (for testing)
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python receiver.py"
```

**Note**: Press Ctrl+C to stop. This is useful for testing changes before deploying as a service.

## OpenHAB Web UI Debugging

### Access OpenHAB UI

1. Open browser: http://weatherstation:8080
2. Navigate to **Settings** → **Items**
3. Search for "WeatherStation"
4. Verify items exist and check their states

### Test REST API (from local machine)

```powershell
# Test OpenHAB REST API connectivity
Invoke-WebRequest -Uri "http://weatherstation:8080/rest/items" -Method GET

# Send test data to temperature item
Invoke-WebRequest -Uri "http://weatherstation:8080/rest/items/WeatherStation_Temperature/state" `
    -Method PUT -ContentType "text/plain" -Body "25.5"

# Get item state
Invoke-WebRequest -Uri "http://weatherstation:8080/rest/items/WeatherStation_Temperature/state" -Method GET
```

### Check OpenHAB Logs via UI

1. Open OpenHAB UI: http://weatherstation:8080
2. Navigate to **Settings** → **System Information** → **Logs**
3. Filter by service or search for errors

## Common Debugging Workflows

### Workflow 1: Service Not Starting

**Symptoms**: Service shows as `inactive` or `failed`

**Steps**:
```powershell
# 1. Check service status
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"

# 2. View recent logs
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50 --no-pager"

# 3. Check if Python dependencies are installed
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python -c 'import pyrf24; print(\"OK\")'"

# 4. Try manual execution to see errors
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python receiver.py"
```

**Common Issues**:
- Missing Python dependencies → Re-run deployment
- Configuration errors → Check `config.json`
- Hardware issues → Check NRF24L01 connections
- Permission issues → Check user/group permissions

### Workflow 2: OpenHAB Not Receiving Data

**Symptoms**: Items not updating in OpenHAB UI

**Steps**:
```powershell
# 1. Check receiver is running
ssh -F .ssh/config server-deploy "sudo systemctl is-active weather-station"

# 2. Check receiver logs for errors
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i error"

# 3. Check receiver logs for successful transmissions
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i 'sent\|received'"

# 4. Test OpenHAB REST API from server
ssh -F .ssh/config server-deploy "curl -X PUT http://localhost:8080/rest/items/WeatherStation_Temperature/state -H 'Content-Type: text/plain' -d '25.5'"

# 5. Check OpenHAB logs for REST API calls
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '10 minutes ago' | grep -i rest"
```

**Common Issues**:
- Receiver not running → Restart service
- Network connectivity → Check OpenHAB URL in config.json
- Item name mismatch → Verify item names in config.json
- OpenHAB not running → Check openhab service status

### Workflow 3: Configuration Not Applied

**Symptoms**: Files deployed but OpenHAB doesn't load them

**Steps**:
```powershell
# 1. Verify files were deployed
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"

# 2. Check OpenHAB logs for configuration errors
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '5 minutes ago' | grep -i error"

# 3. Verify OpenHAB can read the files
ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable' || echo 'Not readable'"

# 4. Check file syntax (preview first lines)
ssh -F .ssh/config server-deploy "head -10 /etc/openhab/items/weather_station.items"

# 5. Restart OpenHAB to reload config
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab"

# 6. Check if items are loaded
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep WeatherStation_Temperature"
```

**Common Issues**:
- Syntax errors in config files → Check OpenHAB logs
- Permission issues → Verify file permissions
- Wrong config directory → Check OPENHAB_CONF environment variable
- OpenHAB not reloading → Restart service

### Workflow 4: No Data Received from Arduino

**Symptoms**: Receiver running but no sensor data

**Steps**:
```powershell
# 1. Check receiver logs for radio initialization
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station | grep -i 'NRF24L01\|radio\|initialized'"

# 2. Check for reception messages
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i 'received\|data'"

# 3. Verify radio channel matches (default: 76)
ssh -F .ssh/config server-deploy "grep radio_channel ~/weather_station/server/src/config.json"

# 4. Check hardware connections (if possible via SSH)
# Note: Physical inspection may be required
```

**Common Issues**:
- Radio not initialized → Check NRF24L01 connections
- Channel mismatch → Verify channel in config.json matches Arduino
- Arduino not transmitting → Check Arduino status
- Range issues → NRF24L01 has limited range (~50-100m)

## Using execute_command.py Utility

The `server/execute_command.py` utility provides an alternative way to execute SSH commands:

```powershell
# Execute command on remote server
python server/execute_command.py "sudo systemctl status openhab"

# Use different SSH host
python server/execute_command.py --host server "uptime"

# Show stderr output
python server/execute_command.py --show-stderr "command"

# View logs
python server/execute_command.py "sudo journalctl -u weather-station -n 50"
```

## Log File Locations

### Remote Server Logs
- **OpenHAB**: `/var/log/openhab/openhab.log` (or via `journalctl -u openhab`)
- **Weather Station Receiver**: `~/weather_station/server/src/weather_station.log` (or via `journalctl -u weather-station`)
- **System logs**: `/var/log/syslog`

### Local Logs
- **Deployment script debug logs**: `.cursor/debug.log` (if enabled)

## Quick Reference Commands

### Service Management
```powershell
# Status
ssh -F .ssh/config server-deploy "sudo systemctl status {service}"

# Restart
ssh -F .ssh/config server-deploy "sudo systemctl restart {service}"

# Logs (real-time)
ssh -F .ssh/config server-deploy "sudo journalctl -u {service} -f"

# Logs (last N lines)
ssh -F .ssh/config server-deploy "sudo journalctl -u {service} -n 100 --no-pager"
```

Replace `{service}` with: `openhab` or `weather-station`

### File Verification
```powershell
# Check file exists
ssh -F .ssh/config server-deploy "test -f {path} && echo 'Exists' || echo 'Missing'"

# Check file permissions
ssh -F .ssh/config server-deploy "ls -la {path}"

# Check if readable by OpenHAB user
ssh -F .ssh/config server-deploy "sudo -u openhab test -r {path} && echo 'Readable'"
```

## Related Documentation

- **Deployment Guide**: `server/DEPLOYMENT.md` - Deployment procedures and verification
- **Monitor Logs**: `server/MONITOR_OPENHAB_LOGS.md` - Detailed log viewing guide with additional methods
- **Testing OpenHAB**: `server/TESTING_OPENHAB.md` - OpenHAB testing procedures and REST API examples
- **Setup Deploy User**: `server/SETUP_DEPLOY_USER.md` - Initial server setup and user configuration
- **Agent Workflows**: `AGENT_WORKFLOWS.md` - Natural language prompt examples for debugging tasks
- **Cursor Rules**: `.cursorrules` - Project context and debugging guidelines

