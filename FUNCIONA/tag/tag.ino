#include <SPI.h>
#include "DW3000.h"
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <WiFiUdp.h>
#define MQTT_MAX_PACKET_SIZE 2048 // AUMENTADO: Buffer más grande para evitar fragmentación
#include <PubSubClient.h>
#include <cmath>  // Para fabs, sqrt, etc.
#include <ArduinoJson.h>

// ===== IDENTIFICACIÓN DEL TAG =====
#define TAG_ID 1 // 

// ===== CONFIGURACIÓN WiFi =====
#define USE_AP_MODE false
#define AP_SSID "UWB_TAG_AP"
#define AP_PASS "12345678"
#define STA_SSID "iPhone de Nicolas"
#define STA_PASS "12345678"

// Configuraciones del servidor y UDP
#define HTTP_PORT 80
#define UDP_PORT 5555
#undef server // por si estaba definido
AsyncWebServer server(HTTP_PORT);
AsyncWebSocket ws("/ws");
WiFiUDP udp;
IPAddress broadcastIP(255, 255, 255, 255);

// MQTT Configuration
const char* mqtt_server = "172.20.10.2"; // Broker IP (Your PC real IP)
const int mqtt_port = 1883;
const char* log_topic = "uwb/tag/logs";       // Topic for detailed CSV logs
char status_topic[30];                      // Topic for simple status (constructed in setup)
WiFiClient espClient;
PubSubClient client(espClient);

// ===== Configuration for WiFi Logging =====
const char* logServerIp = "172.20.10.2"; // Tu PC real en la red iPhone hotspot
const int logServerPort = 5000;             // Port your Python receiver will listen on

// ===== TDMA Configuration (INDOOR) =====
const unsigned long TDMA_CYCLE_MS = 80; // REDUCIDO: Ciclo más rápido (80ms vs 100ms)
const unsigned long TDMA_SLOT_DURATION_MS = 30; // REDUCIDO: Slots más rápidos para indoor

// ===== CONFIGURACIÓN DE RANGING =====
#define ROUND_DELAY 100
static int frame_buffer = 0;
static int rx_status;
static int tx_status;

// Estados del ranging
static int curr_stage = 0;

static int t_roundA = 0;
static int t_replyA = 0;

static long long rx = 0;
static long long tx = 0;

static int clock_offset = 0;
static int ranging_time = 0;
static float distance = 0;

// Configuraciones para mediciones y filtrado (INDOOR)
#define NUM_MEASUREMENTS 3
#define NUM_ANCHORS 5  // CORREGIDO: 5 anclas para salón indoor
int ID_PONG[NUM_ANCHORS] = {1, 2, 3, 4, 5}; // IDs de las 5 anclas (lógico = físico)
float distance_buffer[NUM_ANCHORS][NUM_MEASUREMENTS] = { {0} };
int buffer_index[NUM_ANCHORS] = {0};
float anchor_distance[NUM_ANCHORS] = {0};
float anchor_avg[NUM_ANCHORS] = {0};
float pot_sig[NUM_ANCHORS] = {0};
static int fin_de_com = 0;
bool anchor_responded[NUM_ANCHORS] = {false}; // Added: Array to track anchor responses

// Variables para timeout OPTIMIZADAS
unsigned long timeoutStart = 0;
bool waitingForResponse = false;
const unsigned long RESPONSE_TIMEOUT = 35; // REDUCIDO: 35ms vs 60ms para eliminar gaps grandes

// Variables para gestor de estados OPTIMIZADAS
unsigned long lastUpdate = 0;
unsigned long updateInterval = 12; // AUMENTADO: 83Hz para máxima responsividad (12ms vs 15ms)

// Variables para modo de bajo consumo
unsigned long lastActivityTime = 0;
const unsigned long SLEEP_TIMEOUT = 300000;
bool lowPowerMode = false;

// Variables para Filtro de Kalman (INDOOR optimizado)
float kalman_dist[NUM_ANCHORS][2] = { {0} };
float kalman_dist_q = 0.005; // REDUCIDO: Menos ruido para más estabilidad
float kalman_dist_r = 0.08; // Observación más precisa en indoor

// Variables para posición (INDOOR)
float kalman_x = 0.0;
float kalman_y = 0.0;
float kalman_p_x = 1.0;
float kalman_p_y = 1.0;
float kalman_q = 0.01; // REDUCIDO: Posición más estable
float kalman_r = 0.05; // Observación más precisa

// Variables para la posición del tag
float tagPositionX = 0.0;
float tagPositionY = 0.0;

// NUEVO: Variables para trilateración inteligente (Opción A)
int last_anchor_combination[3] = {0, 1, 2}; // Últimas 3 anclas usadas
unsigned long last_trilateration_time = 0;
float last_valid_position[2] = {0.0, 0.0}; // Última posición válida
bool combination_stable = false; // Si la combinación actual es estable
float rssi_threshold = 5.0; // dBm - margen para cambiar ancla
float validation_threshold = 1.0; // metros - error máximo permitido

// ===== POSICIONES DE ANCLAS GLOBALES (anclas 1-5) =====
const float anchorsPos[NUM_ANCHORS][2] = {
  {-6.0,  0.0},   // Ancla 1 (índice 0) - Oeste
  {-1.6, 10.36},  // Ancla 2 (índice 1) - Noroeste  
  { 2.1, 10.36},  // Ancla 3 (índice 2) - Noreste
  { 6.35, 0.0},   // Ancla 4 (índice 3) - Este (posición corregida)
  { 0.0, -1.8}    // Ancla 5 (índice 4) - Sur centro
};

// ===== FUNCIONES HELPER =====
int getAnchorIndex(int anchor_id) {
  // Mapear ID de ancla (1,2,3,4,5) a índice de array (0,1,2,3,4)
  // Simplificado: índice = ID - 1
  if (anchor_id >= 1 && anchor_id <= 5) {
    return anchor_id - 1;
  }
  return -1; // No encontrado
}

int getAnchorNumber(int array_index) {
  // Convertir índice de array (0,1,2,3,4) a número de ancla (1,2,3,4,5)
  // Simplificado: ID = índice + 1
  return array_index + 1;
}

