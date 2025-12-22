# Agent Workflow Reference

This guide provides natural language prompt examples and command mappings to help the Cursor AI agent effectively work with the weather station project.

## How to Use This Guide

When working with the Cursor agent, you can use natural language prompts. The agent will map these to the appropriate commands based on the project context defined in `.cursorrules` and the documentation in this repository.

## Deployment Workflows

### Deploy Receiver Code

**Natural Language Prompts**:
- "Deploy the receiver code to the server"
- "Update the receiver application on the Raspberry Pi"
- "Deploy receiver.py changes"

**Agent Actions**:
1. Activate virtual environment: `.\venv\Scripts\Activate.ps1`
2. Run deployment: `python server/deploy_openhab.py --skip-openhab`
3. Verify deployment: Check service status via SSH

**Commands Executed**:
```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --skip-openhab
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
```

### Deploy OpenHAB Configuration

**Natural Language Prompts**:
- "Deploy the OpenHAB configuration files"
- "Update OpenHAB items and rules"
- "Push OpenHAB config to the server"

**Agent Actions**:
1. Activate virtual environment
2. Run deployment with `--skip-receiver` flag
3. Verify files were deployed
4. Check OpenHAB service status

**Commands Executed**:
```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --skip-receiver
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"
```

### Full Deployment

**Natural Language Prompts**:
- "Deploy everything to the server"
- "Do a full deployment"
- "Deploy both OpenHAB config and receiver"

**Agent Actions**:
1. Activate virtual environment
2. Run full deployment
3. Verify both services are running

**Commands Executed**:
```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

### Preview Deployment

**Natural Language Prompts**:
- "Show me what would be deployed"
- "Preview the deployment"
- "Dry run the deployment"

**Agent Actions**:
1. Activate virtual environment
2. Run deployment with `--dry-run` flag

**Commands Executed**:
```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --dry-run
```

## Debugging Workflows

### Check Service Status

**Natural Language Prompts**:
- "Check if the services are running"
- "What's the status of the weather station services?"
- "Are openhab and weather-station services active?"

**Agent Actions**:
1. Check both services via SSH
2. Report status

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
ssh -F .ssh/config server-deploy "sudo systemctl status openhab"
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
```

### View Recent Logs

**Natural Language Prompts**:
- "Show me the recent receiver logs"
- "What errors are in the OpenHAB logs?"
- "Display the last 50 lines of weather-station logs"

**Agent Actions**:
1. Query logs via SSH
2. Filter for errors if requested
3. Display results

**Commands Executed**:
```powershell
# For receiver logs
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50 --no-pager"

# For OpenHAB logs
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab -n 50 --no-pager"

# For errors
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"
```

### Debug Service Not Starting

**Natural Language Prompts**:
- "The weather-station service won't start, help me debug"
- "Service is failing, what's wrong?"
- "Debug why the receiver service isn't running"

**Agent Actions**:
1. Check service status
2. View recent logs
3. Check Python dependencies
4. Suggest fixes based on errors

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 100 --no-pager"
ssh -F .ssh/config server-deploy "cd ~/weather_station/server/src && .venv/bin/python -c 'import pyrf24; print(\"OK\")'"
```

### Debug OpenHAB Not Receiving Data

**Natural Language Prompts**:
- "OpenHAB isn't getting data from the receiver"
- "Items aren't updating in OpenHAB"
- "Debug why OpenHAB isn't receiving sensor data"

**Agent Actions**:
1. Check receiver service status
2. Check receiver logs for transmission errors
3. Test OpenHAB REST API
4. Verify item names match

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl is-active weather-station"
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i error"
ssh -F .ssh/config server-deploy "curl -X PUT http://localhost:8080/rest/items/WeatherStation_Temperature/state -H 'Content-Type: text/plain' -d '25.5'"
```

## Arduino Workflows

### Compile Arduino Sketch

**Natural Language Prompts**:
- "Compile the Arduino sketch"
- "Build the weather station Arduino code"
- "Check if the Arduino code compiles"

