# Arduino CLI Guide

This guide provides instructions for using Arduino CLI to compile, upload, and interact with the Arduino Nano weather station client.

## Prerequisites

- **Arduino Nano** connected to computer via USB
- **Windows** operating system (PowerShell)
- **Arduino CLI** installed (see Installation section)
- **COM Port**: COM4 (verify with `arduino-cli board list`)

## Installation

### Install Arduino CLI on Windows

1. **Download Arduino CLI**:
   - Visit: https://arduino.github.io/arduino-cli/latest/installation/
   - Download the Windows 64-bit version
   - Extract to a location in your PATH (e.g., `C:\Program Files\Arduino CLI\`)

2. **Add to PATH** (if not already):
   ```powershell
   # Add Arduino CLI to PATH (adjust path as needed)
   $env:Path += ";C:\Program Files\Arduino CLI"
   ```

3. **Verify Installation**:
   ```powershell
   arduino-cli version
   ```

4. **Initialize Configuration**:
   ```powershell
   arduino-cli config init
   ```

5. **Update Board Index**:
   ```powershell
   arduino-cli core update-index
   ```

6. **Install Arduino AVR Core**:
   ```powershell
   arduino-cli core install arduino:avr
   ```

## Board Configuration

### Detect Connected Boards

```powershell
# List all connected Arduino boards
arduino-cli board list
```

Expected output should show your Arduino Nano on COM4:
```
Port         Type              Board Name              FQBN
COM4         Serial Port       Arduino Nano            arduino:avr:nano
```

### Board Details

```powershell
# Get detailed information about the board
arduino-cli board details -b arduino:avr:nano
```

### Board FQBN

- **FQBN**: `arduino:avr:nano`
- **Port**: `COM4` (verify with `arduino-cli board list`)
- **Processor**: ATmega328P (may need "Old Bootloader" variant)

## Library Management

### Install Required Libraries

The weather station sketch requires these libraries:

```powershell
# Install RF24 library (NRF24L01 wireless module)
arduino-cli lib install "RF24"

# Install Adafruit BME280 Library (pressure/temperature/humidity sensor)
arduino-cli lib install "Adafruit BME280 Library"

# Install Adafruit AS5600 Library (wind direction sensor)
arduino-cli lib install "Adafruit AS5600"

# Install ArduinoJson (JSON serialization)
arduino-cli lib install "ArduinoJson"

# Note: Adafruit BME280 and AS5600 libraries will automatically install dependencies:
# - Adafruit Unified Sensor
# - Adafruit BusIO
```

### List Installed Libraries

```powershell
# List all installed libraries
arduino-cli lib list

# Search for a specific library
arduino-cli lib search "RF24"
```

### Update Libraries

```powershell
# Update library index
arduino-cli lib update-index

# Upgrade all libraries
arduino-cli lib upgrade

# Upgrade specific library
arduino-cli lib upgrade "RF24"
```

## Compiling the Sketch

### Basic Compile

```powershell
# Compile the weather station sketch
arduino-cli compile --fqbn arduino:avr:nano client/main
```

### Compile with Verbose Output

```powershell
# Compile with detailed output
arduino-cli compile --fqbn arduino:avr:nano --verbose client/main
```

### Compile for Old Bootloader

If your Arduino Nano uses the old bootloader:

```powershell
# Compile for old bootloader variant
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old client/main
```

### Common Compile Issues

**Error: Library not found**
- Solution: Install missing library with `arduino-cli lib install "LibraryName"`

**Error: Board not found**
- Solution: Install core with `arduino-cli core install arduino:avr`

**Error: Sketch not found**
- Solution: Verify path to sketch directory (`client/main`)

## Uploading to Arduino

### Basic Upload

```powershell
# Upload compiled sketch to Arduino Nano on COM4
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

### Upload with Verbose Output

```powershell
# Upload with detailed output
arduino-cli upload -p COM4 --fqbn arduino:avr:nano --verbose client/main
```

### Upload for Old Bootloader

```powershell
# Upload for old bootloader variant
arduino-cli upload -p COM4 --fqbn arduino:avr:nano:cpu=atmega328old client/main
```

### Upload Workflow

Complete workflow (compile + upload):

```powershell
# 1. Compile
arduino-cli compile --fqbn arduino:avr:nano client/main

# 2. Upload
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

Or compile and upload in one step:

```powershell
# Compile and upload
arduino-cli compile --fqbn arduino:avr:nano --upload -p COM4 client/main
```

### Common Upload Issues

**Error: Port not found**
- Solution: Verify port with `arduino-cli board list`
- Check Device Manager for COM port
- Try different USB port or cable

**Error: stk500_getsync() - Programmer not responding**
- Solution: See `client/UPLOAD_TROUBLESHOOTING.md` for detailed fixes
- Try "Old Bootloader" variant
- Manual reset during upload

**Error: Permission denied**
- Solution: Close other programs using COM4 (Serial Monitor, Arduino IDE)
- Check if another process has the port open

## Serial Monitoring

### Monitor Serial Output

```powershell
# Monitor serial output from Arduino (9600 baud)
arduino-cli monitor -p COM4

# Monitor with specific baud rate
arduino-cli monitor -p COM4 --config baudrate=9600

# Monitor with timestamp
arduino-cli monitor -p COM4 --timestamp
```

**Note**: Press Ctrl+C to stop monitoring.

### Monitor Configuration

```powershell
# List monitor configurations
arduino-cli monitor -p COM4 --list

# Monitor with custom configuration
arduino-cli monitor -p COM4 --config baudrate=9600 --config line ending=LF
```

## Complete Workflow Examples

### Example 1: First-Time Upload

```powershell
# 1. Verify board is connected
arduino-cli board list

# 2. Install required libraries
arduino-cli lib install "RF24"
arduino-cli lib install "Adafruit BME280 Library"
arduino-cli lib install "Adafruit AS5600"
arduino-cli lib install "ArduinoJson"

# 3. Compile sketch
arduino-cli compile --fqbn arduino:avr:nano client/main

# 4. Upload to Arduino
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main

# 5. Monitor output
arduino-cli monitor -p COM4
```

### Example 2: Quick Update (After Code Changes)

```powershell
# Compile and upload in one command
arduino-cli compile --fqbn arduino:avr:nano --upload -p COM4 client/main
```

### Example 3: Debugging with Serial Monitor

```powershell
# 1. Upload sketch
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main

# 2. Open serial monitor immediately
arduino-cli monitor -p COM4
```

## Troubleshooting

### Board Not Detected

**Symptoms**: `arduino-cli board list` shows no boards

**Solutions**:
1. Check USB cable (use data-capable cable, not charge-only)
2. Check Device Manager for COM port
3. Try different USB port
4. Install CH340/CH341 drivers if needed (common for Nano clones)
5. Close Arduino IDE if open (only one program can access port)

### Upload Fails: stk500_getsync()

**Symptoms**: Upload starts but fails with sync error

**Solutions**:
1. **Try Old Bootloader variant**:
   ```powershell
   arduino-cli upload -p COM4 --fqbn arduino:avr:nano:cpu=atmega328old client/main
   ```

2. **Manual Reset Timing**:
   - Click Upload
   - When "Uploading..." appears, immediately press and release RESET button
   - Upload should proceed

3. **Check Bootloader Selection**:
   - Try both: `arduino:avr:nano` and `arduino:avr:nano:cpu=atmega328old`

4. See `client/UPLOAD_TROUBLESHOOTING.md` for comprehensive troubleshooting

### Compile Errors

**Library Not Found**:
```powershell
# Install missing library
arduino-cli lib install "LibraryName"

# Verify library is installed
arduino-cli lib list | grep "LibraryName"
```

**Board Package Not Found**:
```powershell
# Install Arduino AVR core
arduino-cli core install arduino:avr

# Update core index
arduino-cli core update-index
```

**Sketch Path Error**:
- Verify you're in the project root
- Use relative path: `client/main`
- Or use absolute path: `F:\Projects\weather_station\client\main`

### Serial Monitor Issues

**Port Already in Use**:
- Close other programs using COM4
- Close Arduino IDE Serial Monitor
- Wait a few seconds and try again

**No Output**:
- Verify baud rate matches sketch (default: 9600)
- Check sketch has `Serial.begin(9600)` in setup()
- Verify sketch is actually running (check LED if configured)

## Integration with Existing Documentation

This guide complements the existing troubleshooting documentation:

- **Upload Troubleshooting**: See `client/UPLOAD_TROUBLESHOOTING.md` for detailed upload error solutions
- **Library Dependencies**: See `client/libraries/library_dependencies.txt` for library information
- **Client README**: See `client/README.md` for hardware setup and pin connections

## Quick Reference

### Essential Commands

```powershell
# List boards
arduino-cli board list

# Compile
arduino-cli compile --fqbn arduino:avr:nano client/main

# Upload
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main

# Monitor
arduino-cli monitor -p COM4

# Install library
arduino-cli lib install "LibraryName"
```

### Board FQBN Variants

- **Standard**: `arduino:avr:nano`
- **Old Bootloader**: `arduino:avr:nano:cpu=atmega328old`

### Project Paths

- **Sketch Directory**: `client/main`
- **Sketch File**: `client/main/main.ino`
- **Libraries**: Managed by Arduino CLI (not in project)

## Advanced Usage

### Custom Build Path

```powershell
# Compile to custom build directory
arduino-cli compile --fqbn arduino:avr:nano --build-path ./build client/main
```

### Show Build Properties

```powershell
# Show all build properties for the board
arduino-cli compile --fqbn arduino:avr:nano --show-properties client/main
```

### Verbose Compilation

```powershell
# Show detailed compilation output
arduino-cli compile --fqbn arduino:avr:nano --verbose client/main
```

## Related Documentation

- **Upload Troubleshooting**: `client/UPLOAD_TROUBLESHOOTING.md` - Comprehensive upload error solutions (essential for troubleshooting upload failures)
- **Client README**: `client/README.md` - Hardware setup, pin connections, and configuration
- **Library Dependencies**: `client/libraries/library_dependencies.txt` - Required libraries and installation instructions
- **Agent Workflows**: `AGENT_WORKFLOWS.md` - Natural language prompt examples for Arduino tasks
- **Cursor Rules**: `.cursorrules` - Project context including Arduino configuration

