#include <SPI.h>
#include "DW3000.h"
#include <WiFi.h>
#include <WebServer.h>
#define MQTT_MAX_PACKET_SIZE 2048 // MEJORA TFG v2.1: Robustez para 5 anclas
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h> // MEJORA TFG: Watchdog para robustez
#include <math.h> // TFG v2.1-FINAL: Dependencias matemáticas explícitas (isnan, isinf, sqrt)
#include "../common/config.h" // TFG v2.1: Configuración centralizada

// TFG v2.1-FINAL: Constante para escalado visual consistente
// NOTA: PIXELS_PER_M ahora se define en config.h para evitar duplicación

// TFG v2.1-PRODUCTION: Control de debug (0 para versión release)
#define DEBUG_MODE 0

// TFG v2.1-PRODUCTION: Control de interfaz web (0 para deshabilitar y ahorrar RAM)
#define ENABLE_WEB_INTERFACE 1

#if DEBUG_MODE
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
#endif

// ===== INFORMACIÓN DE FIRMWARE PARA TFG =====
#define FW_VERSION "v2.1-PRODUCTION-TFG-2024"
#define BUILD_DATE __DATE__ " " __TIME__

// ===== IDENTIFICACIÓN DEL TAG =====
#define TAG_ID 1 // 

// ===== CONFIGURACIÓN WiFi =====
#define USE_AP_MODE false
#define AP_SSID "UWB_TAG_AP"
#define AP_PASS "12345678"
#define STA_SSID "iPhone de Nicolas"
#define STA_PASS "12345678"

// Configuraciones del servidor web
#define HTTP_PORT 80
WebServer server(HTTP_PORT);

// MQTT Configuration
const char* mqtt_server = "172.20.10.3"; // Broker IP (Your PC)
const int mqtt_port = 1883;
const char* log_topic = "uwb/tag/logs";       // Topic for detailed CSV logs
char status_topic[30];                      // Topic for simple status (constructed in setup)
WiFiClient espClient;
PubSubClient client(espClient);

// MEJORA TFG OPCIONAL: Para producción con TLS (descomentarar si broker lo soporta)
// #include <WiFiClientSecure.h>
// WiFiClientSecure secureClient; 
// PubSubClient client(secureClient);
// Y en setup(): secureClient.setInsecure(); // o cargar certificados

// TFG v2.1-FINAL: Variables logServer eliminadas (migrado a MQTT)

// ===== CONFIGURACIÓN COHERENTE DEL SISTEMA =====
// NOTA: Las constantes principales están definidas en config.h

// ===== TDMA Configuration OPTIMIZADA =====
constexpr unsigned long TDMA_CYCLE_MS = 500;   // Reducido de 1000ms a 500ms para mayor frecuencia
constexpr unsigned long TDMA_SLOT_DURATION_MS = 100; // Reducido de 500ms a 100ms por tag

// ===== CONFIGURACIÓN DE RANGING OPTIMIZADA =====
constexpr int ROUND_DELAY = 50;  // Reducido de 100 a 50
static int rx_status;
// TFG v2.1-PRODUCTION: frame_buffer y tx_status eliminados (no utilizados)

// Estados del ranging
static int curr_stage = 0;

static int t_roundA = 0;
static int t_replyA = 0;

static long long rx = 0;
static long long tx = 0;

static int clock_offset = 0;
static int ranging_time = 0;
static float distance = 0;

// Configuraciones para mediciones y filtrado MEJORADAS
int ID_PONG[NUM_ANCHORS] = {10, 20, 30, 40, 50};
float anchor_distance[NUM_ANCHORS] = {0};
float pot_sig[NUM_ANCHORS] = {0};
// TFG v2.1-PRODUCTION: distance_buffer, anchor_avg, buffer_index y NUM_MEASUREMENTS eliminados (no utilizados)
static int fin_de_com = 0;
bool anchor_responded[NUM_ANCHORS] = {false};

// NUEVA: Variables para detección de outliers
float last_valid_distances[NUM_ANCHORS] = {0};
unsigned long last_measurement_time[NUM_ANCHORS] = {0};
#define MAX_DISTANCE_CHANGE_PER_MS 0.008f   // 8 m/s -> 0.008 m/ms

// Variables para timeout OPTIMIZADAS
unsigned long timeoutStart = 0;
bool waitingForResponse = false;
constexpr unsigned long RESPONSE_TIMEOUT = 100; // Reducido de 200ms a 100ms para fútbol sala

// TFG v2.1-FINAL: State machine para reset DW3000 no bloqueante
enum ResetState { RESET_IDLE, RESET_REQUESTED, RESET_IN_PROGRESS };
ResetState resetState = RESET_IDLE;
unsigned long resetStartTime = 0;
int consecutiveTimeouts[NUM_ANCHORS] = {0}; // MEJORA TFG: Contar timeouts consecutivos por ancla
bool anchorDead[NUM_ANCHORS] = {false};     // MEJORA TFG: Marcar anclas "muertas" temporalmente

// Variables para gestor de estados OPTIMIZADAS
unsigned long lastUpdate = 0;
unsigned long updateInterval = 25;  // Reducido de 50ms a 25ms para 40Hz

// Variables para modo de bajo consumo
unsigned long lastActivityTime = 0;
const unsigned long SLEEP_TIMEOUT = 300000;
bool lowPowerMode = false;

// Variables para Filtro de Kalman ADAPTATIVO MEJORADO
float kalman_dist[NUM_ANCHORS][2] = { {0} };
float kalman_dist_q = 0.02; // Reducido para mayor estabilidad en movimientos deportivos
float kalman_dist_r = 0.15; // Aumentado ligeramente para compensar ruido UWB

// Variables para posición con FILTRO KALMAN PREDICTIVO
float kalman_x = 0.0;
float kalman_y = 0.0;
float kalman_vx = 0.0;  // NUEVA: Velocidad X
float kalman_vy = 0.0;  // NUEVA: Velocidad Y
float kalman_p_x = 1.0;
float kalman_p_y = 1.0;
float kalman_p_vx = 1.0; // NUEVA: Covarianza velocidad X
float kalman_p_vy = 1.0; // NUEVA: Covarianza velocidad Y
float kalman_q = 0.05;   // Proceso de posición
float kalman_q_vel = 2.0; // NUEVA: Proceso de velocidad (deportes rápidos)
float kalman_r = 0.08;   // Observación mejorada para fútbol sala

// Variables para la posición del tag
float tagPositionX = 0.0;
float tagPositionY = 0.0;
float tagVelocityX = 0.0; // NUEVA: Velocidad estimada X
float tagVelocityY = 0.0; // NUEVA: Velocidad estimada Y

// Variables para predicción de movimiento
unsigned long lastPositionUpdate = 0;
// TFG v2.1-FINAL: predicted_x/predicted_y ahora son locales en predictFuturePosition()

// NUEVA: Estructura para zonas de fútbol sala
#define NUM_ZONES 6
struct Zone {
  float x;
  float y;
  float radius;
  bool tagInside;
  unsigned long entryTime;
  unsigned long minStayTime;
  bool stayTimeReached;
  const char* name;
};

// NUEVA: Definición de zonas específicas de fútbol sala
Zone zones[NUM_ZONES] = {
  {2.0, 4.0, 3.0, false, 0, 1000, false, "Area_Porteria_1"},
  {38.0, 4.0, 3.0, false, 0, 1000, false, "Area_Porteria_2"}, 
  {20.0, 10.0, 3.0, false, 0, 2000, false, "Centro_Campo"},
  {10.0, 10.0, 5.0, false, 0, 1500, false, "Medio_Campo_1"},
  {30.0, 10.0, 5.0, false, 0, 1500, false, "Medio_Campo_2"},
  {20.0, 2.0, 8.0, false, 0, 500, false, "Banda_Lateral"}
};

// Variables para MQTT y Estado
unsigned long lastMqttReconnectAttempt = 0;
unsigned long lastStatusUpdate = 0;
constexpr long statusUpdateInterval = 2000; // Aumentado a cada 2 segundos para fútbol sala
String last_anchor_id = "N/A";

