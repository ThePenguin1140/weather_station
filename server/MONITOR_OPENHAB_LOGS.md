# Monitoring OpenHAB Logs via SSH

This guide provides various methods to monitor OpenHAB logs on your weather station server.

## Quick Start

### Real-time Log Monitoring (Most Common)

```bash
# Connect to server
ssh -F server/config/ssh_config server

# Follow OpenHAB logs in real-time
sudo journalctl -u openhab -f
```

Press `Ctrl+C` to stop monitoring.

## Methods

### 1. Using journalctl (Recommended for OpenHAB 3/4)

OpenHAB runs as a systemd service, so `journalctl` is the primary method for viewing logs.

#### Real-time Monitoring
```bash
# Follow logs in real-time (like tail -f)
sudo journalctl -u openhab -f

# Follow with timestamps
sudo journalctl -u openhab -f --since "1 hour ago"
```

#### View Recent Logs
```bash
# Last 100 lines
sudo journalctl -u openhab -n 100

# Last 50 lines with timestamps
sudo journalctl -u openhab -n 50 --no-pager

# Last 1000 lines
sudo journalctl -u openhab -n 1000
```

#### Filter Logs
```bash
# Show only errors
sudo journalctl -u openhab -p err

# Show errors and warnings
sudo journalctl -u openhab -p warning

# Filter by time
sudo journalctl -u openhab --since "2025-12-14 20:00:00"
sudo journalctl -u openhab --since "1 hour ago"
sudo journalctl -u openhab --since today
sudo journalctl -u openhab --since yesterday

# Search for specific text
sudo journalctl -u openhab | grep -i "error"
sudo journalctl -u openhab | grep -i "weather"
```

#### View Logs Since Boot
```bash
sudo journalctl -u openhab -b
```

### 2. Direct Log Files

OpenHAB also writes logs to files in `/var/log/openhab/`:

```bash
# View main log file in real-time
sudo tail -f /var/log/openhab/openhab.log

# View events log
sudo tail -f /var/log/openhab/events.log

# View error log (filtered)
sudo tail -f /var/log/openhab/openhab.log | grep -i error

# View all log files simultaneously
sudo tail -f /var/log/openhab/*.log

# View last 100 lines
sudo tail -n 100 /var/log/openhab/openhab.log

# Search log files
sudo grep -i "error" /var/log/openhab/openhab.log
sudo grep -i "weather" /var/log/openhab/*.log
```

**Note**: Log file locations may vary:
- OpenHAB 3/4: `/var/log/openhab/`
- OpenHAB 2: `/var/log/openhab2/`
- Custom installations: Check `$OPENHAB_USERDATA/logs/`

### 3. Using OpenHAB CLI

If OpenHAB CLI is installed (common on OpenHABian):

```bash
# Tail logs
sudo openhab-cli logs tail

# View logs
sudo openhab-cli logs show

# View last N lines
sudo openhab-cli logs show -n 100
```

### 4. One-liner SSH Commands

You can run log monitoring commands directly without interactive SSH:

```bash
# View last 50 lines
ssh -F server/config/ssh_config server "sudo journalctl -u openhab -n 50 --no-pager"

# Follow logs (will run until interrupted)
ssh -F server/config/ssh_config server "sudo journalctl -u openhab -f"

# Search for errors in last hour
ssh -F server/config/ssh_config server "sudo journalctl -u openhab --since '1 hour ago' | grep -i error"
```

## Useful Commands

### Check OpenHAB Service Status
```bash
sudo systemctl status openhab
```

### Restart OpenHAB
```bash
sudo systemctl restart openhab
```

### View Service Logs Since Last Restart
```bash
sudo journalctl -u openhab --since "10 minutes ago"
```

### Monitor Multiple Services
```bash
# Monitor OpenHAB and related services
sudo journalctl -u openhab -u openhab-addons -f
```

### Export Logs
```bash
# Export logs to file
sudo journalctl -u openhab --since "1 day ago" > openhab_logs.txt

# Export with timestamps
sudo journalctl -u openhab --since "1 day ago" --no-pager > openhab_logs.txt
```

## Troubleshooting

### If journalctl shows "No entries"
- Check if OpenHAB service is running: `sudo systemctl status openhab`
- Verify service name: `systemctl list-units | grep openhab`
- Check if logs are being written: `ls -la /var/log/openhab/`

### If log files don't exist
- OpenHAB may be using a different log location
- Check OpenHAB configuration: `sudo cat /etc/openhab/runtime.cfg` (if exists)
- Check userdata directory: `ls -la /var/lib/openhab/` or `/usr/share/openhab/userdata/logs/`

### Permission Issues
- Use `sudo` for journalctl and log file access
- If using `openhab-deploy` user, you may need sudo access for log viewing

## Tips

1. **Use `-f` flag for real-time monitoring** - This is like `tail -f` and shows new log entries as they appear
2. **Combine with grep** - Filter logs: `sudo journalctl -u openhab -f | grep -i error`
3. **Use time filters** - `--since` and `--until` help narrow down log searches
4. **Save important logs** - Export logs before restarting if troubleshooting issues
5. **Monitor during deployments** - Keep a log window open when deploying config changes

## Example Workflow

```bash
# 1. Connect to server
ssh -F server/config/ssh_config server

# 2. Start monitoring logs in one terminal
sudo journalctl -u openhab -f

# 3. In another terminal, deploy changes
# (from your local machine)
python server/deploy_openhab.py

# 4. Watch the logs for any errors or issues
```



