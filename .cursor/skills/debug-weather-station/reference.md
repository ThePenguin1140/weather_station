# Debugging Reference

## Example Interactions

### Example 1: Service Not Working
**User**: "The weather-station service isn't working"

**Agent Response**:
1. "Let me check the service status and recent logs to diagnose the issue."
2. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl status weather-station"`
3. Executes: `ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station -n 50 --no-pager"`
4. Analyzes output and suggests fixes
5. May suggest: "I found [error]. Let me try [fix]. See `server/DEBUGGING.md` for more troubleshooting steps."

### Example 2: OpenHAB Not Receiving Data
**User**: "OpenHAB isn't getting data from the receiver"

**Agent Response**:
1. "Let me check the receiver service and logs to diagnose why OpenHAB isn't receiving data."
2. Executes: `ssh -F .ssh/config server-deploy "sudo systemctl is-active weather-station"`
3. Executes: `ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '10 minutes ago' | grep -i error"`
4. Executes: `ssh -F .ssh/config server-deploy "curl -X PUT http://localhost:8080/rest/items/WeatherStation_Temperature/state -H 'Content-Type: text/plain' -d '25.5'"`
5. Analyzes results and suggests fixes

### Example 3: Find Errors
**User**: "Find errors in the logs"

**Agent Response**:
1. "I'll search the logs for errors from both services."
2. Executes: `ssh -F .ssh/config server-deploy "sudo journalctl -u weather-station --since '1 hour ago' | grep -i error"`
3. Executes: `ssh -F .ssh/config server-deploy "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"`
4. Displays relevant error messages
5. Suggests fixes based on errors found
