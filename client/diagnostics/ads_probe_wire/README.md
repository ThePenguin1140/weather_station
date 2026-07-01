# ads_probe_wire

Raw `Wire.h` diagnostic for the 4-channel I²C ADC in the Solar Battery Case (`0x48`). No Adafruit library — useful when the production driver misbehaves or the module is not what the schematic labels it.

## Quick start

```bash
arduino-cli compile --fqbn arduino:avr:nano diagnostics/ads_probe_wire
arduino-cli upload -p <port> --fqbn arduino:avr:nano diagnostics/ads_probe_wire
arduino-cli monitor -p <port>
```

Serial: **9600 baud**. D6/D7 are driven HIGH to power the switched sensor rails (same as `main.ino`).

## Diagnosis (2026)

The board is documented as an **ADS1115** (16-bit, config register reset `0x8583`). On hardware under test:

| Observation               | ADS1115 expected    | What we saw                                                 |
| ------------------------- | ------------------- | ----------------------------------------------------------- |
| I²C ACK @ `0x48`          | Yes                 | Yes                                                         |
| Config reg `0x01` at boot | `0x8583`            | `0xB400`, `0xCB00`, `0x0`, etc.                             |
| Gain sweep on ch0         | Raw scales with PGA | First read ~1486, then stuck at **-12337** on every gain    |
| Raw count range           | 0–32767 (16-bit)    | **0–255** when read correctly                               |
| `Adafruit_ADS1X15`        | Should work         | `ads.begin()` / register protocol fails or returns nonsense |

**Conclusion:** the module is an off-brand **PCF8591** (8-bit ADC/DAC), not an ADS1115. These clones are common — same default address (`0x48`), different protocol.

### PCF8591 reads that confirmed it

```
ADS config was 0xB400
PCF8591 channels read OK: 0 207 0 184
Identified: PCF8591 (8-bit ADC/DAC)
```

Stable 8-bit values on ch1 (~207) and ch3 (~182–184) match the earlier ~205 counts seen through the Adafruit driver (misinterpreted 8-bit data as 16-bit).

### Channel snapshot

| Ch  | Schematic use     | Typical raw | Note                                       |
| --- | ----------------- | ----------- | ------------------------------------------ |
| 0   | Light (LDR)       | 0–173       | Often 0 — verify wiring / pin map on clone |
| 1   | UV                | ~207        | Stable                                     |
| 2   | Solar battery (+) | 0           | Often 0 — verify wiring                    |
| 3   | Shunt / current   | ~182–184    | Stable                                     |

Software deltas `ch0−ch1` and `ch2−ch3` are printed for comparison; PCF8591 has **no hardware differential mode**.

## Fix in this sketch

`ads_probe_wire.ino` **auto-detects** the chip at boot:

1. **ADS1115** — config reg reads `0x8583` → 16-bit gain sweep, 4× single-ended, differential `(0−1)` and `(2−3)`.
2. **PCF8591** — config is not `0x8583` but all four channel reads succeed → 8-bit channel scan, software deltas, DAC mirror test (`AIN0` → `OUT`).

PCF8591 protocol (per channel):

```cpp
Wire.beginTransmission(0x48);
Wire.write(channel);   // 0x00..0x03 = AIN0..AIN3
Wire.endTransmission();
Wire.requestFrom(0x48, 1);
uint8_t raw = Wire.read();   // 0–255
```

I²C reads use **repeated-start** for ADS1115 paths (same pattern as `chip_id.ino`). PCF8591 uses **stop-then-read** after the control byte.

## Still to do in production

`client/main/main.ino` still uses `Adafruit_ADS1X15`. That driver **will not work** with a PCF8591. To restore light / UV / battery / current telemetry:

- Replace the ADS1115 driver with a small PCF8591 `Wire` helper, or
- Replace the module with a genuine ADS1115 breakout.

Until then, expect `ads.begin()` failures or bogus 16-bit values in the main sketch.

## Related sketches

| Sketch                           | Purpose                                                            |
| -------------------------------- | ------------------------------------------------------------------ |
| `../ads_probe/ads_probe.ino`     | ADS1115 probe via Adafruit library (only valid for a real ADS1115) |
| `../chip_id/chip_id.ino`         | I²C scan + chip ID registers                                       |
| `../i2c_scanner/i2c_scanner.ino` | Bus scan only                                                      |