// TFG v2.1-FINAL: Buffer MQTT robusto con validación completa
// CÁLCULO DEL TAMAÑO: formato "%d,%lu,%d,%lu,%lu,%d,%d"
// TAG_ID(3) + millis(10) + ID_PONG(2) + distance(10) + anchor_distance(10) + pot_sig(4) + responded(1) + comas(6) + null(1) = 47 chars
// Margen de seguridad: 160 bytes = 47 * 3.4 = 240% de margen
char pendingMqttData[160] = {0};
bool mqttPublishPending = false;
// TFG v2.1-FINAL: Validación de capacidad del buffer MQTT (47 chars + margen 240% = 160 bytes)
static_assert(sizeof(pendingMqttData) >= 160, "Buffer MQTT insuficiente para formato CSV");

// TFG v2.1-FINAL: Macro para snprintf seguro con validación en tiempo de compilación
#define SAFE_MQTT_SNPRINTF(buffer, format, ...) do { \
  static_assert(sizeof(buffer) >= 160, "Buffer MQTT demasiado pequeño"); \
  int result = snprintf(buffer, sizeof(buffer), format, __VA_ARGS__); \
  if (result >= sizeof(buffer)) { \
    Serial.println(F("[ERROR] Buffer MQTT overflow detectado!")); \
    buffer[sizeof(buffer)-1] = '\0'; \
  } \
} while(0)

// ===== MÉTRICAS PARA EVALUACIÓN TFG (Capítulo 6) =====
struct PerformanceMetrics {
  unsigned long totalRangingCycles = 0;
  unsigned long successfulTriangulations = 0;
  unsigned long timestampsWithLessThan3Anchors = 0;
  unsigned long timestampsWithFullCoverage = 0;
  float averageUpdateRate = 0.0;
  float averageLatency = 0.0;
  unsigned long lastMetricsReport = 0;
  unsigned long rangingStartTime = 0;
  unsigned long mqttPublishTime = 0;
  unsigned long mqttPublishFailures = 0; // MEJORA TFG: Contar fallos MQTT
} performanceMetrics;

const unsigned long METRICS_REPORT_INTERVAL = 30000; // Reportar métricas cada 30 segundos

#if ENABLE_WEB_INTERFACE
// HTML para la página web integrada (solo si está habilitada)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
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
          #visualization { height: auto; position: relative; border: 1px solid #ccc; background: #fafafa; }
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
    // TFG v2.1-PRODUCTION: Fuente única de verdad (valor inyectado desde C++)
    const PIXELS_PER_M = %%PIXELS_PER_M%%;
    
    let lastUpdate = Date.now();
    let anchors = [];
    let tagPosition = { x: 150, y: 150 }; // Initial guess
    let visualizationInitialized = false;
    let vizElements = { // Store references to visualization DOM elements
        container: null,
        border: null,
        anchorPoints: {},
        distanceCircles: {},
        tagPoint: null
    };
    let anchorListItems = {}; // Store references to anchor list DOM elements

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
      // Detectar si cambió el número de anclas para forzar re-render de visualización
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
              <p>Distancia: <span class="anchor-dist">${anchor.dist.toFixed(1)}</span> cm</p>
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
          anchorDiv.querySelector('.anchor-dist').textContent = anchor.dist.toFixed(1);
          anchorDiv.querySelector('.anchor-rssi').textContent = anchor.rssi.toFixed(1);
        }
      });
      // Podríamos añadir lógica para eliminar anclas si desaparecen, pero asumimos que son fijas
      // --- Fin Optimización Lista Anclas ---

      // Calcular posición del tag por trilateración (ahora usa datos del ESP)
      // Ya no necesitamos la condición de anchors.length >=4 aquí si confiamos en data.position
      calculateTagPosition(); // Esta función ahora usará window.currentTagPositionFromESP
      
      // Actualizar visualización - forzar re-render si cambió el número de anclas
      renderVisualization(anchorsChanged);
      
      // Actualizar estado
      document.getElementById('status').textContent = 'Última actualización: ' + new Date().toLocaleTimeString();
    }

    // Cálculo de posición por trilateración
    function calculateTagPosition() {
        // COHERENCIA TFG: Configuración del espacio físico (cancha oficial de fútbol sala)
        const areaWidth = 40.0;  // metros - CANCHA OFICIAL
        const areaHeight = 20.0; // metros - CANCHA OFICIAL  
        const scale = PIXELS_PER_M; // TFG v2.1-PRODUCTION: Fuente única de verdad
        const margin = 20;       // margen en píxeles
        
        /* ---► nuevo: alto del canvas en píxeles */
        const vizHeight = areaHeight * scale + 2 * margin;
        /* (vizWidth ya no hace falta) */

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

        // TFG v2.1-FINAL: Validación NaN para evitar render corrupto
        if (isNaN(esp_x) || isNaN(esp_y) || esp_x === null || esp_y === null || esp_x === undefined || esp_y === undefined) {
            document.getElementById('tag-position').textContent = "Datos de posición inválidos";
            return;
        }

        // TFG v2.1-PRODUCTION: Log reducido para producción
        // console.log("Posición RECIBIDA del ESP32 (metros):", esp_x, esp_y);
              
        try {
          // Aplicar límites razonables (el ESP32 ya debería haber hecho algo similar)
          const boundedX = Math.max(0, Math.min(areaWidth, esp_x));
          const boundedY = Math.max(0, Math.min(areaHeight, esp_y));
      
          // Convertir a coordenadas de visualización
          const pixelX = margin + boundedX * scale;
          const pixelY = vizHeight - margin - boundedY * scale;
      
          // Suavizar el movimiento: mezclamos la nueva posición con la anterior
          tagPosition.x = tagPosition.x * 0.3 + pixelX * 0.7; 
          tagPosition.y = tagPosition.y * 0.3 + pixelY * 0.7; 
      
          // Actualizar texto de posición
          document.getElementById('tag-position').textContent = 
            `X: ${boundedX.toFixed(2)}m, Y: ${boundedY.toFixed(2)}m (ESP)`;
        } catch (e) {
          console.error('Error en conversión de posición ESP:', e);
          document.getElementById('tag-position').textContent = "Error de visualización";
        }
      }
    
    // --- Optimización: Renderizar visualización actualizando elementos existentes ---
    function renderVisualization(forceReInit = false) {
      const viz = document.getElementById('visualization');
      if (!viz) return; 

      // Forzar re-inicialización si cambió el número de anclas
      if (forceReInit && visualizationInitialized) {
        visualizationInitialized = false;
        viz.innerHTML = ''; // Limpiar visualización existente
        // Resetear referencias de elementos
        vizElements = {
          container: viz,
          border: null,
          anchorPoints: {},
          distanceCircles: {},
          tagPoint: null
        };
      }

      if (!visualizationInitialized) {
        vizElements.container = viz;
        viz.innerHTML = ''; 

        const areaWidth = 40.0;  // COHERENCIA: Cancha oficial
        const areaHeight = 20.0; // COHERENCIA: Cancha oficial
        const scale = PIXELS_PER_M; // TFG v2.1-PRODUCTION: Fuente única de verdad
        const margin = 20;       
        const vizHeight = areaHeight * scale + 2 * margin;

        viz.style.width = (areaWidth * scale + 2 * margin) + 'px';
        viz.style.height = vizHeight + 'px';
        viz.style.position = 'relative'; 

        const currentAnchorsToRender = window.currentAnchorsData || anchors; // Usar datos actualizados

        // COHERENCIA TFG: Posiciones de anclas para cancha oficial de fútbol sala (40x20m)
        const anchorsPosMetros = [
          { id: 10, x: 0.0, y: 0.0 },    // Esquina inferior izquierda
          { id: 20, x: 0.0, y: 20.0 },   // Esquina superior izquierda  
          { id: 30, x: 40.0, y: 0.0 },   // Esquina inferior derecha
          { id: 40, x: 40.0, y: 20.0 },  // Esquina superior derecha
          { id: 50, x: 20.0, y: 10.0 }   // Centro exacto de la cancha
        ];

        const border = document.createElement('div');
        border.style.position = 'absolute';
        border.style.left = margin + 'px';
        border.style.top = margin + 'px';
        border.style.width = (areaWidth * scale) + 'px';
        border.style.height = (areaHeight * scale) + 'px';
        border.style.border = '2px solid #333';
        border.style.boxSizing = 'border-box';
        viz.appendChild(border);
        vizElements.border = border;

        // Crear puntos de anclajes y círculos de distancia solo si hay datos de anclas
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData, i) => {
                const anchorCfg = anchorsPosMetros.find(a => a.id === anchorData.id);
                if (!anchorCfg) return; // Si no hay configuración para este ID de ancla

                const anchorPixelX = margin + anchorCfg.x * scale;
                const anchorPixelY = vizHeight - margin - anchorCfg.y * scale;

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
                const radius = (anchorData.dist / 100) * scale;
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
        const scale = PIXELS_PER_M; // TFG v2.1-PRODUCTION: Fuente única de verdad
        const currentAnchorsToRender = window.currentAnchorsData || anchors;

        // Actualizar círculos de distancia solo si hay datos de anclas
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData) => {
                const circle = vizElements.distanceCircles[anchorData.id];
                if (circle) {
                    const radius = (anchorData.dist / 100) * scale;
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
           // TFG v2.1-PRODUCTION: Logs deshabilitados para producción
           // if (Date.now() % 1000 < 120) {
           //   console.log("Dibujando TAG en (píxeles):", tagPosition.x, tagPosition.y);
           // }
           tagPoint.style.transform = `translate(calc(-50% + ${tagPosition.x}px), calc(-50% + ${tagPosition.y}px))`;
        } else if (tagPoint) {
           // TFG v2.1-PRODUCTION: Logs de error deshabilitados para producción
           // if (Date.now() % 5000 < 120) {
           //   console.log("Posición de TAG inválida o tagPoint no listo:", tagPosition.x, tagPosition.y);
           // }
        }
      }
    }
    // --- Fin Optimización Visualización ---

    // Solicitar actualización de datos
    function requestUpdate() {
      fetchData();
    }
    
    // Actualizar datos periódicamente (cada 150ms - optimizado para ESP32)
    setInterval(fetchData, 150);
    
    // Cargar datos iniciales
    fetchData();
  </script>
