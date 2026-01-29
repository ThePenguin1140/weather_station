# Deployment Reference

## Context-Aware Information

### Local vs Remote Context
- **Local**: PowerShell commands, project root directory
- **Remote**: Bash commands via SSH, Raspberry Pi

### Service Names
- `openhab` - OpenHAB service
- `weather-station` - Receiver service

### File Paths
- **Local**: `server/src/receiver.py`, `client/main/main.ino`
- **Remote**: `~/weather_station/server/src/receiver.py`, `/etc/openhab/items/`

### SSH Configuration
- Use `server-deploy` host for deployments
- Use `-F .ssh/config` flag for SSH commands

### Virtual Environment
- Always activate before Python commands: `.\venv\Scripts\Activate.ps1`

### Arduino Configuration
- Port: COM4
- FQBN: arduino:avr:nano
- Sketch: client/main

## Example Interactions

### Example 1: Deploy Receiver
**User**: "Deploy the receiver code"

**Agent Response**:
1. "I'll deploy the receiver code to the server. Let me activate the virtual environment and run the deployment."
2. Executes: `.\venv\Scripts\Activate.ps1`
3. Executes: `python server/deploy_openhab.py --skip-openhab`
4. "Deployment complete. Let me verify the service is running."
5. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"`
6. Reports status to user

### Example 2: Deploy OpenHAB Config
**User**: "Update OpenHAB items and rules"

**Agent Response**:
1. "I'll deploy the OpenHAB configuration files."
2. Executes: `.\venv\Scripts\Activate.ps1`
3. Executes: `python server/deploy_openhab.py --skip-receiver`
4. "Deployment complete. Let me verify the files were deployed."
5. Executes: `ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"`
6. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl status openhab"`
7. Reports results to user

### Example 3: Full Deployment
**User**: "Deploy everything to the server"

**Agent Response**:
1. "I'll perform a full deployment of both OpenHAB config and receiver."
2. Executes: `.\venv\Scripts\Activate.ps1`
3. Executes: `python server/deploy_openhab.py`
4. "Deployment complete. Let me verify both services are running."
5. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"`
6. Reports status to user
