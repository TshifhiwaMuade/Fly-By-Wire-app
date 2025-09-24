#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <Servo.h>

RF24 radio(7, 8);                    // CE, CSN
const byte address[6] = "123AB";

// Servo pins
const uint8_t SERVO_X_LEFT  = 4;     // mirrors X
const uint8_t SERVO_X_RIGHT = 5;     // mirrors X (opposite)
const uint8_t SERVO_Y_1     = 6;     // follows Y
const uint8_t SERVO_Y_2     = 9;     // follows Y
const uint8_t SERVO_Y_3     = 10;    // follows Y (change to X if preferred)

Servo sxL, sxR, sy1, sy2, sy3;

const int16_t MOVE_THRESH = 300;
const int     TRAVEL_DEG  = 80;      // more obvious movement
const int     CENTER_DEG  = 90;
const uint32_t FAILSAFE_MS = 800;    // recenter if no packets in this time

uint32_t lastPktMs = 0;

inline int clampDeg(int d) { return d < 0 ? 0 : (d > 180 ? 180 : d); }

inline int mapAxisToDeg(int16_t v) {
  // v ∈ [-32767..32767] → delta ∈ [-TRAVEL_DEG..+TRAVEL_DEG]
  float norm = (float)v / 32767.0f;     // -1..+1
  int delta = (int)(norm * TRAVEL_DEG);
  return clampDeg(CENTER_DEG + delta);
}

void centerAll() {
  sxL.write(CENTER_DEG);
  sxR.write(CENTER_DEG);
  sy1.write(CENTER_DEG);
  sy2.write(CENTER_DEG);
  sy3.write(CENTER_DEG);
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Attach with explicit pulse limits (some MG996R clones like wider range)
  sxL.attach(SERVO_X_LEFT, 500, 2500);
  sxR.attach(SERVO_X_RIGHT, 500, 2500);
  sy1.attach(SERVO_Y_1, 500, 2500);
  sy2.attach(SERVO_Y_2, 500, 2500);
  sy3.attach(SERVO_Y_3, 500, 2500);
  centerAll();

  radio.begin();
  radio.setAutoAck(true);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(100);
  radio.enableDynamicPayloads();
  radio.openReadingPipe(1, address);
  radio.startListening();

}

void loop() {
  bool got = false;

  while (radio.available()) {
    uint8_t len = radio.getDynamicPayloadSize();
    if (len != 5) { uint8_t dump[32]; if (len > 32) len = 32; radio.read(dump, len); continue; }

    uint8_t buf[5];
    radio.read(buf, 5);

    int16_t xi, yi; uint8_t btn;
    memcpy(&xi, &buf[0], 2);
    memcpy(&yi, &buf[2], 2);
    btn = buf[4];

    int xDeg_centered = mapAxisToDeg(xi);
    int yDeg_centered = mapAxisToDeg(yi);

    int xDeg_left  = xDeg_centered;
    int xDeg_right = clampDeg(180 - xDeg_centered);

    sxL.write(xDeg_left);
    sxR.write(xDeg_right);
    sy1.write(yDeg_centered);
    sy2.write(yDeg_centered);
    sy3.write(yDeg_centered);

    digitalWrite(LED_BUILTIN, HIGH);   // packet indicator
    delay(2);
    digitalWrite(LED_BUILTIN, LOW);

    // Debug once per packet
    Serial.print("RX xi="); Serial.print(xi);
    Serial.print(" yi="); Serial.print(yi);
    Serial.print(" -> X(L,R)="); Serial.print(xDeg_left); Serial.print(","); Serial.print(xDeg_right);
    Serial.print("  Y="); Serial.println(yDeg_centered);

    lastPktMs = millis();
    got = true;
  }

  // Failsafe recenter if link is quiet
  if (!got && (millis() - lastPktMs) > FAILSAFE_MS) {
    centerAll();
  }
}