**Agent Actions**:
1. Run compile command
2. Report any errors

**Commands Executed**:
```powershell
arduino-cli compile --fqbn arduino:avr:nano client/main
```

### Upload to Arduino

**Natural Language Prompts**:
- "Upload the sketch to the Arduino"
- "Flash the Arduino Nano on COM4"
- "Upload the code to the weather station Arduino"

**Agent Actions**:
1. Compile if needed
2. Upload to COM4
3. Report success or errors

**Commands Executed**:
```powershell
arduino-cli compile --fqbn arduino:avr:nano client/main
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

### Monitor Arduino Serial Output

**Natural Language Prompts**:
- "Show me the Arduino serial output"
- "Monitor the Arduino on COM4"
- "What is the Arduino printing to serial?"

**Agent Actions**:
1. Start serial monitor
2. Display output (or instruct user to view)

**Commands Executed**:
```powershell
arduino-cli monitor -p COM4
```

### Complete Arduino Update Workflow

**Natural Language Prompts**:
- "Update the Arduino code and upload it"
- "Compile and upload the Arduino sketch"
- "Deploy the Arduino changes"

**Agent Actions**:
1. Compile sketch
2. Upload to Arduino
3. Optionally start serial monitor

**Commands Executed**:
```powershell
arduino-cli compile --fqbn arduino:avr:nano client/main
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

## Verification Workflows

### Verify Deployment

**Natural Language Prompts**:
- "Verify the deployment was successful"
- "Check if files were deployed correctly"
- "Confirm the deployment worked"

**Agent Actions**:
1. Check remote files exist
2. Check service status
3. Verify OpenHAB items (if applicable)

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "ls -la ~/weather_station/server/src/receiver.py"
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
```

### Verify OpenHAB Configuration

**Natural Language Prompts**:
- "Check if OpenHAB items are loaded"
- "Verify OpenHAB configuration"
- "Are the weather station items in OpenHAB?"

**Agent Actions**:
1. Check if files exist
2. Test REST API
3. Verify items are accessible

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep WeatherStation_Temperature"
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '5 minutes ago' | grep -i error"
```

## Troubleshooting Workflows

### Service Restart

**Natural Language Prompts**:
- "Restart the weather station service"
- "Restart both services"
- "Reboot the receiver service"

**Agent Actions**:
1. Restart service(s) via SSH
2. Verify service is active after restart

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "sudo systemctl restart weather-station"
ssh -F .ssh/config server-deploy "sleep 2 && sudo systemctl is-active weather-station"
```

### Find Errors in Logs

**Natural Language Prompts**:
- "Find errors in the logs"
- "What errors occurred in the last hour?"
- "Show me any errors from the services"

**Agent Actions**:
1. Search logs for errors
2. Display relevant error messages

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"
ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"
```

### Check File Permissions

**Natural Language Prompts**:
- "Check if OpenHAB can read the config files"
- "Verify file permissions"
- "Are the deployment files readable?"

