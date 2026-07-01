// ads_probe.ino — ADS1115 deep diagnostic
//
// Two remote tests that pin down ADS1115 failure modes without opening
// the enclosure:
//
//   1) Gain sweep on ch0 — if conversions are happening, the raw count
//      scales proportionally with the PGA setting. Stuck values mean
//      the chip isn't really converting.
//
//   2) Differential reads on (ch0-ch1) and (ch2-ch3) — if single-ended
//      reads all return identical values because the AIN pins are
//      shorted at the chip, differential reads between shorted pairs
//      must come back ~0. Non-zero differentials prove the channels
//      see different voltages and the matching SE reads are a library
//      or chip-mode artifact.

#include <Wire.h>
#include <Adafruit_ADS1X15.h>

#define ADS1115_ADDRESS 0x48

Adafruit_ADS1115 ads;

const struct { adsGain_t g; const char* name; float fs; } gains[] = {
  { GAIN_TWOTHIRDS, "2/3x (FS=6.144V)", 6.144f },
  { GAIN_ONE,       "1x   (FS=4.096V)", 4.096f },
  { GAIN_TWO,       "2x   (FS=2.048V)", 2.048f },
  { GAIN_FOUR,      "4x   (FS=1.024V)", 1.024f },
  { GAIN_EIGHT,     "8x   (FS=0.512V)", 0.512f },
  { GAIN_SIXTEEN,   "16x  (FS=0.256V)", 0.256f },
};

void setup() {
  Serial.begin(9600);
  delay(200);

  // Match production: drive sensor-power rails high.
  pinMode(6, OUTPUT); pinMode(7, OUTPUT);
  digitalWrite(6, HIGH); digitalWrite(7, HIGH);
  delay(100);

  Wire.begin();
  delay(50);

  Serial.println(F("\n==== ADS1115 deep probe ===="));
  if (!ads.begin(ADS1115_ADDRESS)) {
    Serial.println(F("ads.begin FAILED — chip not on I2C"));
    while (true) { delay(1000); }
  }
  Serial.println(F("ads.begin OK"));
}

void loop() {
  Serial.println(F("\n---- gain sweep on ch0 ----"));
  for (auto& gx : gains) {
    ads.setGain(gx.g);
    delay(10);
    int16_t raw = ads.readADC_SingleEnded(0);
    float volts = ads.computeVolts(raw);
    Serial.print(F("  gain="));
    Serial.print(gx.name);
    Serial.print(F("  raw="));
    Serial.print(raw);
    Serial.print(F("  V="));
    Serial.println(volts, 5);
  }

  // Restore the production gain for the rest of the loop.
  ads.setGain(GAIN_TWOTHIRDS);

  Serial.println(F("---- single-ended (all 4 channels) ----"));
  for (uint8_t ch = 0; ch < 4; ch++) {
    int16_t raw = ads.readADC_SingleEnded(ch);
    Serial.print(F("  ch"));
    Serial.print(ch);
    Serial.print(F("  raw="));
    Serial.print(raw);
    Serial.print(F("  V="));
    Serial.println(ads.computeVolts(raw), 5);
  }

  Serial.println(F("---- differential ----"));
  int16_t d01 = ads.readADC_Differential_0_1();
  int16_t d23 = ads.readADC_Differential_2_3();
  Serial.print(F("  d(0-1) raw="));
  Serial.print(d01);
  Serial.print(F("  V="));
  Serial.println(ads.computeVolts(d01), 5);
  Serial.print(F("  d(2-3) raw="));
  Serial.print(d23);
  Serial.print(F("  V="));
  Serial.println(ads.computeVolts(d23), 5);

  delay(3000);
}