</body>
</html>
)rawliteral";
#pragma GCC diagnostic pop
#endif // ENABLE_WEB_INTERFACE

// ===== FUNCIONES =====

// MEJORADO: Filtro de Kalman para distancias con detección de outliers
float kalmanFilterDistance(float measurement, int anchor_id) {
  unsigned long current_time = millis();
  
  // MEJORA TFG: Inicializar filtro con primera medición válida
  if (last_measurement_time[anchor_id] == 0) {
    kalman_dist[anchor_id][0] = measurement; // Primera medición como estado inicial
    last_valid_distances[anchor_id] = measurement;
    last_measurement_time[anchor_id] = current_time;
      DEBUG_PRINT("[KALMAN-INIT] Ancla ");
      DEBUG_PRINT(ID_PONG[anchor_id]);
      DEBUG_PRINT(" inicializada con: ");
      DEBUG_PRINTLN(measurement);
    return measurement;
  }
  
  // Detección de outliers basada en cambio máximo de distancia por tiempo
  if (last_measurement_time[anchor_id] > 0) {
    float time_diff_ms = current_time - last_measurement_time[anchor_id]; // en milisegundos
    if (time_diff_ms < 1.0) time_diff_ms = 1.0; // MEJORA TFG: Evitar división por cero
    if (time_diff_ms > 200.0) time_diff_ms = 200.0; // MEJORA TFG v2.1: Capar para evitar saltos tras timeouts
    float distance_change = abs(measurement - last_valid_distances[anchor_id]);
    float max_change_allowed = MAX_DISTANCE_CHANGE_PER_MS * time_diff_ms;
    
    // Si el cambio de distancia excede el máximo físicamente posible, rechazar medición
    if (distance_change > max_change_allowed * 1.5) { // Margen del 50%
    DEBUG_PRINT("[OUTLIER] Ancla ");
    DEBUG_PRINT(ID_PONG[anchor_id]);
    DEBUG_PRINT(" - Cambio: ");
    DEBUG_PRINT(distance_change);
    DEBUG_PRINT("m > ");
    DEBUG_PRINT(max_change_allowed * 1.5);
    DEBUG_PRINTLN("m (máx permitido)");
      return kalman_dist[anchor_id][0]; // Retornar valor filtrado anterior
    }
  }
  
  kalman_dist[anchor_id][1] = kalman_dist[anchor_id][1] + kalman_dist_q;
  float k = kalman_dist[anchor_id][1] / (kalman_dist[anchor_id][1] + kalman_dist_r);
  kalman_dist[anchor_id][0] = kalman_dist[anchor_id][0] + k * (measurement - kalman_dist[anchor_id][0]);
  kalman_dist[anchor_id][1] = (1 - k) * kalman_dist[anchor_id][1];
  
  // Actualizar historial
  last_valid_distances[anchor_id] = kalman_dist[anchor_id][0];
  last_measurement_time[anchor_id] = current_time;
  
  return kalman_dist[anchor_id][0];
}

// NUEVO: Filtro de Kalman PREDICTIVO para posición 2D con velocidad
void kalmanFilterPositionWithVelocity(float measured_x, float measured_y) {
  unsigned long current_time = millis();
  float dt = (current_time - lastPositionUpdate) / 1000.0; // Delta tiempo en segundos
  lastPositionUpdate = current_time;
  
  if (dt > 0.5) dt = 0.025; // Limitar dt para evitar saltos por reinicios
  
  // ===== PREDICCIÓN =====
  // Predecir posición basada en velocidad
  float pred_x = kalman_x + kalman_vx * dt;
  float pred_y = kalman_y + kalman_vy * dt;
  
  // Predecir covarianza
  kalman_p_x = kalman_p_x + kalman_p_vx * dt * dt + kalman_q;
  kalman_p_y = kalman_p_y + kalman_p_vy * dt * dt + kalman_q;
  kalman_p_vx = kalman_p_vx + kalman_q_vel;
  kalman_p_vy = kalman_p_vy + kalman_q_vel;
  
  // ===== CORRECCIÓN =====
  // Ganancia de Kalman para posición
  float k_x = kalman_p_x / (kalman_p_x + kalman_r);
  float k_y = kalman_p_y / (kalman_p_y + kalman_r);
  
  // Actualizar posición
  kalman_x = pred_x + k_x * (measured_x - pred_x);
  kalman_y = pred_y + k_y * (measured_y - pred_y);
  
  // Estimar velocidad basada en cambio de posición
  if (dt > 0.001) { // Evitar división por cero
    float new_vx = (kalman_x - (pred_x - kalman_vx * dt)) / dt;
    float new_vy = (kalman_y - (pred_y - kalman_vy * dt)) / dt;
    
    // Filtrar velocidad con límites físicos
    new_vx = constrain(new_vx, -MAX_PLAYER_SPEED, MAX_PLAYER_SPEED);
    new_vy = constrain(new_vy, -MAX_PLAYER_SPEED, MAX_PLAYER_SPEED);
    
    kalman_vx = kalman_vx * 0.7 + new_vx * 0.3; // Suavizado
    kalman_vy = kalman_vy * 0.7 + new_vy * 0.3;
  }
  
  // Actualizar covarianza
  kalman_p_x = (1 - k_x) * kalman_p_x;
  kalman_p_y = (1 - k_y) * kalman_p_y;
  
  // Limitar posición a los límites de la cancha
  kalman_x = constrain(kalman_x, 0.0, FUTSAL_COURT_LENGTH);
  kalman_y = constrain(kalman_y, 0.0, FUTSAL_COURT_WIDTH);
  
  // Actualizar variables globales
  tagPositionX = kalman_x;
  tagPositionY = kalman_y;
  tagVelocityX = kalman_vx;
  tagVelocityY = kalman_vy;
}

// TFG v2.1-FINAL: Predicción de posición futura (sin variables globales)
void predictFuturePosition(float prediction_time_ms) {
  float dt = prediction_time_ms / 1000.0;
  float pred_x = tagPositionX + tagVelocityX * dt;
  float pred_y = tagPositionY + tagVelocityY * dt;
  
  // Limitar predicción a los límites de la cancha
  pred_x = constrain(pred_x, 0.0, FUTSAL_COURT_LENGTH);
  pred_y = constrain(pred_y, 0.0, FUTSAL_COURT_WIDTH);
  
  // Solo para logging/debugging si es necesario
  // Las predicciones se usan internamente, no se almacenan globalmente
}

// TFG v2.1-PRODUCTION: Función para marcar reset pendiente (limpia estado)
void requestDW3000Reset() {
  if (resetState == RESET_IDLE) {
    resetState = RESET_REQUESTED;
    // Limpiar estado del slot actual para evitar usar transceiver corrupto
    waitingForResponse = false;
    curr_stage = 0;
  }
}

