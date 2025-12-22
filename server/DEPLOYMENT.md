# Deployment Guide

This guide provides step-by-step instructions for deploying the weather station server application and OpenHAB configuration files to the Raspberry Pi.

## Prerequisites

### Local Environment (Windows/PowerShell)

- **Python 3.7+**: Ensure Python is installed and accessible
- **Virtual Environment**: Create and activate a virtual environment (see below)
- **SSH Access**: SSH keys configured in `.ssh/config` (see `server/SETUP_DEPLOY_USER.md`)
- **Required Python Packages**: Installed in virtual environment (see `server/requirements.txt`)

### Remote Server (Raspberry Pi 4 Model B)

- **OpenHAB**: Installed and running (access at http://weatherstation:8080)
- **Deployment User**: `openhab-deploy` user configured with proper permissions
- **Services**: 
  - `openhab` service running
  - `weather-station` service created (see `server/SETUP_DEPLOY_USER.md` Step 7)
- **SSH Access**: Configured via `.ssh/config` using `server-deploy` host

## Quick Start

### Step 1: Activate Virtual Environment

```powershell
# Navigate to project root
cd F:\Projects\weather_station

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

**Note**: If the virtual environment doesn't exist, create it first:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
```

### Step 2: Verify SSH Connection

```powershell
# Test SSH connection to deployment server
ssh -F .ssh/config server-deploy "echo 'Connection successful'"
```

If connection fails, verify:
- SSH keys are in `.ssh/` directory
- `.ssh/config` has correct `server-deploy` host configuration
- Remote server is accessible on the network
- See `server/SETUP_DEPLOY_USER.md` for setup instructions

### Step 3: Deploy Configuration

```powershell
# Full deployment (OpenHAB config + receiver)
python server/deploy_openhab.py
```

This will:
- Deploy OpenHAB configuration files (items, rules, sitemap, persistence)
- Deploy receiver application (`receiver.py`)
- Install/update Python dependencies in remote virtual environment
- Restart `openhab` and `weather-station` services

## Deployment Options

### Deploy Only OpenHAB Configuration

```powershell
python server/deploy_openhab.py --skip-receiver
```

This deploys only:
- `weather_station.items`
- `weather_station.rules`
- `weather_station.sitemap`
- `rrd4j.persist`

And restarts the `openhab` service.

### Deploy Only Receiver Application

```powershell
python server/deploy_openhab.py --skip-openhab
```

This deploys only:
- `receiver.py`
- Python dependencies (in remote venv)
- Restarts the `weather-station` service

### Deploy Receiver Configuration File

By default, `config.json` is NOT deployed. To include it:

```powershell
python server/deploy_openhab.py --receiver_config
```

**Warning**: This will overwrite the remote `config.json`. Ensure local config matches remote requirements.

### Dry Run (Preview Deployment)

See what would be deployed without actually deploying:

```powershell
python server/deploy_openhab.py --dry-run
```

This shows:
- Files that would be deployed
- Remote paths
- Commands that would be executed
- Services that would be restarted

### Deploy Without Restarting Services

```powershell
python server/deploy_openhab.py --no-restart
```

Useful when:
- You want to deploy files but restart services manually
- Testing deployment without affecting running services
- Multiple deployments before restart

### Custom Remote Directory

```powershell
# Use custom OpenHAB config directory
python server/deploy_openhab.py --remote-dir /opt/openhab

# Use custom receiver directory
python server/deploy_openhab.py --receiver-dir ~/custom/path/server/src
```

## Deployment Script Options

The `deploy_openhab.py` script supports the following options:

| Option | Description | Default |
|--------|-------------|---------|
| `--skip-receiver` | Skip receiver deployment | False |
| `--skip-openhab` | Skip OpenHAB config deployment | False |
| `--no-restart` | Don't restart services after deployment | False |
| `--dry-run` | Show what would be done without deploying | False |
| `--receiver_config` | Deploy config.json alongside receiver.py | False |
| `--receiver-dir` | Remote directory for receiver files | `~/weather_station/server/src` |
| `--receiver-service-name` | Name of receiver systemd service | `weather-station` |
| `--remote-dir` | Remote OpenHAB config directory | `/etc/openhab` |
| `--host` | SSH host alias from `.ssh/config` | `server-deploy` |
| `--config-dir` | Local OpenHAB config directory | `server/config/openhab_config` |
| `--ssh-config` | Path to SSH config file | `.ssh/config` |

## Verification Procedures

### Check Deployment Status

After deployment, verify files were deployed correctly:

```powershell
# Check OpenHAB config files
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/rules/weather_station.rules"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/sitemaps/weather_station.sitemap"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/persistence/rrd4j.persist"

# Check receiver files
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/receiver.py"
```

### Check Service Status

```powershell
# Check OpenHAB service
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"

# Check weather station receiver service
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"

# Check both services are active
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

Expected output: `active` for both services.

### Verify OpenHAB Items

Access OpenHAB UI:
1. Open browser: http://weatherstation:8080
2. Navigate to **Settings** → **Items**
3. Search for "WeatherStation"
4. Verify items exist:
   - `WeatherStation_Temperature`
   - `WeatherStation_Pressure`
   - `WeatherStation_Altitude`
   - `WeatherStation_Humidity`
   - `WeatherStation_WindDirection`
   - `WeatherStation_WindSpeed`

### Check Deployment Logs

The deployment script logs to `.cursor/debug.log` (if debug logging is enabled). Check for errors:

```powershell
# View recent deployment logs
Get-Content .cursor\debug.log -Tail 50
```

## Common Deployment Scenarios

### Scenario 1: Initial Deployment

First-time deployment of the entire system:

```powershell
# 1. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 2. Verify SSH connection
ssh -F .ssh/config server-deploy "whoami"

# 3. Full deployment
python server/deploy_openhab.py

# 4. Verify services are running
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

### Scenario 2: Update Receiver Code Only

After modifying `server/src/receiver.py`:

```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --skip-openhab
```

### Scenario 3: Update OpenHAB Configuration Only

After modifying files in `server/config/openhab_config/`:

```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --skip-receiver
```

### Scenario 4: Deploy and Test Without Restart

Deploy files but restart services manually:

```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --no-restart

# Later, restart services manually
ssh -F .ssh/config server-deploy "sudo systemctl restart openhab weather-station"
```

### Scenario 5: Preview Before Deployment

Check what would be deployed:

```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --dry-run
```

## Troubleshooting

### Deployment Fails: SSH Connection Error

**Symptoms**: `Error: Authentication failed` or connection timeout

**Solutions**:
1. Verify SSH keys exist: `Test-Path .ssh/deploy_key`
2. Test SSH connection: `ssh -F .ssh/config server-deploy "echo test"`
3. Check `.ssh/config` has correct `server-deploy` host
4. Verify remote server is accessible: `ping weatherstation` (or IP from config)
5. See `server/SETUP_DEPLOY_USER.md` for SSH setup

### Deployment Fails: Permission Denied

**Symptoms**: `Permission denied` when writing files

**Solutions**:
1. Verify deployment user is in `openhab` group:
   ```powershell
   ssh -F .ssh/config server-deploy "groups"
   ```
2. Check directory permissions:
   ```powershell
   ssh -F .ssh/config server-deploy "ls -ld /etc/openhab/items"
   ```
3. See `server/SETUP_DEPLOY_USER.md` Step 3 for permission setup

### Service Restart Fails

**Symptoms**: `Failed to restart service` error

**Solutions**:
1. Verify service exists:
   ```powershell
   ssh -F .ssh/config server-deploy "sudo systemctl list-units | grep weather-station"
   ```
2. Check sudo permissions:
   ```powershell
   ssh -F .ssh/config server-deploy "sudo -n systemctl restart openhab"
   ```
3. See `server/SETUP_DEPLOY_USER.md` Step 6 for sudoers configuration
4. For `weather-station` service, see Step 7 for service creation

### Files Deployed But Not Visible in OpenHAB

**Symptoms**: Files exist but OpenHAB doesn't load them

**Solutions**:
1. Check file permissions (OpenHAB user must be able to read):
   ```powershell
   ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable'"
   ```
2. Check OpenHAB logs for errors:
   ```powershell
   ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -n 50 | grep -i error"
   ```
3. Verify OpenHAB config directory:
   ```powershell
   ssh -F .ssh/config server-deploy "printenv OPENHAB_CONF"
   ```
4. Restart OpenHAB service:
   ```powershell
   ssh -F .ssh/config server-deploy "sudo systemctl restart openhab"
   ```

### Python Dependencies Not Installing

**Symptoms**: Receiver service fails with import errors

**Solutions**:
1. Check remote virtual environment exists:
   ```powershell
   ssh -F .ssh/config server-deploy "test -x ~/weather_station/server/src/.venv/bin/python && echo 'Exists'"
   ```
2. Verify `python3-venv` package is installed on remote:
   ```powershell
   ssh -F .ssh/config server-deploy "dpkg -l | grep python3-venv"
   ```
3. Check deployment logs for pip install errors
4. Manually install dependencies:
   ```powershell
   ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/pip install -r requirements.txt"
   ```

## Advanced Usage

### Using execute_command.py Utility

The `server/execute_command.py` utility provides an alternative way to execute SSH commands:

```powershell
# Execute command on remote server
python server/execute_command.py "sudo systemctl status openhab"

# Use different SSH host
python server/execute_command.py --host server "uptime"

# Show stderr output
python server/execute_command.py --show-stderr "command"
```

### Custom Deployment Workflow

For complex deployments, you can combine options:

```powershell
# Deploy receiver with config, but don't restart
python server/deploy_openhab.py --skip-openhab --receiver_config --no-restart

# Deploy to custom directories
python server/deploy_openhab.py --remote-dir /opt/openhab --receiver-dir ~/custom/path
```

## Related Documentation

- **Setup Deployment User**: `server/SETUP_DEPLOY_USER.md` - Initial server setup (required before first deployment)
- **Debugging Guide**: `server/DEBUGGING.md` - Comprehensive debugging procedures
- **Monitor Logs**: `server/MONITOR_OPENHAB_LOGS.md` - Detailed log viewing commands and methods
- **Testing OpenHAB**: `server/TESTING_OPENHAB.md` - OpenHAB testing procedures and verification
- **Agent Workflows**: `AGENT_WORKFLOWS.md` - Natural language prompt examples for agent tasks
- **Cursor Rules**: `.cursorrules` - Project context and agent guidelines

## Security Notes

- SSH private keys (`.ssh/*_key`) are in `.gitignore` - never commit them
- Deployment user has limited sudo access (only service restarts)
- Always use `server-deploy` host for deployments (not `server` admin host)
- Verify deployment user permissions before first deployment
- Review `server/SETUP_DEPLOY_USER.md` for security best practices

