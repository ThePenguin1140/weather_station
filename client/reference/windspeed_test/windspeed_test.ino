
/*
 * 10K resistor:
 * ends to +5V and ground
*/

int analogInput = 2;
float vout = 0.00;
float   vin = 0.00;
float R1 = 10000.0; // resistance of R1 (10K) -see text!
float   R2 = 61900.0; // resistance of R2 (9.96K) - see text!
float value = 0.0;
float kor = 80.0;
float wind = 0.0;

void   setup() {
pinMode(analogInput,   INPUT);
Serial.begin(9600);
delay(5000);
}

void loop() {
  
// read the value at analog input
   value = analogRead(analogInput);
   
   vout = (value * 5.0) / 1024.0; // see text
   vin = vout / (R2/(R1+R2)); 
//    if (vin<0.09) {
//                  vin=0.0;//statement to quash undesired reading !
//                  } 
 
  Serial.print(vin);
  Serial.print("   ");
  Serial.print("Volts");
  Serial.println("   ");
  wind = vin*kor;
  Serial.print("Windspeed ");
  Serial.print(wind);
  Serial.println(" km/h");
  delay(1000);
}