// ===== TRILATERACIÓN INTELIGENTE OPCIÓN A =====
bool selectOptimalAnchors(int* available_anchors, int count, int* selected) {
  if (count < 3) return false;
  
  // === PASO 1: Verificar si mantener combinación anterior ===
  bool can_keep_previous = false;
  if (combination_stable && (millis() - last_trilateration_time) < 2000) {
    bool all_available = true;
    float previous_avg_rssi = 0;
    
    for (int i = 0; i < 3; i++) {
      bool found = false;
      for (int j = 0; j < count; j++) {
                 if (available_anchors[j] == last_anchor_combination[i]) {
           previous_avg_rssi += pot_sig[last_anchor_combination[i]];
          found = true;
          break;
        }
      }
      if (!found) {
        all_available = false;
        break;
      }
    }
    
    if (all_available) {
      previous_avg_rssi /= 3.0;
      // Solo mantener si el RSSI promedio sigue siendo bueno
      if (previous_avg_rssi > -85.0) {
        selected[0] = last_anchor_combination[0];
        selected[1] = last_anchor_combination[1];
        selected[2] = last_anchor_combination[2];
        can_keep_previous = true;
        Serial.printf("[TRILAT-A] Mantiene anterior: [%d,%d,%d], RSSI=%.1f\n", 
                     getAnchorNumber(selected[0]), getAnchorNumber(selected[1]), getAnchorNumber(selected[2]), previous_avg_rssi);
      }
    }
  }
  
  // === PASO 2: Selección nueva por RSSI + geometría ===
  if (!can_keep_previous) {
    // Ordenar anclas por RSSI (mejor primero)
    int sorted_anchors[NUM_ANCHORS];
    float sorted_rssi[NUM_ANCHORS];
    
         for (int i = 0; i < count; i++) {
       sorted_anchors[i] = available_anchors[i];
       sorted_rssi[i] = pot_sig[available_anchors[i]];
     }
    
    // Bubble sort por RSSI descendente
    for (int i = 0; i < count - 1; i++) {
      for (int j = 0; j < count - i - 1; j++) {
        if (sorted_rssi[j] < sorted_rssi[j + 1]) {
          // Intercambiar RSSI
          float temp_rssi = sorted_rssi[j];
          sorted_rssi[j] = sorted_rssi[j + 1];
          sorted_rssi[j + 1] = temp_rssi;
          // Intercambiar índices
          int temp_anchor = sorted_anchors[j];
          sorted_anchors[j] = sorted_anchors[j + 1];
          sorted_anchors[j + 1] = temp_anchor;
        }
      }
    }
    
    // Inicialmente tomar las 3 mejores por RSSI
    selected[0] = sorted_anchors[0];
    selected[1] = sorted_anchors[1];
    selected[2] = sorted_anchors[2];
    
    // Verificar geometría de este trío
         float det = calculateDeterminant(selected[0], selected[1], selected[2]);
    
    // Si geometría es mala, sustituir el de peor RSSI por el siguiente
    if (fabs(det) < 0.001 && count > 3) {
             selected[2] = sorted_anchors[3]; // Reemplazar el 3º (peor RSSI del trío) por el 4º
       det = calculateDeterminant(selected[0], selected[1], selected[2]);
      Serial.println("[TRILAT-A] Reemplazado por geometría");
    }
    
    // Actualizar combinación estable
    last_anchor_combination[0] = selected[0];
    last_anchor_combination[1] = selected[1];
    last_anchor_combination[2] = selected[2];
    combination_stable = true;
    
         Serial.printf("[TRILAT-A] Nueva selección: [%d,%d,%d], RSSI=[%.1f,%.1f,%.1f], Det=%.3f\n",
                  getAnchorNumber(selected[0]), getAnchorNumber(selected[1]), getAnchorNumber(selected[2]),
                  pot_sig[selected[0]], pot_sig[selected[1]], pot_sig[selected[2]], det);
  }
  
  // === PASO 3: Calcular posición provisional ===
  float test_x, test_y;
  bool trilat_ok = calculateTrilateration(selected[0], selected[1], selected[2], &test_x, &test_y);
  
  if (!trilat_ok) return false;
  
  // === PASO 4: Validar con anclas restantes ===
  bool validation_passed = true;
  float max_error = 0;
  int worst_anchor = -1;
  
  for (int i = 0; i < count; i++) {
    int anchor_id = available_anchors[i];
    
    // Saltar las 3 ya usadas
    if (anchor_id == selected[0] || anchor_id == selected[1] || anchor_id == selected[2]) {
      continue;
    }
    
    // Calcular distancia esperada vs medida
    float expected_dist = sqrt(pow(test_x - anchorsPos[anchor_id][0], 2) + 
                              pow(test_y - anchorsPos[anchor_id][1], 2));
         float measured_dist = anchor_distance[anchor_id]; // Ya en metros
    float error = fabs(expected_dist - measured_dist);
    
    if (error > max_error) {
      max_error = error;
      worst_anchor = anchor_id;
    }
    
    if (error > validation_threshold) {
      validation_passed = false;
    }
    
    Serial.printf("[TRILAT-A] Validación ancla %d: esperado=%.2fm, medido=%.2fm, error=%.2fm\n",
                 getAnchorNumber(anchor_id), expected_dist, measured_dist, error);
  }
  
  // === PASO 5: Re-selección si validación falla ===
  if (!validation_passed && count >= 4) {
    Serial.printf("[TRILAT-A] Validación falló, error máx=%.2fm en ancla %d, reintentando...\n", 
                 max_error, getAnchorNumber(worst_anchor));
    
    // Intentar reemplazar el de peor RSSI del trío actual por el que falló validación
    if (worst_anchor >= 0) {
             // Encontrar cuál del trío tiene peor RSSI
       int worst_in_trio = selected[0];
       float worst_rssi = pot_sig[selected[0]];
       
       for (int i = 1; i < 3; i++) {
         if (pot_sig[selected[i]] < worst_rssi) {
           worst_rssi = pot_sig[selected[i]];
          worst_in_trio = selected[i];
        }
      }
      
      // Reemplazar
      for (int i = 0; i < 3; i++) {
        if (selected[i] == worst_in_trio) {
          selected[i] = worst_anchor;
          break;
        }
      }
      
      Serial.printf("[TRILAT-A] Reemplazo: ancla %d por %d\n", getAnchorNumber(worst_in_trio), getAnchorNumber(worst_anchor));
      
      // Actualizar combinación
      last_anchor_combination[0] = selected[0];
      last_anchor_combination[1] = selected[1];
      last_anchor_combination[2] = selected[2];
    }
  }
  
  return true;
}

// Función auxiliar para calcular determinante (usa anchorsPos global)
float calculateDeterminant(int a0, int a1, int a2) {
  float A = 2 * (anchorsPos[a1][0] - anchorsPos[a0][0]);
  float B = 2 * (anchorsPos[a1][1] - anchorsPos[a0][1]);
  float D = 2 * (anchorsPos[a2][0] - anchorsPos[a1][0]);
  float E = 2 * (anchorsPos[a2][1] - anchorsPos[a1][1]);
  return A * E - B * D;
}

// Función auxiliar para trilateración (usa anchorsPos global)
bool calculateTrilateration(int a0, int a1, int a2, float* result_x, float* result_y) {
  float x1 = anchorsPos[a0][0], y1 = anchorsPos[a0][1];
  float x2 = anchorsPos[a1][0], y2 = anchorsPos[a1][1]; 
  float x3 = anchorsPos[a2][0], y3 = anchorsPos[a2][1];
  
  float r1 = anchor_distance[a0]; // Ya en metros
  float r2 = anchor_distance[a1]; // Ya en metros
  float r3 = anchor_distance[a2]; // Ya en metros
  
  float A = 2 * (x2 - x1);
  float B = 2 * (y2 - y1);
  float C = r1*r1 - r2*r2 - x1*x1 + x2*x2 - y1*y1 + y2*y2;
  float D = 2 * (x3 - x2);
  float E = 2 * (y3 - y2);
  float F = r2*r2 - r3*r3 - x2*x2 + x3*x3 - y2*y2 + y3*y3;
  
  float det = A * E - B * D;
  if (fabs(det) < 0.0001) return false;
  
  *result_x = (C * E - F * B) / det;
  *result_y = (A * F - D * C) / det;
  return true;
}

// Estructura para definir zonas de interés
#define NUM_ZONES 3  // Zonas para salón indoor
struct Zone {
  float x;
  float y;
  float radius;
  bool tagInside;
  unsigned long entryTime;
  unsigned long minStayTime;
  bool stayTimeReached;
};

// Definición de zonas (INDOOR - Salón 3.45x5.40m)
Zone zones[NUM_ZONES] = {
  {0.8, 3.8, 0.7, false, 0, 750, false},   // Zona_Sofa
  {2.8, 1.5, 0.8, false, 0, 500, false},   // Zona_TV  
  {1.7, 2.5, 1.0, false, 0, 1000, false}   // Zona_Centro
};

// Variables para MQTT y Estado OPTIMIZADAS
unsigned long lastMqttReconnectAttempt = 0;
unsigned long lastStatusUpdate = 0;
const long statusUpdateInterval = 80; // OPTIMIZADO: Sincronizado con TDMA (80ms = 12.5 Hz estable)
String last_anchor_id = "N/A"; // Variable para almacenar el ID del último ancla vista

