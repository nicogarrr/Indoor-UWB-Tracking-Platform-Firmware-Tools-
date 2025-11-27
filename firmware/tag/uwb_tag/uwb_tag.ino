#include <SPI.h>
#include "DW3000.h"
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#define MQTT_MAX_PACKET_SIZE 2048 
#include <PubSubClient.h>
#include <cmath>  // For fabs, sqrt, etc.
#include <ArduinoJson.h>
#include "esp_wifi.h"
#include "esp_bt.h"

// FreeRTOS Includes
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

// ===== TAG IDENTIFICATION =====
#define TAG_ID 1 

// ===== WiFi CONFIGURATION =====
#define USE_AP_MODE false
#define AP_SSID "UWB_TAG_AP"
#define AP_PASS "12345678"
#define STA_SSID "iPhone de Nico"
#define STA_PASS "12345678"

// Server configuration 
#define HTTP_PORT 80
AsyncWebServer server(HTTP_PORT);
AsyncWebSocket ws("/ws");

// MQTT Configuration
const char* mqtt_server = "172.20.10.5"; 
const int mqtt_port = 1883;
char status_topic[30];                      
WiFiClient espClient;
PubSubClient client(espClient);

// ===== TDMA Configuration (INDOOR) =====
const unsigned long TDMA_CYCLE_MS = 33;  // Target: ~30 Hz
const unsigned long TDMA_SLOT_DURATION_MS = 33;  // Full cycle for this tag

// ===== RANGING CONFIGURATION =====
#define NUM_ANCHORS 6 
int ID_PONG[NUM_ANCHORS] = {1, 2, 3, 4, 5, 6}; 

// Shared Data (Protected by Mutex)
SemaphoreHandle_t dataMutex;
float global_anchor_distance[NUM_ANCHORS] = {0};
float global_pot_sig[NUM_ANCHORS] = {0};
float global_tagPositionX = 0.0;
float global_tagPositionY = 0.0;
float global_tagPositionZ = 0.0;

// Queue for Inter-Core Communication
struct TagDataPacket {
    float x;
    float y;
    float z;
    float anchor_dist[NUM_ANCHORS];
    float anchor_rssi[NUM_ANCHORS];
    bool anchor_resp[NUM_ANCHORS]; // To know which ones are valid
    int last_anchor_id; // For legacy support if needed
    unsigned long timestamp;
};
QueueHandle_t uwbQueue;

// ===== DYNAMIC ANCHOR SKIPPING (Core 1 Local) =====
bool anchor_is_active[NUM_ANCHORS] = {true, true, true, true, true, true};
int anchor_fail_count[NUM_ANCHORS] = {0};
unsigned long anchor_inactive_ts[NUM_ANCHORS] = {0};
const int MAX_FAILURES = 2;
const unsigned long RETRY_INTERVAL = 2000; // 2 seconds

// Variables for Kalman Filter (Core 1 Local)
float kalman_dist[NUM_ANCHORS][2] = { {0} };
float kalman_dist_q = 0.005; 
float kalman_dist_r = 0.08; 

float kalman_x = 0.0;
float kalman_y = 0.0;
float kalman_z = 0.0;
float kalman_p_x = 1.0;
float kalman_p_y = 1.0;
float kalman_p_z = 1.0;
float kalman_r = 0.05; 

// Variables for WLSQ (Core 1 Local)
unsigned long last_wlsq_time = 0;
float last_valid_position_3d[3] = {0.0, 0.0, 0.0}; 

// ===== GLOBAL ANCHOR POSITIONS (anchors 1-6) =====
const float anchorsPos[NUM_ANCHORS][3] = {
  {0.0,  0.0,  1.8},   // Anchor 1
  {0.0,  6.40, 0.8},   // Anchor 2
  {4,  6.40, 1.8},   // Anchor 3
  {10.6, 6.40, 0.8},   // Anchor 4
  {10.6, 0.0,  1.8},   // Anchor 5
  {5.5,  0.0,  0.8}    // Anchor 6
};