// TFG v2.1-FINAL: State machine no bloqueante para reset DW3000
void executePendingReset() {
  static uint8_t softResets = 0;
  
  switch (resetState) {
    case RESET_IDLE:
      return; // Nada que hacer
      
    case RESET_REQUESTED:
      // Iniciar reset (sin delay bloqueante)
      if (++softResets > 10) {
        Serial.println(F("[INFO] 10+ soft resets → Ejecutando HARD RESET"));
        DW3000.hardReset();
        softResets = 0;
        resetStartTime = millis();
        resetState = RESET_IN_PROGRESS;
      } else {
        DW3000.softReset();
        resetStartTime = millis();
        resetState = RESET_IN_PROGRESS;
      }
      break;
      
    case RESET_IN_PROGRESS:
      // Esperar tiempo necesario (no bloqueante)
      if (millis() - resetStartTime >= 200) { // 200ms suficiente para ambos resets
        // TFG v2.1-FINAL: Verificar retorno de DW3000.init() también en reset state machine
        if (!DW3000.init()) {
          Serial.println(F("[CRITICAL] DW3000.init() falló en reset - Reiniciando ESP32..."));
          delay(1000);
          ESP.restart();
        }
        DW3000.configureAsTX();
        DW3000.clearSystemStatus();
        esp_task_wdt_reset(); // Reset watchdog tras delay prolongado
        Serial.println(F("[INFO] DW3000 reinicializado (state machine)"));
        resetState = RESET_IDLE;
      }
      break;
  }
}

// TFG v2.1-FINAL: Procesa publicaciones MQTT pendientes (sin bloqueos)
void processPendingMqttPublish() {
  if (!mqttPublishPending || pendingMqttData[0] == '\0') return;
  
  if (client.connected()) {
    bool publishSuccess = false;
    
    // TFG v2.1-PRODUCTION: Máximo 2 reintentos para evitar saturar cola
    for (int i = 0; i < 2; i++) {
      publishSuccess = client.publish(log_topic, pendingMqttData);
      if (publishSuccess) break;
      yield(); // No delay bloqueante, solo yield()
    }
    
    if (!publishSuccess) {
      performanceMetrics.mqttPublishFailures++;
    } else {
      performanceMetrics.mqttPublishTime = millis();
      updateLatencyMetrics();
    }
  } else {
    performanceMetrics.mqttPublishFailures++;
  }
  
  mqttPublishPending = false;
  pendingMqttData[0] = '\0';
}

// Configura la conexión WiFi
void setupWiFi() {
  if (USE_AP_MODE) {
      DEBUG_PRINT("Configuring WiFi mode AP...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  esp_task_wdt_reset(); // TFG v2.1-FINAL: Reset WDT también en modo AP
  Serial.print("AP created. IP: ");
  Serial.println(WiFi.softAPIP());
  } else {
    DEBUG_PRINT("Configuring WiFi mode STA...");
    WiFi.mode(WIFI_STA);
    DEBUG_PRINTLN(" Done.");
    DEBUG_PRINT("Beginning WiFi connection to SSID: ");
    DEBUG_PRINTLN(STA_SSID);
    WiFi.begin(STA_SSID, STA_PASS);

    DEBUG_PRINT("Attempting WiFi connection (15s timeout)...");
    unsigned long startAttemptTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < 15000) { // 15-second timeout
      DEBUG_PRINT("."); // Print dots while waiting
      esp_task_wdt_reset(); // TFG v2.1-PRODUCTION: Evitar reset WDT durante conexión
      delay(500);
    }
    
    /* NUEVO – por si falla y sales sin conectar */
    esp_task_wdt_reset();
    DEBUG_PRINTLN(); // Newline after dots

    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("WiFi OK. IP: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.print("WiFi FAILED! Status: ");
      Serial.println(WiFi.status()); // Print the specific failure status code
    }
  }
}

// MEJORA TFG: Capacidad JSON robusta para 5 anclas + velocidad + predicción
#define JSON_CAPACITY 4000 // TFG v2.1-FINAL: Aumentado para evitar "capacity exceeded" (era 3000)
static StaticJsonDocument<JSON_CAPACITY> jsonDoc;

// Genera los datos en formato JSON usando ArduinoJson con gestión de memoria optimizada
String getDataJson() {
  // TFG v2.1-FINAL: Verificación de memoria con rate limiting
  uint32_t freeHeap = ESP.getFreeHeap();
  if (freeHeap < 25000) {
    static uint8_t heapWarningCount = 0;
    if (++heapWarningCount >= 10) { // Mostrar warning cada 10 veces
      Serial.print(F("[WARNING] Memoria baja: "));
      Serial.print(freeHeap);
      Serial.println(F(" bytes libres"));
      heapWarningCount = 0;
    }
  }
  
  jsonDoc.clear(); // Limpiar documento para reutilización

  // Añadir nivel de batería (placeholder)
  jsonDoc["battery"] = 100.0;

  // Añadir datos de anclajes
  JsonArray anchorsArray = jsonDoc.createNestedArray("anchors");
  for (int i = 0; i < NUM_ANCHORS; i++) {
    JsonObject anchorObject = anchorsArray.createNestedObject();
    anchorObject["id"] = ID_PONG[i];
    // Asegurarse de enviar valores válidos (evitar NaN o Inf)
    anchorObject["dist"] = isnan(anchor_distance[i]) || isinf(anchor_distance[i]) ? 0.0 : anchor_distance[i]; // Distancia en cm
    anchorObject["rssi"] = isnan(pot_sig[i]) || isinf(pot_sig[i]) ? -100.0 : pot_sig[i];       // Potencia de señal
  }

  // Añadir posición del tag con datos extendidos para fútbol sala
  JsonObject positionObject = jsonDoc.createNestedObject("position");
  positionObject["x"] = isnan(tagPositionX) || isinf(tagPositionX) ? 0.0 : tagPositionX;
  positionObject["y"] = isnan(tagPositionY) || isinf(tagPositionY) ? 0.0 : tagPositionY;
  
  // NUEVO: Añadir velocidad
  JsonObject velocityObject = jsonDoc.createNestedObject("velocity");
  velocityObject["x"] = isnan(tagVelocityX) || isinf(tagVelocityX) ? 0.0 : tagVelocityX;
  velocityObject["y"] = isnan(tagVelocityY) || isinf(tagVelocityY) ? 0.0 : tagVelocityY;
  velocityObject["speed"] = sqrt(tagVelocityX*tagVelocityX + tagVelocityY*tagVelocityY);
  
  // TFG v2.1-PRODUCTION: Predicción optimizada para 25ms (reducido de 50ms)
  JsonObject predictionObject = jsonDoc.createNestedObject("prediction");
  float pred_x = tagPositionX + tagVelocityX * 0.035; // Predicción 35ms (optimizado)
  predictionObject["x"] = isnan(pred_x) || isinf(pred_x) ? 0.0 : pred_x;
  float pred_y = tagPositionY + tagVelocityY * 0.035; // Predicción 35ms (optimizado)
  predictionObject["y"] = isnan(pred_y) || isinf(pred_y) ? 0.0 : pred_y;
  
  // NUEVO: Estadísticas de calidad
  JsonObject qualityObject = jsonDoc.createNestedObject("quality");
  int responding_anchors = 0;
  for (int i = 0; i < NUM_ANCHORS; i++) {
    if (anchor_responded[i]) responding_anchors++;
  }
  qualityObject["responding_anchors"] = responding_anchors;
  qualityObject["update_rate_hz"] = 1000.0 / updateInterval;
  
  // MEJORA TFG: Añadir información de firmware para debugging
  JsonObject systemObject = jsonDoc.createNestedObject("system");
  systemObject["firmware"] = FW_VERSION;
  systemObject["free_heap"] = ESP.getFreeHeap();
  systemObject["uptime_ms"] = millis();

  // Serializar JSON a String
  String output;
  serializeJson(jsonDoc, output);
  return output;
}

#if ENABLE_WEB_INTERFACE
// TFG v2.1-PRODUCTION: Genera HTML dinámico con valores de C++
String generateIndexHTML() {
  String html = INDEX_HTML;
  // Reemplazar placeholder con valor real de PIXELS_PER_M
  html.replace("%%PIXELS_PER_M%%", String(PIXELS_PER_M, 1));
  return html;
}

// Configura el servidor web con soporte de compresión
void setupWebServer() {
  server.on("/", HTTP_GET, []() {
    String html = generateIndexHTML();
    server.sendHeader("Cache-Control", "max-age=86400"); // Cache 24h
    server.send(200, "text/html", html);
  });
  
  server.on("/data", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-cache");
    server.send(200, "application/json", getDataJson());
  });
  
  server.begin();
      DEBUG_PRINTLN(F("Servidor HTTP iniciado en puerto 80"));
}
#else
void setupWebServer() {
      DEBUG_PRINTLN(F("Interfaz web deshabilitada para ahorrar RAM"));
}
#endif