// ===== SISTEMA DE BUFFERING ESTABILIZADO =====
struct StabilizedBuffer {
  float position_x_buffer[8];
  float position_y_buffer[8];
  unsigned long timestamp_buffer[8];
  int buffer_head = 0;
  int buffer_count = 0;
  unsigned long last_output_time = 0;
  const unsigned long OUTPUT_INTERVAL = 80; // Salida fija cada 80ms (12.5 Hz estable)
} stable_buffer;

// ===== VARIABLES DE CONTROL DE FLUJO MQTT =====
struct MQTTFlowControl {
  unsigned long last_successful_send = 0;
  unsigned long last_connection_check = 0;
  int consecutive_failures = 0;
  bool flow_control_active = false;
  const unsigned long CONNECTION_CHECK_INTERVAL = 1000; // Verificar conexión cada 1s
  const int MAX_CONSECUTIVE_FAILURES = 3;
} mqtt_flow;

// HTML para la página web integrada (versión simplificada)
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Monitor de Tag UWB</title>
  <style>
    body { font-family: Arial; margin: 0; padding: 0; background: #f0f0f0; }
    .container { max-width: 800px; margin: 0 auto; padding: 20px; }
    h1 { color: #333; }
    .card { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .anchor { display: flex; justify-content: space-between; margin-bottom: 10px; }
    .battery { display: flex; align-items: center; margin-bottom: 20px; }
    .battery-icon { width: 30px; height: 15px; border: 2px solid #333; border-radius: 3px; position: relative; margin-right: 10px; }
    .battery-icon:after { content: ''; width: 3px; height: 8px; background: #333; position: absolute; right: -5px; top: 3px; border-radius: 0 2px 2px 0; }
    .battery-level { height: 100%; background: #4CAF50; border-radius: 1px; }
    button { background: #4CAF50; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
    .status { color: #666; font-style: italic; }
    #visualization { height: 400px; width: 100%; max-width: 600px; position: relative; border: 1px solid #ccc; background: #fafafa; margin: 0 auto; }
    .anchor-point { position: absolute; width: 20px; height: 20px; border-radius: 50%; background: blue; color: white; display: flex; justify-content: center; align-items: center; transform: translate(-50%, -50%); }
    .distance-circle { position: absolute; border-radius: 50%; border: 1px dashed rgba(0,0,0,0.3); transform: translate(-50%, -50%); }
    .tag-point { 
      position: absolute; 
      width: 14px; 
      height: 14px; 
      border-radius: 50%; 
      background: red; 
      transform: translate(-50%, -50%); 
      box-shadow: 0 0 15px rgba(255,0,0,0.7); 
      transition: all 0.1s linear;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(255,0,0,0.7); }
      70% { box-shadow: 0 0 0 10px rgba(255,0,0,0); }
      100% { box-shadow: 0 0 0 0 rgba(255,0,0,0); }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Monitor de Tag UWB</h1>
    
    <div class="card">
      <div class="battery">
        <div class="battery-icon">
          <div class="battery-level" id="battery-level" style="width: 50%"></div>
        </div>
        <span id="battery-percentage">50%</span>
      </div>
      <p class="status" id="status">Esperando datos...</p>
    </div>
    
    <div class="card">
      <h2>Anclajes</h2>
      <div id="anchors-container"></div>
    </div>
    
    <div class="card">
      <h2>Visualización</h2>
      <div id="visualization"></div>
      <div style="margin-top: 10px;">
        <p>Posición estimada: <span id="tag-position">Calculando...</span></p>
      </div>
    </div>
    
    <button onclick="requestUpdate()">Actualizar datos</button>
  </div>

  <script>
    let lastUpdate = Date.now();
    let anchors = [];
    let tagPosition = { x: 150, y: 150 }; // Posición actual en píxeles (se actualiza por animación)
    let tagTarget   = { x: 150, y: 150 }; // Próximo destino recibido

    // Variables de visualización (faltaban tras refactor)
    let visualizationInitialized = false;
    let vizElements = {
        container: null,
        border: null,
        anchorPoints: {},
        distanceCircles: {},
        tagPoint: null
    };
    let anchorListItems = {}; // Cache elementos DOM de anclas

    // Conexión WebSocket para recibir datos push en tiempo real
    const socket = new WebSocket(`ws://${window.location.host}/ws`);

    socket.addEventListener('message', (evt) => {
      try {
        const data = JSON.parse(evt.data);
        window.currentTagPositionFromESP = data.position;
        window.currentAnchorsData = data.anchors;
        updateUI(data);
      } catch (e) { console.error('WS parse error', e); }
    });

    socket.addEventListener('open', () => console.log('[WS] conectado'));
    socket.addEventListener('close', () => console.warn('[WS] cerrado'));

    // Animación continua a ~60 fps usando requestAnimationFrame
    function animateTag() {
      const lerp = 0.15; // Factor de interpolación (0-1)
      tagPosition.x += (tagTarget.x - tagPosition.x) * lerp;
      tagPosition.y += (tagTarget.y - tagPosition.y) * lerp;

      if (vizElements.tagPoint) {
        vizElements.tagPoint.style.left = tagPosition.x + 'px';
        vizElements.tagPoint.style.top  = tagPosition.y + 'px';
      }
      requestAnimationFrame(animateTag);
    }
    requestAnimationFrame(animateTag);

    // Obtener datos del ESP32
    function fetchData() {
      fetch('/data')
        .then(response => response.json())
        .then(data => {
          window.currentTagPositionFromESP = data.position; // Almacenar posición del ESP
          window.currentAnchorsData = data.anchors; // Almacenar datos de anclas por si renderVisualization los necesita directamente
          updateUI(data); // Pasar todos los datos a updateUI
          lastUpdate = Date.now();
        })
        .catch(error => {
          console.error('Error:', error);
          document.getElementById('status').textContent = 'Error de conexión';
        });
    }
    
    // Actualizar la interfaz con los datos recibidos
    function updateUI(data) {
      // Actualizar batería
      const batteryLevel = data.battery;
      document.getElementById('battery-level').style.width = batteryLevel + '%';
      document.getElementById('battery-percentage').textContent = batteryLevel + '%';

      // Actualizar anclajes data (usaremos window.currentAnchorsData o data.anchors)
      anchors = data.anchors; // Mantenemos esto por si renderVisualization lo usa directamente

      // Depuración - mostrar distancias en consola
      // console.log("Distancias recibidas (cm):", anchors.map(a => a.dist));

      // --- Optimización: Actualizar lista de anclas sin recrear todo ---
      const anchorsContainer = document.getElementById('anchors-container');
      let anchorsChanged = anchorsContainer.children.length !== anchors.length;

      anchors.forEach((anchor, i) => {
        let anchorDiv = anchorListItems[anchor.id];
        if (!anchorDiv) {
          // Crear el div del ancla si no existe
          anchorDiv = document.createElement('div');
          anchorDiv.className = 'anchor';
          anchorDiv.id = `anchor-list-item-${anchor.id}`;
          anchorDiv.innerHTML = `
            <div>
              <strong>Anclaje ${anchor.id}</strong>
              <p>Distancia: <span class="anchor-dist">${(anchor.dist / 100).toFixed(2)}</span> m</p>
            </div>
            <div>
              <p>Señal: <span class="anchor-rssi">${anchor.rssi.toFixed(1)}</span> dBm</p>
            </div>
          `;
          anchorsContainer.appendChild(anchorDiv);
          anchorListItems[anchor.id] = anchorDiv; // Guardar referencia
          anchorsChanged = true;
        } else {
          // Actualizar datos si ya existe
          anchorDiv.querySelector('.anchor-dist').textContent = (anchor.dist / 100).toFixed(2);
          anchorDiv.querySelector('.anchor-rssi').textContent = anchor.rssi.toFixed(1);
        }
      });
      // Podríamos añadir lógica para eliminar anclas si desaparecen, pero asumimos que son fijas
      // --- Fin Optimización Lista Anclas ---

      // Calcular posición del tag por trilateración (ahora usa datos del ESP)
      // Ya no necesitamos la condición de anchors.length >=4 aquí si confiamos en data.position
      calculateTagPosition(); // Esta función ahora usará window.currentTagPositionFromESP
      
      // Actualizar visualización
      renderVisualization();
      
      // Actualizar estado
      document.getElementById('status').textContent = 'Última actualización: ' + new Date().toLocaleTimeString();
    }

    // Cálculo de posición por trilateración
    function calculateTagPosition() {
        // Configuración del espacio físico INDOOR (rectángulo de 3.45m x 5.40m)
        const minX = -6.9;
        const maxX =  6.8;
        const minY = -3.5;
        const maxY = 10.36;

        const areaWidth  = maxX - minX; // 13.7 m
        const areaHeight = maxY - minY; // 13.86 m
        const scale = 40;        // 1m = 40px (ajuste optimizado para el contenedor web)
        const margin = 15;       // margen en píxeles reducido
      
        // Ancho y alto del área de visualización en píxeles
        const vizWidth = areaWidth * scale + 2 * margin;
        const vizHeight = areaHeight * scale + 2 * margin;

        // Obtener la posición X, Y calculada por el ESP32 (que ya debería estar filtrada por Kalman si está activo en C++)
        // Estos valores vienen de data.position.x y data.position.y en updateUI
        // Necesitamos acceder a la variable 'data' globalmente o pasarla.
        // Por simplicidad, asumiremos que 'currentData' es una variable global actualizada en fetchData.
        // Sería mejor pasar 'data.position' como argumento a calculateTagPosition.
        
        // Para este ejemplo, vamos a necesitar que 'fetchData' almacene 'data.position' en una variable accesible.
        // Modificaremos fetchData y updateUI ligeramente.

        if (!window.currentTagPositionFromESP) {
            document.getElementById('tag-position').textContent = "Esperando datos del ESP...";
            return;
        }

        let esp_x = window.currentTagPositionFromESP.x;
        let esp_y = window.currentTagPositionFromESP.y;

        // Depuración: mostrar la posición recibida del ESP32
        console.log("Posición RECIBIDA del ESP32 (metros):", esp_x, esp_y);
              
        try {
          // Limitar a los nuevos límites del hexágono irregular
          const boundedX = Math.max(minX, Math.min(maxX, esp_x));
          const boundedY = Math.max(minY, Math.min(maxY, esp_y));
      
          // Convertir a coordenadas de visualización
          const pixelX = margin + (boundedX - minX) * scale;
          const pixelY = vizHeight - margin - (boundedY - minY) * scale;
      
          // Actualizar objetivo para la animación fluida
          tagTarget.x = pixelX;
          tagTarget.y = pixelY;

          // Refrescar texto de posición
          document.getElementById('tag-position').textContent = 
            `X: ${boundedX.toFixed(2)}m, Y: ${boundedY.toFixed(2)}m (ESP)`;
        } catch (e) {
          console.error('Error en conversión de posición ESP:', e);
          document.getElementById('tag-position').textContent = "Error de visualización";
        }
      }
    
    // --- Optimización: Renderizar visualización actualizando elementos existentes ---
    function renderVisualization() {
      const viz = document.getElementById('visualization');
      if (!viz) return; 

      if (!visualizationInitialized) {
        vizElements.container = viz;
        viz.innerHTML = ''; 

        const minX = -6.9;
        const maxX =  6.8;
        const minY = -3.5;
        const maxY = 10.36;

        const areaWidth  = maxX - minX; // 13.7 m
        const areaHeight = maxY - minY; // 13.86 m
        const scale = 40;        
        const margin = 15;       
        const vizWidth = areaWidth * scale + 2 * margin;
        const vizHeight = areaHeight * scale + 2 * margin;

        viz.style.width = vizWidth + 'px';
        viz.style.height = vizHeight + 'px';
        viz.style.position = 'relative'; 

        const currentAnchorsToRender = window.currentAnchorsData || anchors; // Usar datos actualizados

        // Dibujar el perímetro real del hexágono mediante SVG
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", vizWidth);
        svg.setAttribute("height", vizHeight);
        svg.style.position = 'absolute';
        svg.style.left = '0';
        svg.style.top  = '0';

        // Vértices del hexágono en metros (en orden)
        const hexVertices = [
          { x: -6.9, y: -2   }, // V1
          { x: -1.6, y: 10.36}, // V2
          { x:  2.1, y: 10.36}, // V3
          { x:  6.8, y: -1.8 }, // V4
          { x:  0.0, y: -1.8 }, // V5
          { x: -0.4, y: -3.5 }  // V6
        ];

        // Posiciones de anclas con IDs
        const anchorsPosMetros = [
          { id: 1, x: -6.0,  y: 0.0  },
          { id: 2, x: -1.6, y: 10.36},
          { id: 3, x:  2.1, y: 10.36},
          { id: 4, x:  6.35, y: 0.0 },
          { id: 5, x:  0.0, y: -1.8 }
        ];

        // Convertir a coordenadas de píxel con el mismo sistema que usamos para los anclajes
        const pointsAttr = hexVertices.map(v => {
          const px = margin + (v.x - minX) * scale;
          const py = vizHeight - margin - (v.y - minY) * scale;
          return `${px},${py}`;
        }).join(' ');

        const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        polygon.setAttribute('points', pointsAttr);
        polygon.setAttribute('stroke', 'orange');
        polygon.setAttribute('stroke-width', '2');
        polygon.setAttribute('fill', 'none');
        svg.appendChild(polygon);
        viz.appendChild(svg);
        vizElements.border = polygon; // Guardamos referencia si hiciera falta

        // Crear puntos de anclajes y círculos de distancia solo si hay datos de anclas
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData, i) => {
                const anchorCfg = anchorsPosMetros.find(a => a.id === anchorData.id);
                if (!anchorCfg) return; // Si no hay configuración para este ID de ancla

                const anchorPixelX = margin + (anchorCfg.x - minX) * scale;
                const anchorPixelY = vizHeight - margin - (anchorCfg.y - minY) * scale;

                const dot = document.createElement('div');
                dot.className = 'anchor-point';
                dot.textContent = anchorData.id; // Usar ID del ancla
                dot.title = `Anclaje ${anchorData.id}`;
                dot.style.position = 'absolute'; 
                dot.style.left = anchorPixelX + 'px';
                dot.style.top = anchorPixelY + 'px';
                dot.style.transform = 'translate(-50%, -50%)'; 
                viz.appendChild(dot);
                vizElements.anchorPoints[anchorData.id] = dot; 

                const circle = document.createElement('div');
                circle.className = 'distance-circle';
                circle.style.position = 'absolute'; 
                circle.style.left = anchorPixelX + 'px';
                circle.style.top = anchorPixelY + 'px';
                const radius = (anchorData.dist / 100) * scale; // Convertir cm a metros para visualización
                circle.style.width = radius * 2 + 'px';
                circle.style.height = radius * 2 + 'px';
                circle.style.transform = 'translate(-50%, -50%)'; 
                viz.appendChild(circle);
                vizElements.distanceCircles[anchorData.id] = circle; 
            });
        }

        const tagPoint = document.createElement('div');
        tagPoint.className = 'tag-point';
        tagPoint.style.position = 'absolute'; 
        tagPoint.style.left = tagPosition.x + 'px';
        tagPoint.style.top = tagPosition.y + 'px';
        tagPoint.style.transform = 'translate(-50%, -50%)'; 
        viz.appendChild(tagPoint);
        vizElements.tagPoint = tagPoint; 

        visualizationInitialized = true;
      } else {
        const scale = 40; 
        const currentAnchorsToRender = window.currentAnchorsData || anchors;

        // Actualizar círculos de distancia solo si hay datos de anclas
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData) => {
                const circle = vizElements.distanceCircles[anchorData.id];
                if (circle) {
                    const radius = (anchorData.dist / 100) * scale; // Convertir cm a metros para actualización
                    const currentWidth = parseFloat(circle.style.width) || 0;
                    if (radius >= 0 && Math.abs(radius * 2 - currentWidth) > 0.1) { 
                        circle.style.width = radius * 2 + 'px';
                        circle.style.height = radius * 2 + 'px';
                    }
                }
            });
        }

        // Actualizar posición del tag (debe hacerse siempre si tagPoint existe)
        const tagPoint = vizElements.tagPoint;
        if (tagPoint && typeof tagPosition.x === 'number' && typeof tagPosition.y === 'number' && !isNaN(tagPosition.x) && !isNaN(tagPosition.y)) {
           console.log("Dibujando TAG en (píxeles):", tagPosition.x, tagPosition.y); // Para depuración
           // Actualizar posición absoluta del tag
           tagPoint.style.left = tagPosition.x + 'px';
           tagPoint.style.top  = tagPosition.y + 'px';
           // Mantener centrado el punto
           tagPoint.style.transform = 'translate(-50%, -50%)';
        } else if (tagPoint) {
           console.log("Posición de TAG inválida o tagPoint no listo:", tagPosition.x, tagPosition.y); // Para depuración
           // Opcional: ocultar el tag si la posición no es válida, en lugar de dejarlo donde estaba
           // tagPoint.style.transform = 'translate(-10000px, -10000px)'; 
        }
      }
    }
    // --- Fin Optimización Visualización ---

    // Solicitar actualización de datos
    function requestUpdate() {
      fetchData();
    }
    
    // Primera carga en caso de que el WebSocket tarde en conectar
    fetchData();

    // Polling de respaldo cada 1 s solo si WS está cerrado
    setInterval(() => {
      if (socket.readyState !== WebSocket.OPEN) fetchData();
    }, 1000);
  </script>
</body>
</html>
)rawliteral";

// ===== FUNCIONES =====

// Filtro de Kalman para distancias
float kalmanFilterDistance(float measurement, int anchor_id) {
  kalman_dist[anchor_id][1] = kalman_dist[anchor_id][1] + kalman_dist_q;
  float k = kalman_dist[anchor_id][1] / (kalman_dist[anchor_id][1] + kalman_dist_r);
  kalman_dist[anchor_id][0] = kalman_dist[anchor_id][0] + k * (measurement - kalman_dist[anchor_id][0]);
  kalman_dist[anchor_id][1] = (1 - k) * kalman_dist[anchor_id][1];
  return kalman_dist[anchor_id][0];
}

// Filtro de Kalman para posición 2D
void kalmanFilterPosition(float measured_x, float measured_y) {
  kalman_p_x = kalman_p_x + kalman_q;
  kalman_p_y = kalman_p_y + kalman_q;
  
  float k_x = kalman_p_x / (kalman_p_x + kalman_r);
  float k_y = kalman_p_y / (kalman_p_y + kalman_r);
  
  kalman_x = kalman_x + k_x * (measured_x - kalman_x);
  kalman_y = kalman_y + k_y * (measured_y - kalman_y);
  
  kalman_p_x = (1 - k_x) * kalman_p_x;
  kalman_p_y = (1 - k_y) * kalman_p_y;
  
  tagPositionX = kalman_x;
  tagPositionY = kalman_y;
}

// Configura la conexión WiFi
void setupWiFi() {
  if (USE_AP_MODE) {
    Serial.print("Configuring WiFi mode AP...");
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.print("AP created. IP address: ");
    Serial.println(WiFi.softAPIP());
  } else {
    Serial.print("Configuring WiFi mode STA...");
    WiFi.mode(WIFI_STA);
    Serial.println(" Done.");
    Serial.print("Beginning WiFi connection to SSID: ");
    Serial.println(STA_SSID);
    WiFi.begin(STA_SSID, STA_PASS);

    Serial.print("Attempting WiFi connection (15s timeout)...");
    unsigned long startAttemptTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < 15000) { // 15-second timeout
      Serial.print("."); // Print dots while waiting
      delay(500);
    }
    Serial.println(); // Newline after dots

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("WiFi connected successfully!");
      Serial.print("IP address: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.print("WiFi connection FAILED! Status: ");
      Serial.println(WiFi.status()); // Print the specific failure status code
      // WL_NO_SSID_AVAIL = 1, WL_CONNECT_FAILED = 3, WL_CONNECTION_LOST = 4, WL_DISCONNECTED = 6 etc.
    }
  }
}

