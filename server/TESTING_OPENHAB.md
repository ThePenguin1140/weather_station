# Testing OpenHAB Weather Station Deployment

This guide covers how to test your OpenHAB weather station configuration after deployment.

## Prerequisites

- OpenHAB is running on your server
- Configuration files have been deployed using `deploy_openhab.py`
- You have SSH access to the OpenHAB server

## 1. Verify Files Were Deployed

SSH into your OpenHAB server and verify the files exist:

```bash
# SSH to your server (using your deploy user or admin)
ssh -i .ssh/openhab_key admin@your-server-ip

# Check if files were deployed correctly
ls -la /etc/openhab/conf/items/weather_station.items
ls -la /etc/openhab/conf/sitemaps/weather_station.sitemap
ls -la /etc/openhab/conf/rules/weather_station.rules
ls -la /etc/openhab/conf/services/openhabian.conf

# Verify file permissions (should be readable by openhab user)
ls -la /etc/openhab/conf/items/ | grep weather_station
```

## 2. Check OpenHAB Service Status

```bash
# Check if OpenHAB service is running
sudo systemctl status openhab

# View recent OpenHAB logs for errors
sudo journalctl -u openhab -n 100 --no-pager

# Or check the OpenHAB log file directly
sudo tail -f /var/log/openhab/openhab.log
```

Look for:
- Configuration errors (syntax issues in items/rules)
- Item loading errors
- Rule compilation errors

## 3. Verify Items Are Loaded

### Option A: Via OpenHAB UI

1. Open OpenHAB UI: `http://your-server-ip:8080`
2. Go to **Settings** → **Items**
3. Search for "WeatherStation" - you should see:
   - `WeatherStation_Temperature`
   - `WeatherStation_Pressure`
   - `WeatherStation_Altitude`
   - `WeatherStation_WindSpeed`
   - `WeatherStation` (group)

### Option B: Via REST API

```bash
# Get all items (requires authentication)
curl -X GET "http://your-server-ip:8080/rest/items" \
  -H "Content-Type: application/json" \
  -u "openhab:your-password" | jq '.[] | select(.name | contains("WeatherStation"))'

# Or check a specific item
curl -X GET "http://your-server-ip:8080/rest/items/WeatherStation_Temperature" \
  -H "Content-Type: application/json" \
  -u "openhab:your-password"
```

### Option C: Via SSH (Karaf Console)

```bash
# SSH to server and access OpenHAB console
ssh -i .ssh/openhab_key admin@your-server-ip
sudo -u openhab /usr/share/openhab/runtime/bin/client

# In the console, type:
openhab:items list | grep WeatherStation
```

## 4. Test REST API Endpoint

Test if you can send data to OpenHAB items via REST API:

```bash
# Test sending temperature data
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_Temperature/state" \
  -H "Content-Type: text/plain" \
  -d "25.5" \
  -u "openhab:your-password"

# Test sending pressure data
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_Pressure/state" \
  -H "Content-Type: text/plain" \
  -d "1013.25" \
  -u "openhab:your-password"

# Test sending altitude data
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_Altitude/state" \
  -H "Content-Type: text/plain" \
  -d "100.0" \
  -u "openhab:your-password"

# Test sending wind speed data
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_WindSpeed/state" \
  -H "Content-Type: text/plain" \
  -d "15.5" \
  -u "openhab:your-password"
```

**Note:** Replace `openhab:your-password` with your actual OpenHAB username and password, or use API tokens if configured.

## 5. View the Sitemap in OpenHAB UI

1. Open OpenHAB UI: `http://your-server-ip:8080`
2. Click on **Sitemaps** in the main menu
3. Look for **"Weather Station"** sitemap
4. Click on it to view the weather station data
5. You should see all four items displayed

If the sitemap doesn't appear:
- Check that the file was deployed correctly
- Verify OpenHAB has reloaded the configuration
- Check logs for sitemap parsing errors

## 6. Test Rules

### Check Rule Status

```bash
# Via Karaf console
sudo -u openhab /usr/share/openhab/runtime/bin/client
openhab:rules list | grep WeatherStation
```

### Trigger Rules Manually

Send test data that should trigger the rules:

