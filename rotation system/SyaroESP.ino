// Libraries
#include <AccelStepper.h>
#include <ESP8266WiFi.h>
#include <ESPAsyncUDP.h>

// Network settings
#define SSID "brisa-2965238"
#define PASSWD "nzjqyqln"
#define BROADPORT 53530

// Stepper settings
#define RADIO 360
#define STEPS 200

// Direction settings
#define NORTH 0.0
#define CW 1
#define NONE 0
#define CCW -1
#define motorInterfaceType 1

// MCU settings
const int DIR = 12;
const int STEP = 14;

// Variables
int direction;       // ccw, none or cw
float angle;         // Angle received by client
float real_angle;    // Angle converted using 360° / STEPS Formula
long north;          // North angle
String string_recv;  // String to be formated
char char_recv;      // Char received by the client
bool client_conected;

// Initialization
AccelStepper stepper(motorInterfaceType, STEP, DIR);  // Stepper
AsyncUDP udp;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Stepper setup
  stepper.setMaxSpeed(1000);
  stepper.setSpeed(200);
  stepper.setAcceleration(60);
  stepper.setCurrentPosition(0);
  north = stepper.currentPosition();

  // Broadcast setup
  client_conected = false;
  prepare_conection();
}

void prepare_conection() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWD);
  if (WiFi.waitForConnectResult() != WL_CONNECTED) {
    Serial.println("WiFi Failed");
    while (1) {
      delay(1000);
    }
  }
  if (udp.listen(BROADPORT)) {
    Serial.print("Listening on IP: ");
    Serial.println(WiFi.localIP());

    udp.onPacket(
      [](AsyncUDPPacket packet) {
        Serial.print("UDP Packet Type: ");
        Serial.print(packet.isBroadcast() ? "Broadcast" : packet.isMulticast() ? "Multicast"
                                                                               : "Unicast");
        Serial.print(", From: ");
        Serial.print(packet.remoteIP());
        Serial.print(":");
        Serial.print(packet.remotePort());
        Serial.print(", To: ");
        Serial.print(packet.localIP());
        Serial.print(":");
        Serial.print(packet.localPort());
        Serial.print(", Length: ");
        Serial.print(packet.length());
        Serial.print(", Data: ");
        Serial.write(packet.data(), packet.length());
        Serial.println();
        packet.printf("Got %u bytes of data", packet.length());

        client_conected = true;

        if (client_conected == true) 
        {
          string_recv = (char*) packet.data();
          angle = string_recv.toFloat();
          if ( angle == NORTH )
          {
            rotate_stepper(NORTH);
          }
          else
          {
            rotate_stepper(angle);
          }
        }
      });
  }
}

void broadcast() {
  while (client_conected == false) {
    Serial.print("Broadcasting...\n");
    delay(1000);
    udp.broadcast("Anyone here?");
    delay(1000);
  }
}

void loop() {
  broadcast();
}

void rotate_stepper(float angle) {
  Serial.print("received angle: ");
  stepper.moveTo(angle);
  Serial.print("real angle: ");
  if (angle != NORTH) {
    // (angle * 200)/360
    real_angle = (long)round(((angle * STEPS) / RADIO) * CCW);
  } else {
    real_angle = north;
  }
  Serial.println(real_angle);

  // move stepper to real_angle
  Serial.print("distanceToGo: ");
  stepper.moveTo(real_angle);
  Serial.println(stepper.distanceToGo());
  while (stepper.distanceToGo() != 0) {
    Serial.print("current position: ");
    stepper.run();
    Serial.println(stepper.currentPosition());
  }
}