// Genera los datos en formato JSON usando ArduinoJson
String getDataJson() {
  // Calcular el tamaño necesario para el JSON
  const int capacity = JSON_OBJECT_SIZE(4) + 
                       JSON_ARRAY_SIZE(NUM_ANCHORS) + 
                       NUM_ANCHORS * JSON_OBJECT_SIZE(3) + 
                       JSON_OBJECT_SIZE(2) + 
                       JSON_OBJECT_SIZE(NUM_ANCHORS);
                       
  StaticJsonDocument<capacity> doc;

  // Añadir nivel de batería
  doc["battery"] = 85;
  
  // Añadir datos de anclajes
  JsonArray anchorsArray = doc.createNestedArray("anchors");
  for (int i = 0; i < NUM_ANCHORS; i++) {
    JsonObject anchorObject = anchorsArray.createNestedObject();
    anchorObject["id"] = ID_PONG[i];
    anchorObject["dist"] = isnan(anchor_distance[i]) || isinf(anchor_distance[i]) ? 0.0 : (anchor_distance[i] * 100); // Metros a cm para WebSocket
    anchorObject["rssi"] = isnan(pot_sig[i]) || isinf(pot_sig[i]) ? -100.0 : pot_sig[i];
  }
  
  // Añadir posición del tag
  JsonObject positionObject = doc.createNestedObject("position");
  positionObject["x"] = isnan(tagPositionX) || isinf(tagPositionX) ? 0.0 : tagPositionX;
  positionObject["y"] = isnan(tagPositionY) || isinf(tagPositionY) ? 0.0 : tagPositionY;

  // Serializar JSON a String
  String output;
  serializeJson(doc, output);
  return output;
}