```bash
# Trigger "Weather Station Data Received" rule by updating an item
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_Temperature/state" \
  -H "Content-Type: text/plain" \
  -d "25.5" \
  -u "openhab:your-password"

# Check logs for rule execution
sudo journalctl -u openhab -n 50 --no-pager | grep WeatherStation
```

### Test Alert Rules

```bash
# Test low temperature alert (< -10°C)
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_Temperature/state" \
  -H "Content-Type: text/plain" \
  -d "-15.0" \
  -u "openhab:your-password"

# Test high wind speed alert (> 80 km/h)
curl -X PUT "http://your-server-ip:8080/rest/items/WeatherStation_WindSpeed/state" \
  -H "Content-Type: text/plain" \
  -d "85.0" \
  -u "openhab:your-password"

# Check logs for warnings
sudo journalctl -u openhab -n 50 --no-pager | grep -i "warn\|alert"
```

## 7. Test with Python Receiver Script

If your receiver script is running, verify it's sending data:

```bash
# On the server where receiver.py runs, check if it's running
ps aux | grep receiver.py

# Check receiver logs
tail -f weather_station.log

# Verify data is being sent (should see successful REST API calls)
grep "Sent.*to.*WeatherStation" weather_station.log
```

## 8. Monitor Real-Time Updates

### Via OpenHAB UI

1. Open the Weather Station sitemap
2. Watch the values update in real-time as data arrives

### Via REST API (Event Stream)

```bash
# Subscribe to item state changes
curl -N "http://your-server-ip:8080/rest/events?topics=smarthome/items/WeatherStation_Temperature/state" \
  -u "openhab:your-password"
```

### Via Logs

```bash
# Watch OpenHAB logs in real-time
sudo journalctl -u openhab -f | grep WeatherStation
```

## 9. Troubleshooting Common Issues

### Items Not Appearing

- **Check file syntax**: Ensure no JSON/DSL syntax errors
- **Reload items**: In Karaf console: `openhab:items reload`
- **Check permissions**: Files should be readable by `openhab` user
- **Check logs**: Look for item loading errors

### REST API Not Working

- **Check authentication**: Verify username/password or API token
- **Check URL**: Ensure OpenHAB REST API is enabled
- **Check firewall**: Port 8080 should be accessible
- **Test connectivity**: `curl http://your-server-ip:8080/rest/`

### Rules Not Executing

- **Check rule syntax**: Look for compilation errors in logs
- **Verify triggers**: Ensure items are actually updating
- **Check rule status**: Rules might be disabled
- **Enable debug logging**: Set log level to DEBUG for rules

### Sitemap Not Showing

- **Check file location**: Must be in `/etc/openhab/conf/sitemaps/`
- **Check file name**: Must end with `.sitemap`
- **Reload sitemaps**: Restart OpenHAB or reload via console
- **Check UI**: Some UIs require sitemap to be set as default

## 10. Quick Test Script

Create a simple test script to verify everything works:

```bash
#!/bin/bash
# test_openhab.sh

OPENHAB_URL="http://your-server-ip:8080"
AUTH="openhab:your-password"

echo "Testing OpenHAB Weather Station Configuration..."
echo ""

# Test items
echo "1. Testing items..."
curl -s -X GET "$OPENHAB_URL/rest/items/WeatherStation_Temperature" \
  -u "$AUTH" | jq -r '.name' && echo "✓ Temperature item exists" || echo "✗ Temperature item missing"

# Test sending data
echo ""
echo "2. Sending test data..."
curl -s -X PUT "$OPENHAB_URL/rest/items/WeatherStation_Temperature/state" \
  -H "Content-Type: text/plain" \
  -d "22.5" \
  -u "$AUTH" && echo "✓ Temperature updated" || echo "✗ Failed to update temperature"

# Verify data was received
echo ""
echo "3. Verifying data..."
sleep 1
TEMP=$(curl -s -X GET "$OPENHAB_URL/rest/items/WeatherStation_Temperature/state" -u "$AUTH")
echo "Current temperature: $TEMP"

echo ""
echo "Test complete!"
```

Make it executable and run:
```bash
chmod +x test_openhab.sh
./test_openhab.sh
```

## Next Steps

Once testing is complete:
1. Ensure your Python receiver script is running as a service
2. Set up monitoring/alerting for the weather station
3. Configure persistence if you want to store historical data
4. Set up charts/graphs in OpenHAB UI for data visualization



