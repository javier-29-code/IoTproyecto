#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include "DFRobot_HumanDetection.h"

// C1001 por UART2
#define RX_PIN 16
#define TX_PIN 17
// MLX90640 por I2C
#define SDA_PIN 21
#define SCL_PIN 22

DFRobot_HumanDetection hu(&Serial2);
Adafruit_MLX90640 mlx;

float frame[32 * 24];            // 768 temperaturas en °C
char buf[32 * 24 * 6 + 16];      // texto de una imagen térmica
bool hayTermica = false;

int corazon = 0, respira = 0;
unsigned long ultimaVital = 0;

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, RX_PIN, TX_PIN);
  Wire.begin(SDA_PIN, SCL_PIN);

  // --- C1001 ---
  while (hu.begin() != 0) {
    Serial.println("Error al iniciar C1001, revisa el cableado...");
    delay(1000);
  }
  while (hu.configWorkMode(hu.eSleepMode) != 0) {
    delay(1000);
  }
  hu.configLEDLight(hu.eHPLed, 1);
  hu.sensorRet();
  delay(1000);

  // --- MLX90640 ---
  if (mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    Wire.setClock(400000);                    // I2C rápido (400 kHz)
    mlx.setMode(MLX90640_CHESS);              // modo recomendado para imagen
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_2_HZ);        // 2 imágenes por segundo
    hayTermica = true;
  } else {
    Serial.println("MLX90640 no encontrado, revisa SDA/SCL");
  }
  Serial.println("Listo");
}

void loop() {
  // Datos del C1001
  int presencia  = hu.smHumanData(hu.eHumanPresence);
  int movimiento = hu.smHumanData(hu.eHumanMovement);
  int rango      = hu.smHumanData(hu.eHumanMovingRange);
  int distancia  = hu.smHumanData(hu.eHumanDistance);

  if (millis() - ultimaVital >= 1000) {
    ultimaVital = millis();
    corazon = hu.getHeartRate();
    respira = hu.getBreatheValue();
  }

  Serial.print("DATA,");
  Serial.print(presencia);  Serial.print(",");
  Serial.print(movimiento); Serial.print(",");
  Serial.print(rango);      Serial.print(",");
  Serial.print(distancia);  Serial.print(",");
  Serial.print(corazon);    Serial.print(",");
  Serial.println(respira);

  // Imagen térmica: getFrame() tarda ~0.5 s, por eso todo el ciclo va a ~2 por segundo
  if (hayTermica && mlx.getFrame(frame) == 0) {
    int n = sprintf(buf, "THERM");
    for (int i = 0; i < 32 * 24; i++) {
      n += sprintf(buf + n, ",%d", (int)round(frame[i] * 10));  // décimas de °C (253 = 25.3 °C)
    }
    buf[n++] = '\n';
    Serial.write((uint8_t*)buf, n);
  }
}