// Configura el servidor web
void setupWebServer() {
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *req){
    req->send_P(200, "text/html", INDEX_HTML);
  });
  server.on("/data", HTTP_GET, [](AsyncWebServerRequest *req){
    req->send(200, "application/json", getDataJson());
  });

  ws.onEvent([](AsyncWebSocket *s, AsyncWebSocketClient *c, AwsEventType t, void*, uint8_t*, size_t){
    if(t==WS_EVT_CONNECT){
      Serial.printf("[WS] Cliente #%u conectado, IP %s\n", c->id(), c->remoteIP().toString().c_str());
    }
  });
  server.addHandler(&ws);
  server.begin();
  Serial.println("✓ AsyncWebServer + WebSocket iniciado en :80");
}

// Envía datos por UDP (broadcasting)
void broadcastUDP() {
  if(WiFi.status() == WL_CONNECTED && !USE_AP_MODE) {
    String udpMessage = "Tag: " + String(TAG_ID) + ", LastAnchor: " + String(last_anchor_id);
    udp.beginPacket(broadcastIP, UDP_PORT);
    udp.print(udpMessage); 
    udp.endPacket();
  }
}

// Comprueba si el tag está dentro de alguna zona definida
void checkZones() {
  bool inAnyZone = false;
  
  for (int i = 0; i < NUM_ZONES; i++) {
    float dx = tagPositionX - zones[i].x;
    float dy = tagPositionY - zones[i].y;
    float distance = sqrt(dx*dx + dy*dy);
    
    if (distance <= zones[i].radius) {
      inAnyZone = true;
      
      if (!zones[i].tagInside) {
        zones[i].tagInside = true;
        zones[i].entryTime = millis();
        
        Serial.print("Tag entró en zona ");
        Serial.println(i);
      }
      
      if (millis() - zones[i].entryTime >= zones[i].minStayTime && !zones[i].stayTimeReached) {
        zones[i].stayTimeReached = true;
        
        Serial.print("Tiempo mínimo alcanzado en zona ");
        Serial.println(i);
      }
    } else {
      if (zones[i].tagInside) {
        zones[i].tagInside = false;
        zones[i].stayTimeReached = false;
        
        Serial.print("Tag salió de zona ");
        Serial.println(i);
      }
    }
  }
}

