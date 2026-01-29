# Arduino Reference

## Example Interactions

### Example 1: Upload Arduino Code
**User**: "Upload the latest Arduino code"

**Agent Response**:
1. "I'll compile and upload the Arduino sketch to COM4."
2. Executes: `arduino-cli compile --fqbn arduino:avr:nano client/main`
3. If compile succeeds: Executes `arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main`
4. If compile fails: Reports errors and suggests fixes
5. Reports success or provides troubleshooting steps

### Example 2: Compile and Upload
**User**: "Compile and upload the Arduino sketch"

**Agent Response**:
1. "I'll compile the sketch first, then upload it."
2. Executes: `arduino-cli compile --fqbn arduino:avr:nano client/main`
3. If successful: "Compilation successful. Uploading to COM4..."
4. Executes: `arduino-cli upload -p COM4 --fqbn arduino:avr:nano client/main`
5. Reports upload status

### Example 3: Monitor Serial Output
**User**: "Show me the Arduino serial output"

**Agent Response**:
1. "I'll start the serial monitor on COM4. Press Ctrl+C to stop."
2. Executes: `arduino-cli monitor -p COM4`
3. Note: This runs continuously until user stops it

## Common Troubleshooting

### Upload Fails
- Check COM port in Device Manager
- Try "ATmega328P (Old Bootloader)" variant
- May need manual reset during upload
- Reference `client/UPLOAD_TROUBLESHOOTING.md`

### Compile Errors
- Missing libraries → Install with `arduino-cli lib install`
- Syntax errors → Show specific error location
- Board not found → Verify FQBN
