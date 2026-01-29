---
name: arduino-weather-station
description: Compile, upload, and monitor Arduino sketches for the weather station. Use when compiling Arduino code, uploading sketches to the Arduino Nano, monitoring serial output, or updating Arduino firmware.
---

# Arduino Weather Station Operations

## Arduino Configuration

- **Port**: COM4
- **FQBN**: arduino:avr:nano
- **Sketch Location**: `client/main/main.ino`
- **Board**: Arduino Nano (ATmega328P)

## Compile Arduino Sketch

```powershell
arduino-cli compile --fqbn arduino:avr:nano client/main
```

Use when: User wants to compile Arduino code, build the weather station Arduino code, or check if code compiles.

**If compile fails**: Report errors and suggest fixes. Common issues:
- Missing libraries → Install required libraries
- Syntax errors → Show specific error location
- Board not found → Verify FQBN is correct

## Upload to Arduino

```powershell
# Compile first (if not already done)
arduino-cli compile --fqbn arduino:avr:nano client/main

# Upload to COM4
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

Use when: User wants to upload sketch, flash the Arduino, or deploy Arduino code.

**If upload fails**: 
- Check COM port is correct (may need to check Device Manager)
- Try "ATmega328P (Old Bootloader)" variant if using old bootloader
- May need manual reset during upload
- Reference `client/UPLOAD_TROUBLESHOOTING.md` for detailed troubleshooting

## Monitor Serial Output

```powershell
arduino-cli monitor -p COM4
```

Use when: User wants to see Arduino serial output, monitor the Arduino, or view debug messages.

**Note**: Monitor runs continuously. User may need to stop it manually (Ctrl+C).

## Complete Arduino Update Workflow

When user wants to update and upload Arduino code:

1. **Compile sketch**:
```powershell
arduino-cli compile --fqbn arduino:avr:nano client/main
```

2. **If compile succeeds, upload**:
```powershell
arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main
```

3. **Optionally start serial monitor** (if user requests):
```powershell
arduino-cli monitor -p COM4
```

Use when: User wants to update Arduino code, deploy Arduino changes, or compile and upload.

## List Connected Boards

```powershell
arduino-cli board list
```

Use when: User wants to verify Arduino connection or check available ports.

## Install Libraries

Common libraries for this project:
```powershell
arduino-cli lib install "RF24"
arduino-cli lib install "Adafruit BME280 Library"
arduino-cli lib install "ArduinoJson"
```

Use when: User reports missing library errors or needs to install dependencies.

## Common Issues

### Bootloader Selection
If upload fails, try the "ATmega328P (Old Bootloader)" variant:
```powershell
arduino-cli upload -p COM4 --fqbn arduino:avr:nano:bootloader=oldbootloader client/main
```

### Port Not Found
- Check Device Manager for COM port
- Try different USB port
- Verify Arduino is connected

### Upload Fails
- May need manual reset during upload
- Check bootloader version
- Verify FQBN matches board

## Additional Resources

- For example interactions and troubleshooting patterns, see [reference.md](reference.md)
- `client/ARDUINO_CLI.md` - Arduino CLI installation and usage
- `client/UPLOAD_TROUBLESHOOTING.md` - Arduino upload error solutions
- `client/README.md` - Arduino project documentation