// --- Funciones MQTT --- 

void reconnectMQTT() {
  // Loop until we're reconnected
  if (!client.connected()) {
    long now = millis();
    // Try to reconnect every 5 seconds
    if (now - lastMqttReconnectAttempt > 5000) {
      lastMqttReconnectAttempt = now;
      Serial.print("Attempting MQTT connection...");
      // Create a unique client ID using MAC address and TAG_ID
      String clientId = "ESP32-Tag-";
      clientId += String(TAG_ID);
      clientId += "-";
      clientId += WiFi.macAddress();

      // Attempt to connect
      if (client.connect(clientId.c_str())) {
        Serial.println("connected");
      } else {
        Serial.print("failed, rc=");
        Serial.print(client.state());
        Serial.println(" try again in 5 seconds");
      }
    }
  }
}

void publishStatus() {
   // BUFFERING ESTABILIZADO SIMPLIFICADO - 80ms fijo = 12.5 Hz
   static unsigned long lastPublish = 0;
   unsigned long currentTime = millis();
   
   // Control de timing estricto - EXACTAMENTE cada 80ms
   if (currentTime - lastPublish < 80) {
     return; // Salir inmediatamente si no ha pasado el tiempo
   }
   
   // Verificar conexión MQTT una sola vez por envío
   if (!client.connected()) {
     Serial.println("[MQTT] Desconectado, saltando envío");
     return;
   }
   
   // Actualizar timestamp ANTES de procesar para evitar overlaps
   lastPublish = currentTime;
   
   // Preparar JSON optimizado con validación mejorada
   StaticJsonDocument<512> doc;
   doc["tag_id"] = TAG_ID;
   doc["last_anchor_id"] = last_anchor_id;
   doc["timestamp_ms"] = currentTime;

   // POSICIÓN con validación NaN/Inf más robusta
   JsonObject position = doc.createNestedObject("position");
   float safe_x = (isnan(tagPositionX) || isinf(tagPositionX)) ? 0.0 : tagPositionX;
   float safe_y = (isnan(tagPositionY) || isinf(tagPositionY)) ? 0.0 : tagPositionY;
   position["x"] = safe_x;
   position["y"] = safe_y;

   // DISTANCIAS con validación estricta
   JsonObject anchorDistances = doc.createNestedObject("anchor_distances");
   for (int i = 0; i < NUM_ANCHORS; i++) {
     String anchorKey = String(ID_PONG[i]);
     float dist = anchor_distance[i];
     
     // Validación más estricta: 0.1-20m rango realista indoor
     if (isnan(dist) || isinf(dist) || dist < 0.1 || dist > 20.0) {
       dist = 0.0;
     }
     anchorDistances[anchorKey] = dist;
   }

   // Serializar y enviar con manejo de errores mejorado
   char buffer[512];
   size_t n = serializeJson(doc, buffer);

   if (client.publish(status_topic, buffer, n)) {
     // Éxito silencioso para no spam logs
     static int successCount = 0;
     if (++successCount % 125 == 0) { // Log cada ~10 segundos (125 * 80ms)
       Serial.printf("[MQTT] %d mensajes enviados OK (12.5Hz estable)\n", successCount);
     }
   } else {
     Serial.printf("[MQTT] Error enviando posición en timestamp %lu\n", currentTime);
   }
}

void broadcastWebSocket(){
  static uint32_t lastWs=0;
  if(millis()-lastWs<16) return; // 60 fps máx (16 ms) - máxima fluidez
  String json=getDataJson();
  ws.textAll(json);
  lastWs=millis();
}

// ===== FUNCIÓN DE BUFFERING ESTABILIZADO =====
void addToStabilizedBuffer(float x, float y) {
  unsigned long currentTime = millis();
  
  // Añadir al buffer circular
  stable_buffer.position_x_buffer[stable_buffer.buffer_head] = x;
  stable_buffer.position_y_buffer[stable_buffer.buffer_head] = y;
  stable_buffer.timestamp_buffer[stable_buffer.buffer_head] = currentTime;
  
  stable_buffer.buffer_head = (stable_buffer.buffer_head + 1) % 8;
  if (stable_buffer.buffer_count < 8) {
    stable_buffer.buffer_count++;
  }
}

bool getStabilizedPosition(float* x, float* y) {
  unsigned long currentTime = millis();
  
  // Verificar si es momento de enviar
  if (currentTime - stable_buffer.last_output_time < stable_buffer.OUTPUT_INTERVAL) {
    return false;
  }
  
  if (stable_buffer.buffer_count == 0) {
    return false;
  }
  
  // Calcular posición promedio ponderada (más peso a datos recientes)
  float sum_x = 0, sum_y = 0, total_weight = 0;
  
  for (int i = 0; i < stable_buffer.buffer_count; i++) {
    int idx = (stable_buffer.buffer_head - 1 - i + 8) % 8;
    float age = currentTime - stable_buffer.timestamp_buffer[idx];
    float weight = exp(-age / 200.0); // Decaimiento exponencial
    
    sum_x += stable_buffer.position_x_buffer[idx] * weight;
    sum_y += stable_buffer.position_y_buffer[idx] * weight;
    total_weight += weight;
  }
  
  if (total_weight > 0) {
    *x = sum_x / total_weight;
    *y = sum_y / total_weight;
    stable_buffer.last_output_time = currentTime;
    return true;
  }
  
  return false;
}

// ===== CONTROL DE FLUJO MQTT MEJORADO =====
bool checkMQTTFlowControl() {
  unsigned long currentTime = millis();
  
  // Verificar conexión periódicamente
  if (currentTime - mqtt_flow.last_connection_check > mqtt_flow.CONNECTION_CHECK_INTERVAL) {
    mqtt_flow.last_connection_check = currentTime;
    
    if (!client.connected()) {
      mqtt_flow.consecutive_failures++;
      if (mqtt_flow.consecutive_failures >= mqtt_flow.MAX_CONSECUTIVE_FAILURES) {
        mqtt_flow.flow_control_active = true;
        Serial.println("[MQTT] Flow control activado por desconexión");
      }
      return false;
    } else {
      // Conexión OK, resetear contadores
      mqtt_flow.consecutive_failures = 0;
      mqtt_flow.flow_control_active = false;
    }
  }
  
  return !mqtt_flow.flow_control_active;
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== UWB TAG with WiFi, Web Server, and SD Logging ===\n");
  
  setupWiFi();
  
  setupWebServer();
  
  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  snprintf(status_topic, sizeof(status_topic), "%s%d/status", "uwb/tag/", TAG_ID); // Construir topic de estado ej: uwb/tag/1/status
  Serial.print("MQTT Status topic set to: ");
  Serial.println(status_topic);

  DW3000.begin();
  DW3000.hardReset();
  delay(200);
  
  while (!DW3000.checkForIDLE()) {
    Serial.println("[ERROR] IDLE1 FAILED");
    delay(100);
  }

  DW3000.softReset();
  delay(200);

  if (!DW3000.checkForIDLE()) {
    Serial.println("[ERROR] IDLE2 FAILED");
    delay(100);
  }

  DW3000.init();
  DW3000.setupGPIO();
  Serial.println("[INFO] DW3000 inicializado correctamente.");

  DW3000.configureAsTX();
  DW3000.clearSystemStatus(); 

  lastActivityTime = millis();
  lastUpdate = millis();
}

