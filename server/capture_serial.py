"""Capture Arduino serial output for a fixed duration."""
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial not installed", file=sys.stderr)
    sys.exit(1)

PORT = "COM4"
BAUD = 9600  # PC-side rate; firmware uses DEBUG_BAUD=38400 at 4MHz CPU
DURATION = 35

lines = []
with serial.Serial(PORT, BAUD, timeout=1) as ser:
    time.sleep(2)  # allow reset after port open
    deadline = time.time() + DURATION
    while time.time() < deadline:
        raw = ser.readline()
        if raw:
            line = raw.decode("utf-8", errors="replace").rstrip()
            lines.append(line)
            safe = line.encode("ascii", errors="replace").decode("ascii")
            print(safe, flush=True)

print("\n--- captured", len(lines), "lines ---", file=sys.stderr)