// MEJORADO: Comprueba zonas específicas de fútbol sala con análisis avanzado
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
        
        DEBUG_PRINT("Tag entró en zona: ");
        DEBUG_PRINT(zones[i].name);
        DEBUG_PRINT(" - Velocidad: ");
        DEBUG_PRINT(sqrt(tagVelocityX*tagVelocityX + tagVelocityY*tagVelocityY));
        DEBUG_PRINTLN(" m/s");
        
        // MQTT: Publicar entrada a zona específica para fútbol sala
        if (client.connected()) {
          StaticJsonDocument<200> zoneDoc;
          zoneDoc["tag_id"] = TAG_ID;
          zoneDoc["zone_name"] = zones[i].name;
          zoneDoc["action"] = "enter";
          zoneDoc["position"]["x"] = tagPositionX;
          zoneDoc["position"]["y"] = tagPositionY;
          zoneDoc["velocity"]["x"] = tagVelocityX;
          zoneDoc["velocity"]["y"] = tagVelocityY;
          zoneDoc["timestamp"] = millis();
          
          char zoneBuffer[250];
          serializeJson(zoneDoc, zoneBuffer);
          client.publish("uwb/futsal/zones", zoneBuffer);
        }
      }
      
      if (millis() - zones[i].entryTime >= zones[i].minStayTime && !zones[i].stayTimeReached) {
        zones[i].stayTimeReached = true;
        
        DEBUG_PRINT("Permanencia confirmada en zona: ");
        DEBUG_PRINTLN(zones[i].name);
        
        // MQTT: Publicar permanencia confirmada
        if (client.connected()) {
          StaticJsonDocument<150> stayDoc;
          stayDoc["tag_id"] = TAG_ID;
          stayDoc["zone_name"] = zones[i].name;
          stayDoc["action"] = "stay_confirmed";
          stayDoc["duration_ms"] = millis() - zones[i].entryTime;
          
          char stayBuffer[200];
          serializeJson(stayDoc, stayBuffer);
          client.publish("uwb/futsal/zones", stayBuffer);
        }
      }
    } else {
      if (zones[i].tagInside) {
        unsigned long stayDuration = millis() - zones[i].entryTime;
        zones[i].tagInside = false;
        zones[i].stayTimeReached = false;
        
        DEBUG_PRINT("Tag salió de zona: ");
        DEBUG_PRINT(zones[i].name);
        DEBUG_PRINT(" - Duración: ");
        DEBUG_PRINT(stayDuration);
        DEBUG_PRINTLN(" ms");
        
        // MQTT: Publicar salida de zona con estadísticas
        if (client.connected()) {
          StaticJsonDocument<200> exitDoc;
          exitDoc["tag_id"] = TAG_ID;
          exitDoc["zone_name"] = zones[i].name;
          exitDoc["action"] = "exit";
          exitDoc["duration_ms"] = stayDuration;
          exitDoc["exit_velocity"]["x"] = tagVelocityX;
          exitDoc["exit_velocity"]["y"] = tagVelocityY;
          
          char exitBuffer[250];
          serializeJson(exitDoc, exitBuffer);
          client.publish("uwb/futsal/zones", exitBuffer);
        }
      }
    }
  }
  
  // NUEVO: Detección de velocidades altas (sprints)
  float speed = sqrt(tagVelocityX*tagVelocityX + tagVelocityY*tagVelocityY);
  static bool inSprint = false;
  static unsigned long sprintStartTime = 0;
  
  if (speed > 5.0 && !inSprint) { // Sprint detectado
    inSprint = true;
    sprintStartTime = millis();
    
            DEBUG_PRINT("SPRINT detectado - Velocidad: ");
        DEBUG_PRINTLN(speed);
    
    if (client.connected()) {
      StaticJsonDocument<150> sprintDoc;
      sprintDoc["tag_id"] = TAG_ID;
      sprintDoc["action"] = "sprint_start";
      sprintDoc["speed"] = speed;
      sprintDoc["position"]["x"] = tagPositionX;
      sprintDoc["position"]["y"] = tagPositionY;
      
      char sprintBuffer[200];
      serializeJson(sprintDoc, sprintBuffer);
      client.publish("uwb/futsal/performance", sprintBuffer);
    }
  } else if (speed < 3.0 && inSprint) { // Fin del sprint
    inSprint = false;
    unsigned long sprintDuration = millis() - sprintStartTime;
    
          DEBUG_PRINT("SPRINT finalizado - Duración: ");
      DEBUG_PRINTLN(sprintDuration);
    
    if (client.connected()) {
      StaticJsonDocument<150> sprintDoc;
      sprintDoc["tag_id"] = TAG_ID;
      sprintDoc["action"] = "sprint_end";
      sprintDoc["duration_ms"] = sprintDuration;
      
      char sprintBuffer[200];
      serializeJson(sprintDoc, sprintBuffer);
      client.publish("uwb/futsal/performance", sprintBuffer);
    }
  }
}

// --- Funciones MQTT --- 

// MEJORA TFG: Callback para comandos OTA y configuración remota
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  DEBUG_PRINT("Comando MQTT recibido en topic: ");
  DEBUG_PRINT(topic);
  DEBUG_PRINT(" - Mensaje: ");
  DEBUG_PRINTLN(message);
  
  // Parsear comandos JSON
  StaticJsonDocument<300> cmdDoc;
  DeserializationError error = deserializeJson(cmdDoc, message);
  
  if (!error) {
    String command = cmdDoc["command"];
    
    if (command == "update_zones") {
      // Actualizar zonas de fútbol sala remotamente
      DEBUG_PRINTLN("[OTA] Actualizando configuración de zonas...");
      // Implementar actualización de zonas
    }
    else if (command == "adjust_kalman") {
      // Ajustar parámetros de Kalman remotamente
      if (cmdDoc["kalman_q"]) kalman_q = cmdDoc["kalman_q"];
      if (cmdDoc["kalman_r"]) kalman_r = cmdDoc["kalman_r"];
      DEBUG_PRINTLN("[OTA] Parámetros Kalman actualizados");
    }
    else if (command == "reset_metrics") {
      // Resetear métricas de rendimiento
      memset(&performanceMetrics, 0, sizeof(performanceMetrics));
      DEBUG_PRINTLN("[OTA] Métricas reseteadas");
    }
  }
}

void reconnectMQTT() {
  if (!client.connected()) {
    esp_task_wdt_reset(); // TFG v2.1-PRODUCTION: Reset WDT durante reconexión MQTT
    long now = millis();
    if (now - lastMqttReconnectAttempt > 5000) {
      lastMqttReconnectAttempt = now;
      DEBUG_PRINT("Attempting MQTT connection...");
      
      String clientId = "ESP32-Tag-";
      clientId += String(TAG_ID);
      clientId += "-";
      clientId += WiFi.macAddress();
      
      // MEJORA TFG: Last Will Testament para detectar desconexiones
      String willTopic = "uwb/futsal/status/lastwill";
      String willMessage = "{\"tag_id\":" + String(TAG_ID) + ",\"status\":\"offline\",\"timestamp\":" + String(millis()) + "}";
      
      // Intentar conectar con Last Will
      if (client.connect(clientId.c_str(), willTopic.c_str(), 1, true, willMessage.c_str())) {
                  DEBUG_PRINTLN("connected with Last Will");
        
        // MEJORA TFG: Suscribirse a topic de comandos OTA
        String commandTopic = "uwb/futsal/commands/" + String(TAG_ID);
        client.subscribe(commandTopic.c_str());
        
        // Enviar mensaje de conexión exitosa
        String onlineTopic = "uwb/futsal/status/online";
        String onlineMessage = "{\"tag_id\":" + String(TAG_ID) + ",\"status\":\"online\",\"timestamp\":" + String(millis()) + "}";
        client.publish(onlineTopic.c_str(), onlineMessage.c_str());
        
              } else {
          DEBUG_PRINT("failed, rc=");
          DEBUG_PRINT(client.state());
          DEBUG_PRINTLN(" try again in 5 seconds");
        }
    }
  }
}