void loop() {
  ws.cleanupClients(); // mantener clientes activos (no bloquea)
  // server.handleClient();  // ya no se usa con AsyncWebServer
  
  // Handle MQTT Client
  if (!client.connected()) {
    reconnectMQTT(); // Try to reconnect if disconnected
  }
  client.loop(); // Allow MQTT client to process messages/maintain connection

  unsigned long currentMillis = millis();
  
  if (!lowPowerMode && (currentMillis - lastActivityTime >= SLEEP_TIMEOUT)) {
    Serial.println("Entrando en modo de bajo consumo...");
    lowPowerMode = true;
    updateInterval = 1000;
  }
  
  if (currentMillis - lastUpdate >= updateInterval) {
    lastUpdate = currentMillis;
    lastActivityTime = currentMillis;
    
    unsigned long time_in_cycle = currentMillis % TDMA_CYCLE_MS;
    unsigned long assigned_slot_start = (TAG_ID - 1) * TDMA_SLOT_DURATION_MS;
    unsigned long assigned_slot_end = assigned_slot_start + TDMA_SLOT_DURATION_MS;

    bool is_my_slot = (time_in_cycle >= assigned_slot_start && time_in_cycle < assigned_slot_end);

    if (is_my_slot && !lowPowerMode) { 
        lastActivityTime = currentMillis; // Update activity time when ranging

        String dataString = ""; // Declare dataString outside the switch

        // Reset anchor status for this cycle
        for(int k=0; k<NUM_ANCHORS; k++) {
          anchor_responded[k] = false;
        }

        for (int ii = 0; ii < NUM_ANCHORS; ii++) {
          DW3000.setDestinationID(ID_PONG[ii]);
          fin_de_com = 0;
          
          while (fin_de_com == 0) {
            if (waitingForResponse && ((millis() - timeoutStart) >= RESPONSE_TIMEOUT)) {
              Serial.print("Timeout REFORZADO para ancla ID: "); 
              Serial.println(ID_PONG[ii]);

              DW3000.softReset();
              delay(100); 
              DW3000.init(); 
              DW3000.configureAsTX(); 
              DW3000.clearSystemStatus(); 

              anchor_distance[ii] = 0;
              pot_sig[ii] = -120.0f; // Valor de dBm muy bajo para indicar mala calidad/sin señal
              anchor_responded[ii] = false;
              
              curr_stage = 0; 
              ranging_time = 0;
              waitingForResponse = false; 
              fin_de_com = 1; 
              
              Serial.println("[INFO] TAG DW3000 re-inicializado post-timeout.");
              break; 
            }
            
            switch (curr_stage) {
              case 0:
                t_roundA = 0;
                t_replyA = 0;
                DW3000.ds_sendFrame(1);
                tx = DW3000.readTXTimestamp();
                curr_stage = 1;
                timeoutStart = millis();
                waitingForResponse = true;
                break;
                
              case 1:
                if (rx_status = DW3000.receivedFrameSucc()) {
                  DW3000.clearSystemStatus(); // Limpiar estado del sistema después de la recepción
                  if ((rx_status == 1) && (DW3000.getDestinationID() == ID_PONG[ii])) {
                    if (DW3000.ds_isErrorFrame()) {
                      Serial.println("[WARNING] Error frame detected! Reverting to stage 0.");
                      curr_stage = 0;
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com), dejamos que intente de nuevo o timeoutee si el ancla sigue mal
                    } else if ((DW3000.getDestinationID() != ID_PONG[ii])) {
                      // Mensaje para otra ancla, ignorar y seguir esperando (o timeout)
                      break; // Sale del switch, pero no del while, sigue esperando respuesta para ID_PONG[ii]
                    } else if (DW3000.ds_getStage() != 2) {
                      Serial.println("[WARNING] Stage incorrecto del ancla. Enviando error frame.");
                      DW3000.ds_sendErrorFrame();
                      curr_stage = 0; // Reiniciar protocolo para esta ancla
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com), dejamos que intente de nuevo o timeoutee
                    } else {
                      curr_stage = 2;
                      waitingForResponse = false;
                    }
                  } else { // rx_status != 1 O el ID no es el correcto
                    Serial.print("[ERROR] Receiver Error (case 1) o ID incorrecto. RX_STATUS: ");
                    Serial.print(rx_status);
                    Serial.print(", DEST_ID: ");
                    Serial.println(DW3000.getDestinationID());
                    
                    DW3000.softReset();
                    delay(100);
                    DW3000.init();
                    DW3000.configureAsTX();
                    DW3000.clearSystemStatus();

                    anchor_distance[ii] = 0;
                    pot_sig[ii] = -120.0f; // Valor de dBm muy bajo para indicar mala calidad/sin señal
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1; 
                    Serial.println("[INFO] TAG DW3000 re-inicializado post-receiver error (case 1).");
                  }
                }
                break;
                
              case 2:
                rx = DW3000.readRXTimestamp();
                DW3000.ds_sendFrame(3);
                t_roundA = rx - tx;
                tx = DW3000.readTXTimestamp();
                t_replyA = tx - rx;
                curr_stage = 3;
                timeoutStart = millis();
                waitingForResponse = true;
                break;
                
              case 3:
                if (rx_status = DW3000.receivedFrameSucc()) {
                  DW3000.clearSystemStatus(); // Limpiar estado del sistema después de la recepción
                  if (rx_status == 1) { // ASUMIMOS que el PONG no cambia el Destination ID para el último msg
                    if (DW3000.ds_isErrorFrame()) {
                      Serial.println("[WARNING] Error frame detected (case 3)! Reverting to stage 0.");
                      curr_stage = 0;
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com)
                    } else {
                      waitingForResponse = false;
                      clock_offset = DW3000.getRawClockOffset();
                      curr_stage = 4;
                    }
                  } else { // rx_status != 1
                    Serial.print("[ERROR] Receiver Error (case 3)! RX_STATUS: ");
                    Serial.println(rx_status);

                    DW3000.softReset();
                    delay(100);
                    DW3000.init();
                    DW3000.configureAsTX();
                    DW3000.clearSystemStatus();

                    anchor_distance[ii] = 0;
                    pot_sig[ii] = -120.0f; // Valor de dBm muy bajo para indicar mala calidad/sin señal
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1; 
                    Serial.println("[INFO] TAG DW3000 re-inicializado post-receiver error (case 3).");
                  }
                }
                break;
                
              case 4: {
                ranging_time = DW3000.ds_processRTInfo(t_roundA, t_replyA, DW3000.read(0x12, 0x04), DW3000.read(0x12, 0x08), clock_offset);
                distance = DW3000.convertToCM(ranging_time);
                
                // === CONVERSIÓN A METROS DIRECTAMENTE ===
                float distance_meters = distance / 100.0; // Convertir cm a metros una sola vez
                
                // Leer la potencia de la señal recibida y almacenarla
                pot_sig[ii] = DW3000.getSignalStrength();

                anchor_responded[ii] = true; 
                if (distance_meters > 0) { 
                    anchor_distance[ii] = kalmanFilterDistance(distance_meters, ii); // Ya en metros
                } else {
                    anchor_distance[ii] = 0; 
                    // Si la distancia es inválida, también deberíamos considerar la señal como mala para WLS
                    // pot_sig[ii] = -120.0f; // Opcional: si distancia es 0, forzar mala señal para WLS
                }
 
                // Formatear logs: TODO EN METROS para consistencia completa del sistema
                dataString = String(TAG_ID) + "," +
                                  String(millis()) + "," +
                                  String(ID_PONG[ii]) + "," +
                                  String(distance_meters, 4) + "," +       // Raw en metros (4 decimales)
                                  String(anchor_distance[ii], 4) + "," +   // Filtrada en metros (4 decimales)
                                  String(pot_sig[ii], 2) + "," +
                                  String(anchor_responded[ii] ? 1 : 0); 
                
                // --- Publish SINGLE log line IMMEDIATELY --- 
                if (client.connected()) {
                    if (!client.publish(log_topic, dataString.c_str())) {
                       Serial.println("MQTT Publish Failed (single log line)"); 
                    }
                } else {
                    // Optional: Indicate MQTT isn't connected when trying to send log
                    // Serial.println("MQTT disconnected, cannot send log line."); 
                }
                // ----------------------------------------------
 
                // Respond with a PONG
                curr_stage = 0;
                fin_de_com = 1;
                
                // REMOVED: delay(50); // This was slowing down the measurement cycle
                break;
              }
                
              default:
                Serial.print("[ERROR] Estado desconocido (");
                Serial.print(curr_stage);
                Serial.println("). Volviendo a estado 0.");
                curr_stage = 0;
                break;
            }
          }
        }
        
        // Count responding anchors
        int responding_anchors = 0;
        for(int k=0; k<NUM_ANCHORS; k++) {
          if(anchor_responded[k]) responding_anchors++;
        }

        // Only trilaterate if enough anchors responded
        if (responding_anchors >= 3) { 
          // Calcular posición del tag usando trilateración inteligente (INDOOR)
          
          float distances[NUM_ANCHORS];
          for (int i = 0; i < NUM_ANCHORS; i++) {
            distances[i] = anchor_distance[i]; // Ya están en metros
          }


          // === Selección inteligente de 3 anclas para evitar degeneración ===
          int responded_idx[NUM_ANCHORS];
          int r_count = 0;
          for (int i = 0; i < NUM_ANCHORS; i++) {
            if (anchor_responded[i]) {
              responded_idx[r_count++] = i;
            }
          }

          if (r_count >= 3) {
            // === TRILATERACIÓN INTELIGENTE OPCIÓN A ===
            int selected_anchors[3];
            bool selection_successful = selectOptimalAnchors(responded_idx, r_count, selected_anchors);
            
            int a0, a1, a2;
            if (selection_successful) {
              a0 = selected_anchors[0];
              a1 = selected_anchors[1]; 
              a2 = selected_anchors[2];
            } else {
              // Fallback a método original si falla la selección inteligente
              Serial.println("[TRILAT-A] Fallback a método básico");
              float best_det = 0.0f;
              a0 = responded_idx[0]; a1 = responded_idx[1]; a2 = responded_idx[2];
              
              for (int i = 0; i < r_count - 2; i++) {
                for (int j = i + 1; j < r_count - 1; j++) {
                  for (int k = j + 1; k < r_count; k++) {
                    int ia = responded_idx[i];
                    int ib = responded_idx[j];
                    int ic = responded_idx[k];
                    
                    float A_tmp = 2 * (anchorsPos[ib][0] - anchorsPos[ia][0]);
                    float B_tmp = 2 * (anchorsPos[ib][1] - anchorsPos[ia][1]);
                    float D_tmp = 2 * (anchorsPos[ic][0] - anchorsPos[ib][0]);
                    float E_tmp = 2 * (anchorsPos[ic][1] - anchorsPos[ib][1]);
                    float det_tmp = A_tmp * E_tmp - B_tmp * D_tmp;
                    
                    if (fabs(det_tmp) > fabs(best_det)) {
                      best_det = det_tmp;
                      a0 = ia; a1 = ib; a2 = ic;
                    }
                  }
                }
              }
            }

            float x1 = anchorsPos[a0][0], y1 = anchorsPos[a0][1];
            float x2 = anchorsPos[a1][0], y2 = anchorsPos[a1][1]; 
            float x3 = anchorsPos[a2][0], y3 = anchorsPos[a2][1];
            
            float r1 = distances[a0], r2 = distances[a1], r3 = distances[a2];
            
            // Ecuaciones de trilateración básica
            float A = 2 * (x2 - x1);
            float B = 2 * (y2 - y1);
            float C = r1*r1 - r2*r2 - x1*x1 + x2*x2 - y1*y1 + y2*y2;
            float D = 2 * (x3 - x2);
            float E = 2 * (y3 - y2);
            float F = r2*r2 - r3*r3 - x2*x2 + x3*x3 - y2*y2 + y3*y3;
            
            float det = A * E - B * D;
            if (abs(det) > 0.0001) {
              float x = (C * E - F * B) / det;
              float y = (A * F - D * C) / det;
              
              // === LÍMITES SUAVES para evitar tirones bruscos ===
              float bounded_x = x;
              float bounded_y = y;
              
              // Aplicar límites suaves con transición gradual
              if (x < -6.9f) {
                bounded_x = -6.9f + (x + 6.9f) * 0.1f; // Reducir en 90% la extrapolación
              } else if (x > 6.8f) {
                bounded_x = 6.8f + (x - 6.8f) * 0.1f;
              }
              
              if (y < -3.5f) {
                bounded_y = -3.5f + (y + 3.5f) * 0.1f;
              } else if (y > 10.36f) {
                bounded_y = 10.36f + (y - 10.36f) * 0.1f;
              }
              
              // === APLICAR FILTRO KALMAN OBLIGATORIO ===
              kalmanFilterPosition(bounded_x, bounded_y);
              
              // Actualizar timestamp y posición anterior
              last_trilateration_time = millis();
              last_valid_position[0] = tagPositionX;
              last_valid_position[1] = tagPositionY;
              
              checkZones();
            } else {
              // Si determinante muy pequeño, mantener última posición válida
              if (millis() - last_trilateration_time < 2000) {
                tagPositionX = last_valid_position[0];
                tagPositionY = last_valid_position[1];
              }
            }
          }
        }
        
        for (int i = 0; i < NUM_ANCHORS; i++) {
          Serial.print("Anclaje ");
          Serial.print(ID_PONG[i]);
          Serial.print(" ");
          Serial.print(anchor_distance[i], 3); // Mostrar metros con 3 decimales
          Serial.print(" m, Potencia = ");
          Serial.print(pot_sig[i]);
          Serial.println("dBm");
        }
        
        // broadcastUDP();
        
        // MQTT con buffering estabilizado - llamar SIEMPRE, el control está dentro de publishStatus()
        publishStatus();
        
        // Enviar datos por WebSocket de forma continua para la interfaz (≈25-50 fps)
        broadcastWebSocket();

        fin_de_com = 0;
    }
  } // <<< ADDED: Closing brace for if (currentMillis - lastUpdate >= updateInterval)

    // === Difusión WebSocket cada actualización incluso fuera de mi slot ===
    broadcastWebSocket();
} // Closing brace for loop()