// HTML Content
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UWB Tag Monitor</title>
  <style>
    body { font-family: Arial; margin: 0; padding: 0; background: #f0f0f0; }
    .container { max-width: 800px; margin: 0 auto; padding: 20px; }
    h1 { color: #333; }
    .card { background: white; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .anchor { display: flex; justify-content: space-between; margin-bottom: 10px; }
    button { background: #4CAF50; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
    .status { color: #666; font-style: italic; }
    #visualization { height: 400px; width: 100%; max-width: 600px; position: relative; border: 1px solid #ccc; background: #fafafa; margin: 0 auto; }
    .anchor-point { position: absolute; width: 20px; height: 20px; border-radius: 50%; background: blue; color: white; display: flex; justify-content: center; align-items: center; transform: translate(-50%, -50%); }
    .distance-circle { position: absolute; border-radius: 50%; border: 1px dashed rgba(0,0,0,0.3); transform: translate(-50%, -50%); }
    .tag-point { 
      position: absolute; width: 14px; height: 14px; border-radius: 50%; background: red; 
      transform: translate(-50%, -50%); box-shadow: 0 0 15px rgba(255,0,0,0.7); 
      transition: all 0.1s linear; animation: pulse 1.5s infinite;
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
    <h1>UWB Tag Monitor</h1>
    <div class="card">
      <h2>Anchors</h2>
      <div id="anchors-container"></div>
    </div>
    <div class="card">
      <h2>Visualization</h2>
      <div id="visualization"></div>
      <div style="margin-top: 10px;">
        <p>Estimated position: <span id="tag-position">Calculating...</span></p>
      </div>
    </div>
    <button onclick="requestUpdate()">Update data</button>
  </div>
  <script>
    let lastUpdate = Date.now();
    let anchors = [];
    let tagPosition = { x: 150, y: 150 };
    let tagTarget   = { x: 150, y: 150 };
    let visualizationInitialized = false;
    let vizElements = { container: null, border: null, anchorPoints: {}, distanceCircles: {}, tagPoint: null };
    let anchorListItems = {};

    const socket = new WebSocket(`ws://${window.location.host}/ws`);
    socket.addEventListener('message', (evt) => {
      try {
        const data = JSON.parse(evt.data);
        window.currentTagPositionFromESP = data.position;
        window.currentAnchorsData = data.anchors;
        updateUI(data);
      } catch (e) { console.error('WS parse error', e); }
    });

    function animateTag() {
      const dx = tagTarget.x - tagPosition.x;
      const dy = tagTarget.y - tagPosition.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const baseLerp = 0.12;
      const adaptiveLerp = Math.min(0.25, baseLerp + distance * 0.002);
      tagPosition.x += dx * adaptiveLerp;
      tagPosition.y += dy * adaptiveLerp;
      if (vizElements.tagPoint) {
        vizElements.tagPoint.style.transform = `translate(${tagPosition.x - 7}px, ${tagPosition.y - 7}px)`;
      }
      requestAnimationFrame(animateTag);
    }
    requestAnimationFrame(animateTag);

    function fetchData() {
      fetch('/data').then(response => response.json()).then(data => {
          window.currentTagPositionFromESP = data.position;
          window.currentAnchorsData = data.anchors;
          updateUI(data);
          lastUpdate = Date.now();
      });
    }
    
    function updateUI(data) {
      anchors = data.anchors;
      const anchorsContainer = document.getElementById('anchors-container');
      anchors.forEach((anchor, i) => {
        let anchorDiv = anchorListItems[anchor.id];
        if (!anchorDiv) {
          anchorDiv = document.createElement('div');
          anchorDiv.className = 'anchor';
          anchorDiv.id = `anchor-list-item-${anchor.id}`;
          anchorDiv.innerHTML = `<div><strong>Anchor ${anchor.id}</strong><p>Distance: <span class="anchor-dist">${(anchor.dist / 100).toFixed(2)}</span> m</p></div><div><p>Signal: <span class="anchor-rssi">${anchor.rssi.toFixed(1)}</span> dBm</p></div>`;
          anchorsContainer.appendChild(anchorDiv);
          anchorListItems[anchor.id] = anchorDiv;
        } else {
          anchorDiv.querySelector('.anchor-dist').textContent = (anchor.dist / 100).toFixed(2);
          anchorDiv.querySelector('.anchor-rssi').textContent = anchor.rssi.toFixed(1);
        }
      });
      calculateTagPosition();
      renderVisualization();
    }

    function calculateTagPosition() {
        const minX = -0.5, maxX = 11.1, minY = -0.5, maxY = 7.85;
        const scale = 40, margin = 15;
        const vizHeight = (maxY - minY) * scale + 2 * margin;

        if (!window.currentTagPositionFromESP) return;
        let esp_x = window.currentTagPositionFromESP.x;
        let esp_y = window.currentTagPositionFromESP.y;

        try {
          const boundedX = Math.max(minX, Math.min(maxX, esp_x));
          const boundedY = Math.max(minY, Math.min(maxY, esp_y));
          const pixelX = margin + (boundedX - minX) * scale;
          const pixelY = vizHeight - margin - (boundedY - minY) * scale;
          tagTarget.x = pixelX;
          tagTarget.y = pixelY;
          document.getElementById('tag-position').textContent = `X: ${boundedX.toFixed(2)}m, Y: ${boundedY.toFixed(2)}m (ESP32)`;
        } catch (e) {}
    }
    
    function renderVisualization() {
      const viz = document.getElementById('visualization');
      if (!viz) return; 
      if (!visualizationInitialized) {
        vizElements.container = viz;
        viz.innerHTML = ''; 
        const minX = -0.5, maxX = 11.1, minY = -0.5, maxY = 7.85;
        const scale = 40, margin = 15;
        const vizWidth = (maxX - minX) * scale + 2 * margin;
        const vizHeight = (maxY - minY) * scale + 2 * margin;
        viz.style.width = vizWidth + 'px';
        viz.style.height = vizHeight + 'px';
        
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", vizWidth);
        svg.setAttribute("height", vizHeight);
        svg.style.position = 'absolute'; svg.style.left = '0'; svg.style.top  = '0';

        const hexVertices = [{x:0,y:0}, {x:0,y:6.40}, {x:10.6,y:6.40}, {x:10.6,y:0}];
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

        const anchorsPosMetros = [
          { id: 1, x: 0.0,  y: 0.0  }, { id: 2, x: 0.0,  y: 6.40 },
          { id: 3, x: 4,  y: 6.40 }, { id: 4, x: 10.6, y: 6.40 },
          { id: 5, x: 10.6, y: 0.0  }, { id: 6, x: 5.5,  y: 0.0  }
        ];

        anchorsPosMetros.forEach(anchorCfg => {
            const anchorPixelX = margin + (anchorCfg.x - minX) * scale;
            const anchorPixelY = vizHeight - margin - (anchorCfg.y - minY) * scale;
            const dot = document.createElement('div');
            dot.className = 'anchor-point';
            dot.textContent = anchorCfg.id;
            dot.style.left = anchorPixelX + 'px';
            dot.style.top = anchorPixelY + 'px';
            viz.appendChild(dot);
            vizElements.anchorPoints[anchorCfg.id] = dot; 

            const circle = document.createElement('div');
            circle.className = 'distance-circle';
            circle.style.left = anchorPixelX + 'px';
            circle.style.top = anchorPixelY + 'px';
            viz.appendChild(circle);
            vizElements.distanceCircles[anchorCfg.id] = circle; 
        });

        const tagPoint = document.createElement('div');
        tagPoint.className = 'tag-point';
        tagPoint.style.left = '0px'; tagPoint.style.top = '0px';
        viz.appendChild(tagPoint);
        vizElements.tagPoint = tagPoint; 
        visualizationInitialized = true;
      } else {
        const scale = 40; 
        const currentAnchorsToRender = window.currentAnchorsData || anchors;
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData) => {
                const circle = vizElements.distanceCircles[anchorData.id];
                if (circle) {
                    const radius = (anchorData.dist / 100) * scale;
                    circle.style.width = radius * 2 + 'px';
                    circle.style.height = radius * 2 + 'px';
                }
            });
        }
      }
    }
    function requestUpdate() { fetchData(); }
    setInterval(() => { if (socket.readyState !== WebSocket.OPEN) fetchData(); }, 1000);
  </script>
</body>
</html>
)rawliteral";

// ===== HELPER FUNCTIONS =====

bool invertMatrix4x4(float A[4][4], float A_inv[4][4]) {
  for (int i = 0; i < 4; i++) {
    for (int j = 0; j < 4; j++) {
      A_inv[i][j] = (i == j) ? 1.0f : 0.0f;
    }
  }
  for (int i = 0; i < 4; i++) {
    float pivot = A[i][i];
    if (fabs(pivot) < 1e-6) return false;
    for (int j = 0; j < 4; j++) {
      A[i][j] /= pivot;
      A_inv[i][j] /= pivot;
    }
    for (int k = 0; k < 4; k++) {
      if (k != i) {
        float factor = A[k][i];
        for (int j = 0; j < 4; j++) {
          A[k][j] -= factor * A[i][j];
          A_inv[k][j] -= factor * A_inv[i][j];
        }
      }
    }
  }
  return true;
}

bool calculateWLSQPosition(int* available_anchors, int count, float* x, float* y, float* z, float* local_anchor_dist, float* local_pot_sig) {
  if (count < 4) return false; 
  float H_T_W_H[4][4] = {0};
  float H_T_W_Y[4] = {0};

  for (int i = 0; i < count; i++) {
    int anchor_idx = available_anchors[i];
    float ax = anchorsPos[anchor_idx][0];
    float ay = anchorsPos[anchor_idx][1];
    float az = anchorsPos[anchor_idx][2];
    float d = local_anchor_dist[anchor_idx];
    float rssi = local_pot_sig[anchor_idx];

    float weight = pow(10.0f, (rssi + 90.0f) / 20.0f); 
    float dist_weight = 1.0f / (d * d + 0.1f); 
    weight *= dist_weight;
    if (weight < 0.001f) weight = 0.001f;

    float h_row[4] = { -2.0f * ax, -2.0f * ay, -2.0f * az, 1.0f };
    float k_i = ax*ax + ay*ay + az*az;
    float y_val = d*d - k_i;

    for (int r = 0; r < 4; r++) {
      for (int c = 0; c < 4; c++) {
        H_T_W_H[r][c] += h_row[r] * weight * h_row[c];
      }
    }
    for (int r = 0; r < 4; r++) {
      H_T_W_Y[r] += h_row[r] * weight * y_val;
    }
  }

  float H_T_W_H_inv[4][4];
  if (!invertMatrix4x4(H_T_W_H, H_T_W_H_inv)) return false;

  float theta[4] = {0};
  for (int r = 0; r < 4; r++) {
    for (int c = 0; c < 4; c++) {
      theta[r] += H_T_W_H_inv[r][c] * H_T_W_Y[c];
    }
  }
  *x = theta[0]; *y = theta[1]; *z = theta[2];
  return true;
}

float kalmanFilterDistance(float measurement, int anchor_id) {
  kalman_dist[anchor_id][1] = kalman_dist[anchor_id][1] + kalman_dist_q;
  float k = kalman_dist[anchor_id][1] / (kalman_dist[anchor_id][1] + kalman_dist_r);
  kalman_dist[anchor_id][0] = kalman_dist[anchor_id][0] + k * (measurement - kalman_dist[anchor_id][0]);
  kalman_dist[anchor_id][1] = (1 - k) * kalman_dist[anchor_id][1];
  return kalman_dist[anchor_id][0];
}

void kalmanFilterPosition3D(float measured_x, float measured_y, float measured_z) {
  float dist_moved = sqrt(pow(measured_x - kalman_x, 2) + pow(measured_y - kalman_y, 2) + pow(measured_z - kalman_z, 2));
  float adaptive_q = 0.01;
  if (dist_moved > 0.5) adaptive_q = 0.1;
  else if (dist_moved > 0.2) adaptive_q = 0.05;
  else adaptive_q = 0.005;
  
  kalman_p_x += adaptive_q; kalman_p_y += adaptive_q; kalman_p_z += adaptive_q;
  float k_x = kalman_p_x / (kalman_p_x + kalman_r);
  float k_y = kalman_p_y / (kalman_p_y + kalman_r);
  float k_z = kalman_p_z / (kalman_p_z + kalman_r);
  
  kalman_x += k_x * (measured_x - kalman_x);
  kalman_y += k_y * (measured_y - kalman_y);
  kalman_z += k_z * (measured_z - kalman_z);
  
  kalman_p_x *= (1 - k_x); kalman_p_y *= (1 - k_y); kalman_p_z *= (1 - k_z);
}

// Generate data in JSON format (Thread-Safe Reading)
String getDataJson() {
  StaticJsonDocument<1024> doc;
  
  // Lock Mutex to read globals safely
  if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
      JsonArray anchorsArray = doc.createNestedArray("anchors");
      for (int i = 0; i < NUM_ANCHORS; i++) {
        JsonObject anchorObject = anchorsArray.createNestedObject();
        anchorObject["id"] = ID_PONG[i];
        anchorObject["dist"] = isnan(global_anchor_distance[i]) || isinf(global_anchor_distance[i]) ? 0.0 : (global_anchor_distance[i] * 100);
        anchorObject["rssi"] = isnan(global_pot_sig[i]) || isinf(global_pot_sig[i]) ? -100.0 : global_pot_sig[i];
      }
      JsonObject positionObject = doc.createNestedObject("position");
      positionObject["x"] = isnan(global_tagPositionX) || isinf(global_tagPositionX) ? 0.0 : global_tagPositionX;
      positionObject["y"] = isnan(global_tagPositionY) || isinf(global_tagPositionY) ? 0.0 : global_tagPositionY;
      positionObject["z"] = isnan(global_tagPositionZ) || isinf(global_tagPositionZ) ? 0.0 : global_tagPositionZ;
      xSemaphoreGive(dataMutex);
  } else {
      // Failed to take mutex, return empty or old data
      return "{}";
  }

  String output;
  serializeJson(doc, output);
  return output;
}

// ===== TASKS =====

// CORE 1: UWB Physics Task
void TaskUWB(void *pvParameters) {
    Serial.println("[Core 1] UWB Task Started");

    // Local variables for this task
    float local_anchor_distance[NUM_ANCHORS] = {0};
    float local_pot_sig[NUM_ANCHORS] = {0};
    bool local_anchor_responded[NUM_ANCHORS] = {false};
    
    // Ranging state variables
    int curr_stage = 0;
    int t_roundA = 0, t_replyA = 0;
    long long rx = 0, tx = 0;
    int clock_offset = 0;
    int ranging_time = 0;
    bool waitingForResponse = false;
    unsigned long timeoutStart = 0;
    const unsigned long RESPONSE_TIMEOUT = 15;
    int rx_status;
    int fin_de_com = 0;

    unsigned long lastUpdate = millis();
    unsigned long lastActivityTime = millis();
    bool lowPowerMode = false;
    unsigned long updateInterval = 12;

    for(;;) {
        unsigned long currentMillis = millis();

        // Low Power Logic
        if (!lowPowerMode && (currentMillis - lastActivityTime >= 300000)) {
            lowPowerMode = true;
            updateInterval = 1000;
        }

        if (currentMillis - lastUpdate >= updateInterval) {
            lastUpdate = currentMillis;
            
            unsigned long time_in_cycle = currentMillis % TDMA_CYCLE_MS;
            unsigned long assigned_slot_start = (TAG_ID - 1) * TDMA_SLOT_DURATION_MS;
            unsigned long assigned_slot_end = assigned_slot_start + TDMA_SLOT_DURATION_MS;
            bool is_my_slot = (time_in_cycle >= assigned_slot_start && time_in_cycle < assigned_slot_end);

            if (is_my_slot && !lowPowerMode) {
                lastActivityTime = currentMillis;
                
                // Reset local status
                for(int k=0; k<NUM_ANCHORS; k++) local_anchor_responded[k] = false;

                // Ranging Loop
                for (int ii = 0; ii < NUM_ANCHORS; ii++) {
                    // Dynamic Skipping Check
                    if (!anchor_is_active[ii]) {
                        if (millis() - anchor_inactive_ts[ii] < RETRY_INTERVAL) {
                            local_anchor_distance[ii] = 0;
                            local_pot_sig[ii] = -120.0f;
                            continue;
                        }
                    }

                    DW3000.setDestinationID(ID_PONG[ii]);
                    fin_de_com = 0;
                    curr_stage = 0;
                    waitingForResponse = false;

                    while (fin_de_com == 0) {
                        // Timeout Logic
                        if (waitingForResponse && ((millis() - timeoutStart) >= RESPONSE_TIMEOUT)) {
                            anchor_fail_count[ii]++;
                            if (anchor_fail_count[ii] >= MAX_FAILURES) {
                                anchor_is_active[ii] = false;
                                anchor_inactive_ts[ii] = millis();
                                anchor_fail_count[ii] = 0;
                            }
                            DW3000.softReset(); delay(1); DW3000.init(); DW3000.configureAsTX(); DW3000.clearSystemStatus();
                            local_anchor_distance[ii] = 0; local_pot_sig[ii] = -120.0f;
                            fin_de_com = 1; break;
                        }

                        // State Machine
                        switch (curr_stage) {
                            case 0: // Poll
                                DW3000.ds_sendFrame(1);
                                tx = DW3000.readTXTimestamp();
                                curr_stage = 1; timeoutStart = millis(); waitingForResponse = true;
                                break;
                            case 1: // Wait for Response
                                if (rx_status = DW3000.receivedFrameSucc()) {
                                    DW3000.clearSystemStatus();
                                    if ((rx_status == 1) && (DW3000.getDestinationID() == ID_PONG[ii]) && !DW3000.ds_isErrorFrame()) {
                                        curr_stage = 2; waitingForResponse = false;
                                    } else {
                                        // Error
                                        anchor_fail_count[ii]++;
                                        if (anchor_fail_count[ii] >= MAX_FAILURES) { anchor_is_active[ii] = false; anchor_inactive_ts[ii] = millis(); anchor_fail_count[ii] = 0; }
                                        DW3000.softReset(); delay(1); DW3000.init(); DW3000.configureAsTX(); DW3000.clearSystemStatus();
                                        local_anchor_distance[ii] = 0; local_pot_sig[ii] = -120.0f; fin_de_com = 1;
                                    }
                                }
                                break;
                            case 2: // Send Final
                                rx = DW3000.readRXTimestamp();
                                DW3000.ds_sendFrame(3);
                                t_roundA = rx - tx; tx = DW3000.readTXTimestamp(); t_replyA = tx - rx;
                                curr_stage = 3; timeoutStart = millis(); waitingForResponse = true;
                                break;
                            case 3: // Wait for Report
                                if (rx_status = DW3000.receivedFrameSucc()) {
                                    DW3000.clearSystemStatus();
                                    if (rx_status == 1 && !DW3000.ds_isErrorFrame()) {
                                        clock_offset = DW3000.getRawClockOffset(); curr_stage = 4; waitingForResponse = false;
                                    } else {
                                        // Error
                                        anchor_fail_count[ii]++;
                                        if (anchor_fail_count[ii] >= MAX_FAILURES) { anchor_is_active[ii] = false; anchor_inactive_ts[ii] = millis(); anchor_fail_count[ii] = 0; }
                                        DW3000.softReset(); delay(1); DW3000.init(); DW3000.configureAsTX(); DW3000.clearSystemStatus();
                                        local_anchor_distance[ii] = 0; local_pot_sig[ii] = -120.0f; fin_de_com = 1;
                                    }
                                }
                                break;
                            case 4: // Calculate
                                ranging_time = DW3000.ds_processRTInfo(t_roundA, t_replyA, DW3000.read(0x12, 0x04), DW3000.read(0x12, 0x08), clock_offset);
                                float distance_meters = DW3000.convertToCM(ranging_time) / 100.0;
                                local_pot_sig[ii] = DW3000.getSignalStrength();
                                local_anchor_responded[ii] = true;
                                anchor_is_active[ii] = true; anchor_fail_count[ii] = 0;

                                if (distance_meters > 0) {
                                    local_anchor_distance[ii] = kalmanFilterDistance(distance_meters, ii);
                                } else {
                                    local_anchor_distance[ii] = 0;
                                }
                                fin_de_com = 1;
                                break;
                        }
                    }
                } // End Anchor Loop

                // Calculate Position
                int responding_anchors = 0;
                int responded_idx[NUM_ANCHORS];
                for(int k=0; k<NUM_ANCHORS; k++) {
                    if(local_anchor_responded[k]) responded_idx[responding_anchors++] = k;
                }

                if (responding_anchors >= 4) {
                    float x, y, z;
                    if (calculateWLSQPosition(responded_idx, responding_anchors, &x, &y, &z, local_anchor_distance, local_pot_sig)) {
                        // Smooth Limits
                        if (x < 0.0f) x = x * 0.1f; else if (x > 10.6f) x = 10.6f + (x - 10.6f) * 0.1f;
                        if (y < 0.0f) y = y * 0.1f; else if (y > 6.40f) y = 6.40f + (y - 6.40f) * 0.1f;
                        if (z < 0.0f) z = z * 0.1f; else if (z > 3.0f) z = 3.0f + (z - 3.0f) * 0.1f;

                        kalmanFilterPosition3D(x, y, z);
                        
                        if (kalman_z < 0.0 || kalman_z > 2.5) { kalman_z = 1.0; } // Floor fix

                        last_wlsq_time = millis();
                        last_valid_position_3d[0] = kalman_x;
                        last_valid_position_3d[1] = kalman_y;
                        last_valid_position_3d[2] = kalman_z;
                    }
                } else {
                    if (millis() - last_wlsq_time < 2000) {
                        kalman_x = last_valid_position_3d[0];
                        kalman_y = last_valid_position_3d[1];
                        kalman_z = last_valid_position_3d[2];
                    }
                }

                // Send Data to Queue
                TagDataPacket packet;
                packet.x = kalman_x;
                packet.y = kalman_y;
                packet.z = kalman_z;
                packet.timestamp = millis();
                for(int i=0; i<NUM_ANCHORS; i++) {
                    packet.anchor_dist[i] = local_anchor_distance[i];
                    packet.anchor_rssi[i] = local_pot_sig[i];
                    packet.anchor_resp[i] = local_anchor_responded[i];
                }
                
                // Overwrite if full (we want latest data)
                xQueueOverwrite(uwbQueue, &packet);
            }
        }
        vTaskDelay(1); // Yield
    }
}

// CORE 0: Communications Task
void TaskComms(void *pvParameters) {
    Serial.println("[Core 0] Comms Task Started");

    // WiFi Setup
    if (USE_AP_MODE) {
        WiFi.mode(WIFI_AP);
        WiFi.softAP(AP_SSID, AP_PASS);
    } else {
        WiFi.mode(WIFI_STA);
        esp_wifi_set_ps(WIFI_PS_NONE);
        WiFi.begin(STA_SSID, STA_PASS);
        while (WiFi.status() != WL_CONNECTED) {
            vTaskDelay(pdMS_TO_TICKS(500));
            Serial.print(".");
        }
        Serial.println("\nWiFi Connected");
        WiFi.setTxPower(WIFI_POWER_19_5dBm);
    }

    // WebServer Setup
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *req){ req->send_P(200, "text/html", INDEX_HTML); });
    server.on("/data", HTTP_GET, [](AsyncWebServerRequest *req){ req->send(200, "application/json", getDataJson()); });
    ws.onEvent([](AsyncWebSocket *s, AsyncWebSocketClient *c, AwsEventType t, void*, uint8_t*, size_t){});
    server.addHandler(&ws);
    server.begin();

    // MQTT Setup
    client.setServer(mqtt_server, mqtt_port);
    snprintf(status_topic, sizeof(status_topic), "uwb/tag/%d/status", TAG_ID);

    TagDataPacket packet;
    unsigned long lastMqttReconnect = 0;
    unsigned long lastWsSend = 0;

    for(;;) {
        // 1. Receive Data from Queue
        if (xQueueReceive(uwbQueue, &packet, pdMS_TO_TICKS(10)) == pdTRUE) {
            // Update Globals (Protected)
            if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                global_tagPositionX = packet.x;
                global_tagPositionY = packet.y;
                global_tagPositionZ = packet.z;
                for(int i=0; i<NUM_ANCHORS; i++) {
                    global_anchor_distance[i] = packet.anchor_dist[i];
                    global_pot_sig[i] = packet.anchor_rssi[i];
                }
                xSemaphoreGive(dataMutex);
            }

            // MQTT Publish
            if (client.connected()) {
                StaticJsonDocument<512> doc;
                doc["tag_id"] = TAG_ID;
                doc["timestamp_ms"] = packet.timestamp;
                
                JsonObject position = doc.createNestedObject("position");
                position["x"] = packet.x; position["y"] = packet.y; position["z"] = packet.z;

                JsonObject anchorDistances = doc.createNestedObject("anchor_distances");
                for (int i = 0; i < NUM_ANCHORS; i++) {
                    if (packet.anchor_resp[i]) {
                        anchorDistances[String(ID_PONG[i])] = packet.anchor_dist[i];
                    }
                }

                char buffer[512];
                size_t n = serializeJson(doc, buffer);
                client.publish(status_topic, buffer, n);
            }
        }

        // 2. Maintain MQTT Connection
        if (!client.connected()) {
            if (millis() - lastMqttReconnect > 5000) {
                lastMqttReconnect = millis();
                String clientId = "ESP32-Tag-" + String(TAG_ID) + "-" + WiFi.macAddress();
                if (client.connect(clientId.c_str())) {
                    Serial.println("[MQTT] Connected");
                }
            }
        }
        client.loop();

        // 3. WebSocket Broadcast (Throttled)
        if (millis() - lastWsSend > 20) { // 50Hz
            lastWsSend = millis();
            String json = getDataJson();
            ws.cleanupClients();
            if (ws.count() > 0) ws.textAll(json);
        }

        vTaskDelay(1); // Yield
    }
}

void setup() {
  Serial.begin(115200);
  
  // Init Mutex & Queue
  dataMutex = xSemaphoreCreateMutex();
  uwbQueue = xQueueCreate(1, sizeof(TagDataPacket)); // Size 1, overwrite mode

  // Init DW3000
  SPI.begin();
  DW3000.begin();
  SPI.setFrequency(8000000);
  DW3000.hardReset(); delay(200);
  DW3000.softReset(); delay(200);
  DW3000.init();
  DW3000.setupGPIO();
  DW3000.configureAsTX();
  DW3000.clearSystemStatus();

  // Create Tasks
  // Core 1: UWB (High Priority)
  xTaskCreatePinnedToCore(TaskUWB, "UWB_Task", 10000, NULL, 2, NULL, 1);
  
  // Core 0: Comms (Standard Priority)
  xTaskCreatePinnedToCore(TaskComms, "Comms_Task", 10000, NULL, 1, NULL, 0);
}

void loop() {
  // Empty - tasks handle everything
  vTaskDelete(NULL);
}