void publishStatus() {
   if (client.connected()) {
     StaticJsonDocument<200> doc;
     doc["tag_id"] = TAG_ID;
     doc["last_anchor_id"] = last_anchor_id;
     doc["timestamp_ms"] = millis();

     char buffer[200];
     size_t n = serializeJson(doc, buffer);

     if (client.publish(status_topic, buffer, n)) { 
         // Serial.println("MQTT Status published");
     } else {
         Serial.println(F("Failed to publish MQTT status"));
     }
   }
}

// ===== FUNCIONES DE MÉTRICAS PARA TFG =====
void reportPerformanceMetrics() {
  unsigned long currentTime = millis();
  
  if (currentTime - performanceMetrics.lastMetricsReport > METRICS_REPORT_INTERVAL) {
    performanceMetrics.lastMetricsReport = currentTime;
    
    float triangulationSuccessRate = performanceMetrics.totalRangingCycles > 0 ? 
      (float)performanceMetrics.successfulTriangulations / performanceMetrics.totalRangingCycles * 100.0 : 0.0;
    
    float fullCoverageRate = performanceMetrics.totalRangingCycles > 0 ?
      (float)performanceMetrics.timestampsWithFullCoverage / performanceMetrics.totalRangingCycles * 100.0 : 0.0;
    
      // TFG v2.1-PRODUCTION: Métricas compactas para producción
  Serial.println(F("=== MÉTRICAS TFG ==="));
  Serial.print("Éxito trilateración: ");
  Serial.print(triangulationSuccessRate);
  Serial.print("% | Cobertura: ");
  Serial.print(fullCoverageRate);
  Serial.print("% | Latencia: ");
  Serial.print(performanceMetrics.averageLatency);
  Serial.print("ms | MQTT fallos: ");
  Serial.println(performanceMetrics.mqttPublishFailures);
  Serial.println(F("=================="));
    
    // MEJORA TFG: Publicar métricas vía MQTT para análisis posterior
    if (client.connected()) {
      StaticJsonDocument<400> metricsDoc;
      metricsDoc["tag_id"] = TAG_ID;
      metricsDoc["metrics"]["total_cycles"] = performanceMetrics.totalRangingCycles;
      metricsDoc["metrics"]["successful_triangulations"] = performanceMetrics.successfulTriangulations;
      metricsDoc["metrics"]["triangulation_success_rate"] = triangulationSuccessRate;
      metricsDoc["metrics"]["less_than_3_anchors"] = performanceMetrics.timestampsWithLessThan3Anchors;
      metricsDoc["metrics"]["full_coverage"] = performanceMetrics.timestampsWithFullCoverage;
      metricsDoc["metrics"]["full_coverage_rate"] = fullCoverageRate;
          metricsDoc["metrics"]["average_latency_ms"] = performanceMetrics.averageLatency;
    metricsDoc["metrics"]["average_update_rate_hz"] = performanceMetrics.averageUpdateRate; // TFG v2.1-FINAL
    metricsDoc["metrics"]["mqtt_failures"] = performanceMetrics.mqttPublishFailures; // MEJORA TFG
    metricsDoc["timestamp"] = millis();
      
      char metricsBuffer[450];
      serializeJson(metricsDoc, metricsBuffer);
      client.publish("uwb/futsal/metrics", metricsBuffer);
    }
  }
}