**Agent Actions**:
1. Check file permissions
2. Test OpenHAB user readability

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "sudo -u openhab test -r /etc/openhab/items/weather_station.items && echo 'Readable' || echo 'Not readable'"
```

## Multi-Step Workflows

### Complete Update Workflow

**Natural Language Prompts**:
- "Update the receiver code, deploy it, and verify it's working"
- "Deploy receiver changes and check the logs"

**Agent Actions**:
1. Activate venv
2. Deploy receiver
3. Check service status
4. View recent logs

**Commands Executed**:
```powershell
.\venv\Scripts\Activate.ps1
python server/deploy_openhab.py --skip-openhab
ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"
ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 20 --no-pager"
```

### Initial Setup Verification

**Natural Language Prompts**:
- "Verify the entire system is set up correctly"
- "Check if everything is configured properly"

**Agent Actions**:
1. Check SSH connectivity
2. Check service status
3. Verify files exist
4. Test OpenHAB REST API

**Commands Executed**:
```powershell
ssh -F .ssh/config server-deploy "whoami"
ssh -F .ssh/config server-deploy "sudo systemctl is-active openhab weather-station"
ssh -F .ssh/config server-deploy "ls -la /etc/openhab/items/weather_station.items"
ssh -F .ssh/config server-deploy "curl -s http://localhost:8080/rest/items | grep WeatherStation"
```

## Context-Aware Workflows

### Agent Should Understand:

1. **Local vs Remote Context**:
   - Local: PowerShell commands, project root directory
   - Remote: Bash commands via SSH, Raspberry Pi

2. **Service Names**:
   - `openhab` - OpenHAB service
   - `weather-station` - Receiver service

3. **File Paths**:
   - Local: `server/src/receiver.py`, `client/main/main.ino`
   - Remote: `~/weather_station/server/src/receiver.py`, `/etc/openhab/items/`

4. **SSH Configuration**:
   - Use `server-deploy` host for deployments
   - Use `-F .ssh/config` flag for SSH commands

5. **Virtual Environment**:
   - Always activate before Python commands: `.\venv\Scripts\Activate.ps1`

6. **Arduino Configuration**:
   - Port: COM4
   - FQBN: arduino:avr:nano
   - Sketch: client/main

## Error Handling Patterns

When the agent encounters errors, it should:

1. **Show the error message** clearly
2. **Suggest common fixes** based on error type
3. **Reference relevant documentation**:
   - Deployment issues → `server/DEPLOYMENT.md`
   - Debugging issues → `server/DEBUGGING.md`
   - Arduino issues → `client/ARDUINO_CLI.md` or `client/UPLOAD_TROUBLESHOOTING.md`
4. **Provide next steps** to resolve the issue

## Example Agent Interactions

### Example 1: User asks to deploy receiver

**User**: "Deploy the receiver code"

**Agent Response**:
1. "I'll deploy the receiver code to the server. Let me activate the virtual environment and run the deployment."
2. Executes: `.\venv\Scripts\Activate.ps1`
3. Executes: `python server/deploy_openhab.py --skip-openhab`
4. "Deployment complete. Let me verify the service is running."
5. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"`
6. Reports status to user

### Example 2: User reports service not working

**User**: "The weather-station service isn't working"

**Agent Response**:
1. "Let me check the service status and recent logs to diagnose the issue."
2. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"`
3. Executes: `ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50 --no-pager"`
4. Analyzes output and suggests fixes
5. May suggest: "I found [error]. Let me try [fix]. See `server/DEBUGGING.md` for more troubleshooting steps."

### Example 3: User wants to update Arduino

**User**: "Upload the latest Arduino code"

**Agent Response**:
1. "I'll compile and upload the Arduino sketch to COM4."
2. Executes: `arduino-cli compile --fqbn arduino:avr:nano client/main`
3. If compile succeeds: Executes `arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main`
4. If compile fails: Reports errors and suggests fixes
5. Reports success or provides troubleshooting steps

## Related Documentation

- **Cursor Rules**: `.cursorrules` - Project context and agent guidelines (essential reference)
- **Deployment Guide**: `server/DEPLOYMENT.md` - Detailed deployment procedures and options
- **Debugging Guide**: `server/DEBUGGING.md` - Comprehensive debugging procedures and workflows
- **Arduino CLI Guide**: `client/ARDUINO_CLI.md` - Arduino CLI installation and usage
- **Setup Deploy User**: `server/SETUP_DEPLOY_USER.md` - Initial server setup (required before deployments)
- **Monitor Logs**: `server/MONITOR_OPENHAB_LOGS.md` - Detailed log viewing methods
- **Testing OpenHAB**: `server/TESTING_OPENHAB.md` - OpenHAB testing and verification procedures
- **Upload Troubleshooting**: `client/UPLOAD_TROUBLESHOOTING.md` - Arduino upload error solutions

