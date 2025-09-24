#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(7, 8);                    // CE, CSN
const byte address[6] = "123AB";

// Serial frame from Python: 0xAA | xi(lo) | xi(hi) | yi(lo) | yi(hi) | btn | csum
const uint8_t START = 0xAA;
const uint8_t FRAME_LEN = 7;

uint8_t frameBuf[FRAME_LEN];
uint8_t idx = 0;
bool inFrame = false;

uint8_t csum(const uint8_t* b, uint8_t n) {
  uint16_t s = 0; for (uint8_t i=0;i<n;++i) s += b[i]; return (uint8_t)(s & 0xFF);
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);

  radio.begin();
  radio.setAutoAck(true);
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_250KBPS);
  radio.setChannel(100);               // move away from noisy Wi-Fi overlap
  radio.setRetries(5, 15);
  radio.enableDynamicPayloads();
  radio.openWritingPipe(address);
  radio.stopListening();

  // Uncomment to dump config once:
  // radio.printDetails();
}

void loop() {
  while (Serial.available()) {
    uint8_t b = (uint8_t)Serial.read();

    if (!inFrame) {
      if (b == START) { inFrame = true; idx = 0; frameBuf[idx++] = b; }
      continue;
    }

    frameBuf[idx++] = b;
    if (idx >= FRAME_LEN) {
      uint8_t calc = csum(&frameBuf[1], FRAME_LEN - 2);
      uint8_t recv = frameBuf[FRAME_LEN - 1];

      if (calc == recv) {
        int16_t xi = (int16_t)(frameBuf[1] | (frameBuf[2] << 8));
        int16_t yi = (int16_t)(frameBuf[3] | (frameBuf[4] << 8));
        uint8_t btn = frameBuf[5];

        uint8_t rf[5];
        memcpy(&rf[0], &xi, 2);
        memcpy(&rf[2], &yi, 2);
        rf[4] = btn;

        bool ok = radio.write(&rf, sizeof(rf));
        if (ok) { digitalWrite(LED_BUILTIN, HIGH); delay(2); digitalWrite(LED_BUILTIN, LOW); }
      }
      inFrame = false; idx = 0;
    }
  }
}