void updateLatencyMetrics() {
  // Calcular latencia extremo-a-extremo (ranging → MQTT publicado)
  if (performanceMetrics.rangingStartTime > 0 && performanceMetrics.mqttPublishTime > 0) {
    float currentLatency = performanceMetrics.mqttPublishTime - performanceMetrics.rangingStartTime;
    
    // Media móvil para latencia promedio
    if (performanceMetrics.averageLatency == 0.0) {
      performanceMetrics.averageLatency = currentLatency;
    } else {
      performanceMetrics.averageLatency = performanceMetrics.averageLatency * 0.9 + currentLatency * 0.1;
    }
  }
  
  // TFG v2.1-FINAL: Actualizar averageUpdateRate solo si NO estamos en low-power mode
  if (!lowPowerMode) {
    performanceMetrics.averageUpdateRate = 1000.0 / updateInterval;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println(F("\n=== SISTEMA GPS INDOOR PARA FÚTBOL SALA - TFG ==="));
  Serial.print("Firmware: ");
  Serial.println(FW_VERSION);
  Serial.print("Build: ");
  Serial.println(BUILD_DATE);
  Serial.print("Tag ID: ");
  Serial.println(TAG_ID);
  Serial.println(F("============================================\n"));
  
  setupWiFi();
  
  setupWebServer();
  
  // MEJORA TFG: Configurar watchdog para robustez del sistema
  esp_task_wdt_init(7, true); // TFG v2.1-FINAL: 7s para WiFi lag + lowPowerMode
  esp_task_wdt_add(NULL);     // Añadir tarea actual al watchdog
              DEBUG_PRINTLN("Watchdog configurado: 7s timeout");
  
  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(onMqttMessage); // MEJORA TFG: Configurar callback para comandos OTA
  snprintf(status_topic, sizeof(status_topic), "%s%d/status", "uwb/tag/", TAG_ID);
  DEBUG_PRINT("MQTT Status topic set to: ");
  DEBUG_PRINTLN(status_topic);

  DW3000.begin();
  DW3000.hardReset();
  delay(200);
  
  while (!DW3000.checkForIDLE()) {
    Serial.println(F("[ERROR] IDLE1 FAILED"));
    delay(100);
  }

  DW3000.softReset();
  delay(200);

  if (!DW3000.checkForIDLE()) {
    Serial.println(F("[ERROR] IDLE2 FAILED"));
    delay(100);
  }

  // TFG v2.1-FINAL: Verificar retorno de DW3000.init() para robustez crítica
  if (!DW3000.init()) {
    Serial.println(F("[CRITICAL] DW3000.init() falló - Reiniciando ESP32..."));
    delay(1000);
    ESP.restart();
  }
  DW3000.setupGPIO();
  Serial.println(F("[INFO] DW3000 inicializado correctamente."));

  DW3000.configureAsTX();
  DW3000.clearSystemStatus();
  
  lastActivityTime = millis();
  lastUpdate = millis();
}

void loop() {
#if ENABLE_WEB_INTERFACE
  server.handleClient(); // Handle web server requests
#endif
  
  // Handle MQTT Client
  if (!client.connected()) {
    reconnectMQTT(); // Try to reconnect if disconnected
  }
  client.loop(); // Allow MQTT client to process messages/maintain connection

  unsigned long currentMillis = millis();
  
  if (!lowPowerMode && (currentMillis - lastActivityTime >= SLEEP_TIMEOUT)) {
    DEBUG_PRINTLN(F("Entrando en modo de bajo consumo..."));
    lowPowerMode = true;
    updateInterval = 1000;
    performanceMetrics.averageUpdateRate = 0.0; // TFG v2.1-FINAL: Reiniciar métrica
  }
  
  if (currentMillis - lastUpdate >= updateInterval) {
    lastUpdate = currentMillis;
    lastActivityTime = currentMillis;
    
    unsigned long time_in_cycle = currentMillis % TDMA_CYCLE_MS;
    unsigned long assigned_slot_start = (TAG_ID - 1) * TDMA_SLOT_DURATION_MS;
    unsigned long assigned_slot_end = assigned_slot_start + TDMA_SLOT_DURATION_MS;

    bool is_my_slot = (time_in_cycle >= assigned_slot_start && time_in_cycle < assigned_slot_end);

    // TFG v2.1-FINAL: Detectar salida de low-power mode y restaurar configuración
    if (is_my_slot && lowPowerMode) {
      DEBUG_PRINTLN(F("Saliendo de modo de bajo consumo - restaurando configuración..."));
      lowPowerMode = false;
      updateInterval = 25; // Restaurar a frecuencia normal (40Hz)
      performanceMetrics.averageUpdateRate = 0.0; // Reiniciar métrica
      lastActivityTime = currentMillis;
    }

    if (is_my_slot && !lowPowerMode) { 
        lastActivityTime = currentMillis;

        // TFG v2.1-PRODUCTION: dataString eliminado (se usa snprintf directo)
        
        // MEJORA TFG: Iniciar medición de latencia para métricas
        performanceMetrics.rangingStartTime = millis();
        performanceMetrics.mqttPublishTime = 0; // Resetear tiempo de publicación MQTT
        performanceMetrics.totalRangingCycles++;

        // Reset anchor status for this cycle
        for(int k=0; k<NUM_ANCHORS; k++) {
          anchor_responded[k] = false;
          pot_sig[k] = -120.0f; // MEJORA TFG: Limpiar potencia previa para evitar confusión en WLS
        }

        for (int ii = 0; ii < NUM_ANCHORS; ii++) {
          // MEJORA TFG: Saltar anclas marcadas como "muertas"
          if (anchorDead[ii]) {
            consecutiveTimeouts[ii] = max(0, consecutiveTimeouts[ii] - 1); // TFG: Evitar negativo
            if (consecutiveTimeouts[ii] <= 0) {
              anchorDead[ii] = false; // Reactivar después de 5 ciclos
              consecutiveTimeouts[ii] = 0;
              // MEJORA TFG v2.1: Reinicializar Kalman al reactivar ancla
              last_measurement_time[ii] = 0; // Forzar re-init en próxima medición
              kalman_dist[ii][0] = 0;         // Reset estado
              kalman_dist[ii][1] = kalman_dist_r; // TFG v2.1-FINAL: Arranque suave (no salto)
              DEBUG_PRINT("Ancla ");
              DEBUG_PRINT(ID_PONG[ii]);
              DEBUG_PRINTLN(" REACTIVADA automáticamente (Kalman reiniciado)");
            }
            continue;
          }
          
          DW3000.setDestinationID(ID_PONG[ii]);
          fin_de_com = 0;
          
          while (fin_de_com == 0) {
            esp_task_wdt_reset(); // MEJORA TFG: Reset watchdog durante ranging intensivo
            
            // TFG v2.1-FINAL: Reset adicional cuando no esperamos respuesta
            if (!waitingForResponse) {
              esp_task_wdt_reset();
            }
            
            if (waitingForResponse && ((millis() - timeoutStart) >= RESPONSE_TIMEOUT)) {
              DEBUG_PRINT("Timeout REFORZADO para ancla ID: "); 
              DEBUG_PRINTLN(ID_PONG[ii]);

              // MEJORA TFG: Gestión inteligente de timeouts consecutivos
              consecutiveTimeouts[ii]++;
              if (consecutiveTimeouts[ii] >= 3) {
                anchorDead[ii] = true;
                consecutiveTimeouts[ii] = 5; // Desactivar por 5 ciclos TDMA
                DEBUG_PRINT("Ancla ");
                DEBUG_PRINT(ID_PONG[ii]);
                DEBUG_PRINTLN(" marcada como MUERTA por 5 ciclos");
              }

              requestDW3000Reset(); // TFG v2.1-FINAL: Reset asíncrono

              anchor_distance[ii] = 0;
              pot_sig[ii] = -120.0f;
              anchor_responded[ii] = false;
              
              curr_stage = 0; 
              ranging_time = 0;
              waitingForResponse = false; 
              fin_de_com = 1; 
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
                      DEBUG_PRINTLN(F("[WARNING] Error frame detected! Reverting to stage 0."));
                      curr_stage = 0;
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com), dejamos que intente de nuevo o timeoutee si el ancla sigue mal
                    } else if ((DW3000.getDestinationID() != ID_PONG[ii])) {
                      // Mensaje para otra ancla, reiniciar protocolo para evitar bucle infinito
                      curr_stage = 0; // TFG v2.1-PRODUCTION: Volver a stage 0
                      waitingForResponse = false;
                      break;
                    } else if (DW3000.ds_getStage() != 2) {
                      DEBUG_PRINTLN(F("[WARNING] Stage incorrecto del ancla. Enviando error frame."));
                      DW3000.ds_sendErrorFrame();
                      curr_stage = 0; // Reiniciar protocolo para esta ancla
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com), dejamos que intente de nuevo o timeoutee
                    } else {
                      curr_stage = 2;
                      waitingForResponse = false;
                    }
                  } else { // rx_status != 1 O el ID no es el correcto
                    DEBUG_PRINT("[ERROR] Receiver Error (case 1) o ID incorrecto. RX_STATUS: ");
                    DEBUG_PRINT(rx_status);
                    DEBUG_PRINT(", DEST_ID: ");
                    DEBUG_PRINTLN(DW3000.getDestinationID());
                    
                    requestDW3000Reset(); // TFG v2.1-FINAL: Reset asíncrono

                    anchor_distance[ii] = 0;
                    pot_sig[ii] = -120.0f;
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1;
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
                      DEBUG_PRINTLN(F("[WARNING] Error frame detected (case 3)! Reverting to stage 0."));
                      curr_stage = 0;
                      waitingForResponse = false;
                      // No rompemos el while (fin_de_com)
                    } else {
                      waitingForResponse = false;
                      clock_offset = DW3000.getRawClockOffset();
                      curr_stage = 4;
                    }
                  } else { // rx_status != 1
                                      DEBUG_PRINT("[ERROR] Receiver Error (case 3)! RX_STATUS: ");
                  DEBUG_PRINTLN(rx_status);

                    requestDW3000Reset(); // TFG v2.1-FINAL: Reset asíncrono

                    anchor_distance[ii] = 0;
                    pot_sig[ii] = -120.0f;
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1;
                  }
                }
                break;
                
              case 4:
                ranging_time = DW3000.ds_processRTInfo(t_roundA, t_replyA, DW3000.read(0x12, 0x04), DW3000.read(0x12, 0x08), clock_offset);
                distance = DW3000.convertToCM(ranging_time);
                
                // Leer la potencia de la señal recibida y almacenarla
                pot_sig[ii] = DW3000.getSignalStrength();

                anchor_responded[ii] = true;
                consecutiveTimeouts[ii] = 0; // MEJORA TFG: Resetear contador de timeouts en éxito
                last_anchor_id = String(ID_PONG[ii]); // MEJORA TFG: Actualizar último ancla exitosa 
                if (distance > 0) { 
                    anchor_distance[ii] = kalmanFilterDistance(distance, ii);
                } else {
                    anchor_distance[ii] = 0; 
                    // Si la distancia es inválida, también deberíamos considerar la señal como mala para WLS
                    // pot_sig[ii] = -120.0f; // Opcional: si distancia es 0, forzar mala señal para WLS
                }
 
                // TFG v2.1-FINAL: MQTT con formato optimizado y validación de overflow
                SAFE_MQTT_SNPRINTF(pendingMqttData, 
                        "%d,%lu,%d,%lu,%lu,%d,%d",
                        TAG_ID, millis(), ID_PONG[ii], 
                        (unsigned long)round(distance), (unsigned long)round(anchor_distance[ii]), 
                        (int)round(pot_sig[ii]), anchor_responded[ii] ? 1 : 0);
                mqttPublishPending = true;
                // ----------------------------------------------
 
                // Respond with a PONG
                curr_stage = 0;
                fin_de_com = 1;
                
                // REMOVED: delay(50); // This was slowing down the measurement cycle
                break;
                
              default:
                DEBUG_PRINT("[ERROR] Estado desconocido (");
                DEBUG_PRINT(curr_stage);
                DEBUG_PRINTLN("). Volviendo a estado 0.");
                curr_stage = 0;
                waitingForResponse = false; // MEJORA TFG: Limpiar flag de timeout
                break;
            }
          }
        }
        
        // Count responding anchors
        int responding_anchors = 0;
        for(int k=0; k<NUM_ANCHORS; k++) {
          if(anchor_responded[k]) responding_anchors++;
        }

        // MEJORA TFG: Actualizar métricas de cobertura
        if (responding_anchors < 3) {
          performanceMetrics.timestampsWithLessThan3Anchors++;
        } else {
          performanceMetrics.successfulTriangulations++;
        }
        
        if (responding_anchors == NUM_ANCHORS) {
          performanceMetrics.timestampsWithFullCoverage++;
        }

        // Only trilaterate if enough anchors responded
        if (responding_anchors >= 3) { 
          // Calcular posición del tag usando multilateración PONDERADA
          
          // POSICIONES OPTIMIZADAS PARA CANCHA DE FÚTBOL SALA (40x20m)
          float anchorsPos[NUM_ANCHORS][2] = {
            {0.0, 0.0},    // Ancla 10 - Esquina inferior izquierda
            {0.0, 20.0},   // Ancla 20 - Esquina superior izquierda  
            {40.0, 0.0},   // Ancla 30 - Esquina inferior derecha
            {40.0, 20.0},  // Ancla 40 - Esquina superior derecha
            {20.0, 10.0}   // Ancla 50 - Centro exacto de la cancha
          };
          
          // MEJORA TFG: Filtrar anclas válidas para WLS robusto
          float distances[NUM_ANCHORS];
          float quality[NUM_ANCHORS];
          int validAnchors = 0;
          
          for (int i = 0; i < NUM_ANCHORS; i++) {
            distances[i] = anchor_distance[i] / 100.0;
            
                         // MEJORA TFG: Peso explícito cero para anclas inválidas
             if (!anchor_responded[i] || distances[i] <= 0.0) {
               quality[i] = 0.0; // Peso cero explícito para no contaminar WLS
               // NOTA TFG: pot_sig[i] = -120.0f → quality = 0.1, pero con peso 0.0 explícito es más claro
             } else {
               quality[i] = max(0.01f, pot_sig[i] + 120.1f); // Peso basado en RSSI (rango 0.1 a ~60)
               validAnchors++;
             }
          }
          
          // MEJORA TFG: Verificar que tengamos suficientes anclas válidas después del filtro
          if (validAnchors < 3) {
                  DEBUG_PRINT("[WLS-ERROR] Solo ");
      DEBUG_PRINT(validAnchors);
      DEBUG_PRINTLN(" anclas válidas para trilateración");
            return; // Salir sin calcular posición
          }

          // MEJORA TFG v2.1: Pesos robustos solo entre anclas válidas
          float w_eq1 = (quality[0] > 0 && quality[1] > 0) ? (quality[0] + quality[1]) / 2.0f : 0.0f; 
          float w_eq2 = (quality[1] > 0 && quality[2] > 0) ? (quality[1] + quality[2]) / 2.0f : 0.0f; 
          float w_eq3 = (quality[2] > 0 && quality[3] > 0) ? (quality[2] + quality[3]) / 2.0f : 0.0f; 
          float w_eq4 = (quality[3] > 0 && quality[4] > 0) ? (quality[3] + quality[4]) / 2.0f : 0.0f; 
          float w_eq5 = (quality[4] > 0 && quality[0] > 0) ? (quality[4] + quality[0]) / 2.0f : 0.0f; 
          
          // TFG v2.1: Optimización de eficiencia - no calcular ecuaciones con peso cero
          float A1, B1, C1, A2, B2, C2, A3, B3, C3, A4, B4, C4, A5, B5, C5;
          
          if (w_eq1 == 0) { A1 = B1 = C1 = 0; } else {
            A1 = 2 * (anchorsPos[1][0] - anchorsPos[0][0]);
            B1 = 2 * (anchorsPos[1][1] - anchorsPos[0][1]);
            C1 = distances[0]*distances[0] - distances[1]*distances[1] - 
                 anchorsPos[0][0]*anchorsPos[0][0] + anchorsPos[1][0]*anchorsPos[1][0] - 
                 anchorsPos[0][1]*anchorsPos[0][1] + anchorsPos[1][1]*anchorsPos[1][1];
          }
          
          if (w_eq2 == 0) { A2 = B2 = C2 = 0; } else {
            A2 = 2 * (anchorsPos[2][0] - anchorsPos[1][0]);
            B2 = 2 * (anchorsPos[2][1] - anchorsPos[1][1]);
            C2 = distances[1]*distances[1] - distances[2]*distances[2] - 
                 anchorsPos[1][0]*anchorsPos[1][0] + anchorsPos[2][0]*anchorsPos[2][0] - 
                 anchorsPos[1][1]*anchorsPos[1][1] + anchorsPos[2][1]*anchorsPos[2][1];
          }
          
          if (w_eq3 == 0) { A3 = B3 = C3 = 0; } else {
            A3 = 2 * (anchorsPos[3][0] - anchorsPos[2][0]);
            B3 = 2 * (anchorsPos[3][1] - anchorsPos[2][1]);
            C3 = distances[2]*distances[2] - distances[3]*distances[3] - 
                 anchorsPos[2][0]*anchorsPos[2][0] + anchorsPos[3][0]*anchorsPos[3][0] - 
                 anchorsPos[2][1]*anchorsPos[2][1] + anchorsPos[3][1]*anchorsPos[3][1];
          }
          
          if (w_eq4 == 0) { A4 = B4 = C4 = 0; } else {
            A4 = 2 * (anchorsPos[4][0] - anchorsPos[3][0]);
            B4 = 2 * (anchorsPos[4][1] - anchorsPos[3][1]);
            C4 = distances[3]*distances[3] - distances[4]*distances[4] - 
                 anchorsPos[3][0]*anchorsPos[3][0] + anchorsPos[4][0]*anchorsPos[4][0] - 
                 anchorsPos[3][1]*anchorsPos[3][1] + anchorsPos[4][1]*anchorsPos[4][1];
          }
          
          if (w_eq5 == 0) { A5 = B5 = C5 = 0; } else {
            A5 = 2 * (anchorsPos[0][0] - anchorsPos[4][0]);
            B5 = 2 * (anchorsPos[0][1] - anchorsPos[4][1]);
            C5 = distances[4]*distances[4] - distances[0]*distances[0] - 
                 anchorsPos[4][0]*anchorsPos[4][0] + anchorsPos[0][0]*anchorsPos[0][0] - 
                 anchorsPos[4][1]*anchorsPos[4][1] + anchorsPos[0][1]*anchorsPos[0][1];
          }
          
          float ATA11 = w_eq1*A1*A1 + w_eq2*A2*A2 + w_eq3*A3*A3 + w_eq4*A4*A4 + w_eq5*A5*A5;
          float ATA12 = w_eq1*A1*B1 + w_eq2*A2*B2 + w_eq3*A3*B3 + w_eq4*A4*B4 + w_eq5*A5*B5;
          float ATA21 = ATA12; 
          float ATA22 = w_eq1*B1*B1 + w_eq2*B2*B2 + w_eq3*B3*B3 + w_eq4*B4*B4 + w_eq5*B5*B5;
          
          float ATb1 = w_eq1*A1*C1 + w_eq2*A2*C2 + w_eq3*A3*C3 + w_eq4*A4*C4 + w_eq5*A5*C5;
          float ATb2 = w_eq1*B1*C1 + w_eq2*B2*C2 + w_eq3*B3*C3 + w_eq4*B4*C4 + w_eq5*B5*C5;
          
          float detATA = ATA11 * ATA22 - ATA12 * ATA21;
          
          // MEJORA TFG v2.1: Verificar que el sistema no sea singular
          if (abs(detATA) > 0.001) {
            float invATA11 = ATA22 / detATA;
            float invATA12 = -ATA12 / detATA;
            float invATA21 = -ATA21 / detATA;
            float invATA22 = ATA11 / detATA;
            
            float x = invATA11 * ATb1 + invATA12 * ATb2;
            float y = invATA21 * ATb1 + invATA22 * ATb2;
            
            x = max(0.0f, min(FUTSAL_COURT_LENGTH, x));
            y = max(0.0f, min(FUTSAL_COURT_WIDTH, y));
            
            // ACTIVADO: Filtro de Kalman predictivo para fútbol sala
            kalmanFilterPositionWithVelocity(x, y);
            
            // Predecir posición futura para compensar latencia del sistema
            predictFuturePosition(35.0); // TFG v2.1-FINAL: Unificado a 35ms (coherente con JSON)
            
            checkZones();
          }
        }
        
        // TFG v2.1-FINAL: Logging de distancias controlado por DEBUG_MODE
        #if DEBUG_MODE
        for (int i = 0; i < NUM_ANCHORS; i++) {
                  DEBUG_PRINT("Anclaje ");
        DEBUG_PRINT(ID_PONG[i]);
        DEBUG_PRINT(" ");
        DW3000.printDouble(anchor_distance[i], 100, false);
        DEBUG_PRINT(" cm, Potencia = ");
        DEBUG_PRINT(pot_sig[i]);
        DEBUG_PRINTLN("dBm");
        }
        #endif
        
        // broadcastUDP();
        
        // Publish MQTT status periodically
        if (currentMillis - lastStatusUpdate >= statusUpdateInterval) {
            lastStatusUpdate = currentMillis;
            publishStatus();
        }

        fin_de_com = 0;
    }
  } 
  
  // TFG v2.1-FINAL: Procesar tareas pendientes fuera del slot TDMA
  executePendingReset();
  processPendingMqttPublish();
  
  // MEJORA TFG v2.1: Reset watchdog también fuera del slot para TAG_ID altos
  esp_task_wdt_reset();
  
  // MEJORA TFG: Reportar métricas de rendimiento periódicamente
  reportPerformanceMetrics();

} // Closing brace for loop()
