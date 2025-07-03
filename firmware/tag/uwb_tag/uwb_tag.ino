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

// ===== TAG IDENTIFICATION =====
#define TAG_ID 1 


const uint32_t WS_SEND_INTERVAL_MS = 33; // 1000/33 ≈ 30 fps

// ===== WiFi CONFIGURATION =====
#define USE_AP_MODE false
#define AP_SSID "UWB_TAG_AP"
#define AP_PASS "12345678"
#define STA_SSID "iPhone de Nicolas"
#define STA_PASS "12345678"

// Server configuration 
#define HTTP_PORT 80
AsyncWebServer server(HTTP_PORT);
AsyncWebSocket ws("/ws");

// MQTT Configuration
const char* mqtt_server = "172.20.10.2"; 
const int mqtt_port = 1883;
const char* log_topic = "uwb/tag/logs";       
char status_topic[30];                      
WiFiClient espClient;
PubSubClient client(espClient);

// ===== Configuration for WiFi Logging =====
const char* logServerIp = "172.20.10.2"; 
const int logServerPort = 5000;             

// ===== TDMA Configuration (INDOOR) =====
const unsigned long TDMA_CYCLE_MS = 60; 
const unsigned long TDMA_SLOT_DURATION_MS = 20; 

// ===== RANGING CONFIGURATION =====
#define ROUND_DELAY 100
static int frame_buffer = 0;
static int rx_status;
static int tx_status;

// Ranging states
static int curr_stage = 0;

static int t_roundA = 0;
static int t_replyA = 0;

static long long rx = 0;
static long long tx = 0;

static int clock_offset = 0;
static int ranging_time = 0;
static float distance = 0;

// Configuration for measurements and filtering (INDOOR)
#define NUM_MEASUREMENTS 3
#define NUM_ANCHORS 5 
int ID_PONG[NUM_ANCHORS] = {1, 2, 3, 4, 5}; 
float distance_buffer[NUM_ANCHORS][NUM_MEASUREMENTS] = { {0} };
int buffer_index[NUM_ANCHORS] = {0};
float anchor_distance[NUM_ANCHORS] = {0};
float anchor_avg[NUM_ANCHORS] = {0};
float pot_sig[NUM_ANCHORS] = {0};
static int fin_de_com = 0;
bool anchor_responded[NUM_ANCHORS] = {false}; 

// Variables for timeout 
unsigned long timeoutStart = 0;
bool waitingForResponse = false;
const unsigned long RESPONSE_TIMEOUT = 35; 

// Variables for state manager 
unsigned long lastUpdate = 0;
unsigned long updateInterval = 12; 

// Variables for low power mode
unsigned long lastActivityTime = 0;
const unsigned long SLEEP_TIMEOUT = 300000;
bool lowPowerMode = false;

// Variables for Kalman Filter 
float kalman_dist[NUM_ANCHORS][2] = { {0} };
float kalman_dist_q = 0.005; 
float kalman_dist_r = 0.08; 

// Variables for position 
float kalman_x = 0.0;
float kalman_y = 0.0;
float kalman_p_x = 1.0;
float kalman_p_y = 1.0;
float kalman_q = 0.01; 
float kalman_r = 0.05; 

// Variables for tag position
float tagPositionX = 0.0;
float tagPositionY = 0.0;

// Variables for intelligent trilateration 
int last_anchor_combination[3] = {0, 1, 2}; 
unsigned long last_trilateration_time = 0;
float last_valid_position[2] = {0.0, 0.0}; 
bool combination_stable = false; 
float rssi_threshold = 5.0; 
float validation_threshold = 1.0; 

// ===== GLOBAL ANCHOR POSITIONS (anchors 1-5) =====
const float anchorsPos[NUM_ANCHORS][2] = {
  {-6.0,  0.0},   // Anchor 1 (index 0) - West
  {-2.6,  7.92},  // Anchor 2 (index 1) - Northwest 
  { 2.1, 10.36},  // Anchor 3 (index 2) - Northeast
  { 6.35, 0.0},   // Anchor 4 (index 3) - East 
  { 0.0, -1.8}    // Anchor 5 (index 4) - South center
};

// ===== HELPER FUNCTIONS =====
int getAnchorIndex(int anchor_id) {
  if (anchor_id >= 1 && anchor_id <= 5) {
    return anchor_id - 1;
  }
  return -1; 
}

int getAnchorNumber(int array_index) {
  return array_index + 1;
}

// ===== INTELLIGENT TRILATERATION =====
bool selectOptimalAnchors(int* available_anchors, int count, int* selected) {
  if (count < 3) return false;
  
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
      // Keep if the average RSSI is still good
      if (previous_avg_rssi > -85.0) {
        selected[0] = last_anchor_combination[0];
        selected[1] = last_anchor_combination[1];
        selected[2] = last_anchor_combination[2];
        can_keep_previous = true;
        Serial.printf("[TRILAT-A] Keeping previous: [%d,%d,%d], RSSI=%.1f\n", 
                     getAnchorNumber(selected[0]), getAnchorNumber(selected[1]), getAnchorNumber(selected[2]), previous_avg_rssi);
      }
    }
  }
  
  // === STEP 2: New selection by RSSI + geometry ===
  if (!can_keep_previous) {
    // Sort anchors by RSSI (best first)
    int sorted_anchors[NUM_ANCHORS];
    float sorted_rssi[NUM_ANCHORS];
    
         for (int i = 0; i < count; i++) {
       sorted_anchors[i] = available_anchors[i];
       sorted_rssi[i] = pot_sig[available_anchors[i]];
     }
    
    // Bubble sort by descending RSSI
    for (int i = 0; i < count - 1; i++) {
      for (int j = 0; j < count - i - 1; j++) {
        if (sorted_rssi[j] < sorted_rssi[j + 1]) {
          // Swap RSSI
          float temp_rssi = sorted_rssi[j];
          sorted_rssi[j] = sorted_rssi[j + 1];
          sorted_rssi[j + 1] = temp_rssi;
          // Swap indices
          int temp_anchor = sorted_anchors[j];
          sorted_anchors[j] = sorted_anchors[j + 1];
          sorted_anchors[j + 1] = temp_anchor;
        }
      }
    }
    
    // Initially take the 3 best by RSSI
    selected[0] = sorted_anchors[0];
    selected[1] = sorted_anchors[1];
    selected[2] = sorted_anchors[2];
    
    // Verify geometry of this trio
         float det = calculateDeterminant(selected[0], selected[1], selected[2]);
    
    // If geometry is bad, replace the worst RSSI with the next one
    if (fabs(det) < 0.001 && count > 3) {
      selected[2] = sorted_anchors[3]; // Replace the 3rd (worst RSSI of the trio) with the 4th
      det = calculateDeterminant(selected[0], selected[1], selected[2]);
      Serial.printf("[TRILAT-A] Replacing worst RSSI of the trio with the 4th: [%d,%d,%d\n", 
                   getAnchorNumber(selected[0]), getAnchorNumber(selected[1]), getAnchorNumber(selected[2]));
    }
    
    // Update stable combination
    last_anchor_combination[0] = selected[0];
    last_anchor_combination[1] = selected[1];
    last_anchor_combination[2] = selected[2];
    combination_stable = true;
    
    Serial.printf("[TRILAT-A] New selection: [%d,%d,%d], RSSI=[%.1f,%.1f,%.1f], Det=%.3f\n",
                  getAnchorNumber(selected[0]), getAnchorNumber(selected[1]), getAnchorNumber(selected[2]),
                  pot_sig[selected[0]], pot_sig[selected[1]], pot_sig[selected[2]], det);
  }
  
  // === STEP 3: Calculate provisional position ===
  float test_x, test_y;
  bool trilat_ok = calculateTrilateration(selected[0], selected[1], selected[2], &test_x, &test_y);
  
  if (!trilat_ok) return false;
  
  // === STEP 4: Validate with remaining anchors ===
  bool validation_passed = true;
  float max_error = 0;
  int worst_anchor = -1;
  
  for (int i = 0; i < count; i++) {
    int anchor_id = available_anchors[i];
    
    // Skip the 3 already used
    if (anchor_id == selected[0] || anchor_id == selected[1] || anchor_id == selected[2]) {
      continue;
    }
    
    // Calculate expected distance vs measured
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
    
    Serial.printf("[TRILAT-A] Validation anchor %d: expected=%.2fm, measured=%.2fm, error=%.2fm\n",
                 getAnchorNumber(anchor_id), expected_dist, measured_dist, error);
  }
  
  // === STEP 5: Re-selection if validation fails ===
  if (!validation_passed && count >= 4) {
    Serial.printf("[TRILAT-A] Validation failed, max error=%.2fm in anchor %d, retrying...\n", 
                 max_error, getAnchorNumber(worst_anchor));
    
    // Try replacing the worst RSSI of the current trio with the one that failed validation
    if (worst_anchor >= 0) {
             // Find which of the trio has the worst RSSI
       int worst_in_trio = selected[0];
       float worst_rssi = pot_sig[selected[0]];
       
       for (int i = 1; i < 3; i++) {
         if (pot_sig[selected[i]] < worst_rssi) {
           worst_rssi = pot_sig[selected[i]];
          worst_in_trio = selected[i];
        }
      }
      
      // Replace
      for (int i = 0; i < 3; i++) {
        if (selected[i] == worst_in_trio) {
          selected[i] = worst_anchor;
          break;
        }
      }
      
      Serial.printf("[TRILAT-A] Replacement: anchor %d by %d\n", getAnchorNumber(worst_in_trio), getAnchorNumber(worst_anchor));
      
      // Update combination
      last_anchor_combination[0] = selected[0];
      last_anchor_combination[1] = selected[1];
      last_anchor_combination[2] = selected[2];
    }
  }
  
  return true;
}

// Helper function to calculate determinant (uses global anchorsPos)
float calculateDeterminant(int a0, int a1, int a2) {
  float A = 2 * (anchorsPos[a1][0] - anchorsPos[a0][0]);
  float B = 2 * (anchorsPos[a1][1] - anchorsPos[a0][1]);
  float D = 2 * (anchorsPos[a2][0] - anchorsPos[a1][0]);
  float E = 2 * (anchorsPos[a2][1] - anchorsPos[a1][1]);
  return A * E - B * D;
}

// Helper function for trilateration (uses global anchorsPos)
bool calculateTrilateration(int a0, int a1, int a2, float* result_x, float* result_y) {
  float x1 = anchorsPos[a0][0], y1 = anchorsPos[a0][1];
  float x2 = anchorsPos[a1][0], y2 = anchorsPos[a1][1]; 
  float x3 = anchorsPos[a2][0], y3 = anchorsPos[a2][1];
  
  float r1 = anchor_distance[a0]; 
  float r2 = anchor_distance[a1]; 
  float r3 = anchor_distance[a2]; 
  
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

// Structure to define interest zones
#define NUM_ZONES 5 
struct Zone {
  float x;
  float y;
  float radius;
  bool tagInside;
  unsigned long entryTime;
  unsigned long minStayTime;
  bool stayTimeReached;
};

Zone zones[NUM_ZONES] = {
   //   x ,   y ,  r , inZone,lastEntry,minStay,flag
   {  0.0,  9.0, 1.5, false, 0, 750,  false},   // North zone
   {  0.0, -2.0, 1.5, false, 0, 750,  false},   // South zone
   {  5.5,  4.0, 1.5, false, 0, 500,  false},   // East zone
   { -5.5,  4.0, 1.5, false, 0, 500,  false},   // West zone
   {  0.0,  4.0, 2.0, false, 0, 1000, false}    // Central zone
};

// Variables for MQTT and State 
unsigned long lastMqttReconnectAttempt = 0;
unsigned long lastStatusUpdate = 0;
const long statusUpdateInterval = 80; 
String last_anchor_id = "N/A"; 

// ===== SYSTEM BUFFERING =====
struct StabilizedBuffer {
  float position_x_buffer[8];
  float position_y_buffer[8];
  unsigned long timestamp_buffer[8];
  int buffer_head = 0;
  int buffer_count = 0;
  unsigned long last_output_time = 0;
  const unsigned long OUTPUT_INTERVAL = 80; 
} stable_buffer;

// ===== MQTT FLOW CONTROL VARIABLES =====
struct MQTTFlowControl {
  unsigned long last_successful_send = 0;
  unsigned long last_connection_check = 0;
  int consecutive_failures = 0;
  bool flow_control_active = false;
  const unsigned long CONNECTION_CHECK_INTERVAL = 1000; // Check connection every 1s
  const int MAX_CONSECUTIVE_FAILURES = 3;
} mqtt_flow;

// HTML for the integrated web page 
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
    /* Remove battery styles */
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
    let tagPosition = { x: 150, y: 150 }; // Current position in pixels (updated by animation)
    let tagTarget   = { x: 150, y: 150 }; // Next destination received

    // Visualization variables (missing after refactor)
    let visualizationInitialized = false;
    let vizElements = {
        container: null,
        border: null,
        anchorPoints: {},
        distanceCircles: {},
        tagPoint: null
    };
    let anchorListItems = {}; // Cache DOM elements of anchors

    // WebSocket connection to receive real-time push data
    const socket = new WebSocket(`ws://${window.location.host}/ws`);

    socket.addEventListener('message', (evt) => {
      try {
        const data = JSON.parse(evt.data);
        window.currentTagPositionFromESP = data.position;
        window.currentAnchorsData = data.anchors;
        updateUI(data);
      } catch (e) { console.error('WS parse error', e); }
    });

    socket.addEventListener('open', () => console.log('[WS] connected'));
    socket.addEventListener('close', () => console.warn('[WS] closed'));

    // Continuous animation at ~60 fps using requestAnimationFrame
    function animateTag() {
      const lerp = 0.15; // Interpolation factor (0-1)
      tagPosition.x += (tagTarget.x - tagPosition.x) * lerp;
      tagPosition.y += (tagTarget.y - tagPosition.y) * lerp;

      if (vizElements.tagPoint) {
        vizElements.tagPoint.style.left = tagPosition.x + 'px';
        vizElements.tagPoint.style.top  = tagPosition.y + 'px';
      }
      requestAnimationFrame(animateTag);
    }
    requestAnimationFrame(animateTag);

    // Get data from ESP32
    function fetchData() {
      fetch('/data')
        .then(response => response.json())
        .then(data => {
          window.currentTagPositionFromESP = data.position; // Store ESP position
          window.currentAnchorsData = data.anchors; // Store anchor data in case renderVisualization needs it directly
          updateUI(data); // Pass all data to updateUI
          lastUpdate = Date.now();
        })
        .catch(error => {
          console.error('Error:', error);
          document.getElementById('status').textContent = 'Connection error';
        });
    }
    
    // Update the interface with the received data
    function updateUI(data) {
      // Update anchor data (we'll use window.currentAnchorsData or data.anchors)
      anchors = data.anchors; // Keep this for if renderVisualization uses it directly

      // Debug - show distances in console
      // console.log("Distancias recibidas (cm):", anchors.map(a => a.dist));

      // --- Optimization: Update anchor list without recreating everything ---
      const anchorsContainer = document.getElementById('anchors-container');
      let anchorsChanged = anchorsContainer.children.length !== anchors.length;

      anchors.forEach((anchor, i) => {
        let anchorDiv = anchorListItems[anchor.id];
        if (!anchorDiv) {
          // Create the anchor div if it doesn't exist
          anchorDiv = document.createElement('div');
          anchorDiv.className = 'anchor';
          anchorDiv.id = `anchor-list-item-${anchor.id}`;
          anchorDiv.innerHTML = `
            <div>
              <strong>Anchor ${anchor.id}</strong>
              <p>Distance: <span class="anchor-dist">${(anchor.dist / 100).toFixed(2)}</span> m</p>
            </div>
            <div>
              <p>Signal: <span class="anchor-rssi">${anchor.rssi.toFixed(1)}</span> dBm</p>
            </div>
          `;
          anchorsContainer.appendChild(anchorDiv);
          anchorListItems[anchor.id] = anchorDiv; // Store reference
          anchorsChanged = true;
        } else {
          // Update data if it already exists
          anchorDiv.querySelector('.anchor-dist').textContent = (anchor.dist / 100).toFixed(2);
          anchorDiv.querySelector('.anchor-rssi').textContent = anchor.rssi.toFixed(1);
        }
      });
      // We could add logic to remove anchors if they disappear, but we assume they're fixed
      // --- End Optimization Anchor List ---
      // We don't need the anchors.length >=4 condition here if we trust data.position
      calculateTagPosition(); // This function now uses window.currentTagPositionFromESP
      
      // Update visualization
      renderVisualization();
      
      // Update state
      document.getElementById('status').textContent = 'Last update: ' + new Date().toLocaleTimeString(); 
    }

    // Calculation of position by trilateration
    function calculateTagPosition() {
        // Physical space configuration INDOOR 
        const minX = -6.9;
        const maxX =  6.8;
        const minY = -3.5;
        const maxY = 10.36;

        const areaWidth  = maxX - minX; // 13.7 m
        const areaHeight = maxY - minY; // 13.86 m
        const scale = 40;        // 1m = 40px (optimized for web container)
        const margin = 15;       // reduced margin in pixels
      
        // Width and height of the visualization area in pixels
        const vizWidth = areaWidth * scale + 2 * margin;
        const vizHeight = areaHeight * scale + 2 * margin;

        // Get the X, Y position calculated by the ESP32 (which should already be filtered by Kalman if active in C++)
        // These values come from data.position.x and data.position.y in updateUI
        // We need to access the 'data' variable globally or pass it.
        // For simplicity, we assume that 'currentData' is a global variable updated in fetchData.
        // It would be better to pass 'data.position' as an argument to calculateTagPosition.
        

        if (!window.currentTagPositionFromESP) {
            document.getElementById('tag-position').textContent = "Waiting for ESP data...";
            return;
        }

        let esp_x = window.currentTagPositionFromESP.x;
        let esp_y = window.currentTagPositionFromESP.y;

        // Debug: show the received position from the ESP32
        console.log("Received position from ESP32 (meters):", esp_x, esp_y);
              
        try {
          // Limit to the new irregular hexagon limits
          const boundedX = Math.max(minX, Math.min(maxX, esp_x));
          const boundedY = Math.max(minY, Math.min(maxY, esp_y));
      
          // Convert to visualization coordinates
          const pixelX = margin + (boundedX - minX) * scale;
          const pixelY = vizHeight - margin - (boundedY - minY) * scale;
      
          // Update target for fluid animation
          tagTarget.x = pixelX;
          tagTarget.y = pixelY;

          // Refresh position text
          document.getElementById('tag-position').textContent = 
            `X: ${boundedX.toFixed(2)}m, Y: ${boundedY.toFixed(2)}m (ESP32)`;
        } catch (e) {
          console.error('Error in ESP position conversion:', e);
          document.getElementById('tag-position').textContent = "Error in visualization";
        }
      }
    
    // --- Optimization: Render visualization updating existing elements ---
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

        const currentAnchorsToRender = window.currentAnchorsData || anchors; // Use updated data

        // Draw the real perimeter of the irregular hexagon using SVG
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", vizWidth);
        svg.setAttribute("height", vizHeight);
        svg.style.position = 'absolute';
        svg.style.left = '0';
        svg.style.top  = '0';

        // Hexagon vertices in meters (in order)
        const hexVertices = [
          { x: -6.9, y: -2   }, // V1
          { x: -1.6, y: 10.36}, // V2 (physical perimeter of the field)
          { x:  2.1, y: 10.36}, // V3
          { x:  6.8, y: -1.8 }, // V4
          { x:  0.0, y: -1.8 }, // V5
          { x: -0.4, y: -3.5 }  // V6
        ];

        // Anchor positions with IDs
        const anchorsPosMetros = [
          { id: 1, x: -6.0,  y: 0.0  },
          { id: 2, x: -2.6, y: 7.92},
          { id: 3, x:  2.1, y: 10.36},
          { id: 4, x:  6.35, y: 0.0 },
          { id: 5, x:  0.0, y: -1.8 }
        ];

        // Convert to pixel coordinates with the same system we use for anchors
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
        vizElements.border = polygon; // Store
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData, i) => {
                const anchorCfg = anchorsPosMetros.find(a => a.id === anchorData.id);
                if (!anchorCfg) return; // If there is no configuration for this anchor ID

                const anchorPixelX = margin + (anchorCfg.x - minX) * scale;
                const anchorPixelY = vizHeight - margin - (anchorCfg.y - minY) * scale;

                const dot = document.createElement('div');
                dot.className = 'anchor-point';
                dot.textContent = anchorData.id; // Use anchor ID
                dot.title = `Anchor ${anchorData.id}`;
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
                const radius = (anchorData.dist / 100) * scale; // Convert to meters for visualization
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

        // Update distance circles only if there are anchor data
        if (currentAnchorsToRender && currentAnchorsToRender.length > 0) {
            currentAnchorsToRender.forEach((anchorData) => {
                const circle = vizElements.distanceCircles[anchorData.id];
                if (circle) {
                    const radius = (anchorData.dist / 100) * scale; // Convert to meters for update
                    const currentWidth = parseFloat(circle.style.width) || 0;
                    if (radius >= 0 && Math.abs(radius * 2 - currentWidth) > 0.1) { 
                        circle.style.width = radius * 2 + 'px';
                        circle.style.height = radius * 2 + 'px';
                    }
                }
            });
        }

        // Update tag position (must be done always if tagPoint exists)
        const tagPoint = vizElements.tagPoint;
        if (tagPoint && typeof tagPosition.x === 'number' && typeof tagPosition.y === 'number' && !isNaN(tagPosition.x) && !isNaN(tagPosition.y)) {
           console.log("Drawing TAG in (pixels):", tagPosition.x, tagPosition.y); // For debugging
           // Update absolute tag position
           tagPoint.style.left = tagPosition.x + 'px';
           tagPoint.style.top  = tagPosition.y + 'px';
           // Keep the point centered
           tagPoint.style.transform = 'translate(-50%, -50%)';
        } else if (tagPoint) {
          console.log("Invalid TAG position or tagPoint not ready:", tagPosition.x, tagPosition.y); // For debugging
        }
      }
    }
    // --- End Optimization Visualization ---

    // Request data update
    function requestUpdate() {
      fetchData();
    }
    
    // First load in case the WebSocket takes a while to connect
    fetchData();

    // Polling backup every 1 s only if WS is closed
    setInterval(() => {
      if (socket.readyState !== WebSocket.OPEN) fetchData();
    }, 1000);
  </script>
</body>
</html>
)rawliteral";

// ===== FUNCTIONS =====

// Kalman filter for distances
float kalmanFilterDistance(float measurement, int anchor_id) {
  kalman_dist[anchor_id][1] = kalman_dist[anchor_id][1] + kalman_dist_q;
  float k = kalman_dist[anchor_id][1] / (kalman_dist[anchor_id][1] + kalman_dist_r);
  kalman_dist[anchor_id][0] = kalman_dist[anchor_id][0] + k * (measurement - kalman_dist[anchor_id][0]);
  kalman_dist[anchor_id][1] = (1 - k) * kalman_dist[anchor_id][1];
  return kalman_dist[anchor_id][0];
}

// Kalman filter for 2D position
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

// Configure WiFi connection
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
    // Disable Wi-Fi Power-Save for minimum latency
    esp_wifi_set_ps(WIFI_PS_NONE);
    WiFi.setSleep(false);
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
      Serial.println(WiFi.status());
    }
  }
}

// Generate data in JSON format using ArduinoJson
String getDataJson() {
  // Calculate the necessary size for the JSON
  const int capacity = JSON_OBJECT_SIZE(4) + 
                       JSON_ARRAY_SIZE(NUM_ANCHORS) + 
                       NUM_ANCHORS * JSON_OBJECT_SIZE(3) + 
                       JSON_OBJECT_SIZE(2) + 
                       JSON_OBJECT_SIZE(NUM_ANCHORS);
                       
  StaticJsonDocument<capacity> doc;
  // Add anchor data
  JsonArray anchorsArray = doc.createNestedArray("anchors");
  for (int i = 0; i < NUM_ANCHORS; i++) {
    JsonObject anchorObject = anchorsArray.createNestedObject();
    anchorObject["id"] = ID_PONG[i];
    anchorObject["dist"] = isnan(anchor_distance[i]) || isinf(anchor_distance[i]) ? 0.0 : (anchor_distance[i] * 100); // Meters to cm for WebSocket
    anchorObject["rssi"] = isnan(pot_sig[i]) || isinf(pot_sig[i]) ? -100.0 : pot_sig[i];
  }
  
  // Add tag position
  JsonObject positionObject = doc.createNestedObject("position");
  positionObject["x"] = isnan(tagPositionX) || isinf(tagPositionX) ? 0.0 : tagPositionX;
  positionObject["y"] = isnan(tagPositionY) || isinf(tagPositionY) ? 0.0 : tagPositionY;

  // Serialize JSON to String
  String output;
  serializeJson(doc, output);
  return output;
}

// Configure the web server
void setupWebServer() {
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *req){
    req->send_P(200, "text/html", INDEX_HTML);
  });
  server.on("/data", HTTP_GET, [](AsyncWebServerRequest *req){
    req->send(200, "application/json", getDataJson());
  });

  ws.onEvent([](AsyncWebSocket *s, AsyncWebSocketClient *c, AwsEventType t, void*, uint8_t*, size_t){
    if(t==WS_EVT_CONNECT){
      Serial.printf("[WS] Client #%u connected, IP %s\n", c->id(), c->remoteIP().toString().c_str());
    }
  });
  server.addHandler(&ws);
  server.begin();
  Serial.println("AsyncWebServer + WebSocket started on :80");
}


// Check if the tag is inside any defined zone
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
        
        Serial.print("Tag entered zone ");
        Serial.println(i);
      }
      
      if (millis() - zones[i].entryTime >= zones[i].minStayTime && !zones[i].stayTimeReached) {
        zones[i].stayTimeReached = true;
        
        Serial.print("Minimum time reached in zone ");
        Serial.println(i);
      }
    } else {
      if (zones[i].tagInside) {
        zones[i].tagInside = false;
        zones[i].stayTimeReached = false;
        
        Serial.print("Tag left zone ");
        Serial.println(i);
      }
    }
  }
}

// --- MQTT FUNCTIONS --- 

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
   // STABILIZED BUFFERING SIMPLIFIED - 80ms fixed = 12.5 Hz
   static unsigned long lastPublish = 0;
   unsigned long currentTime = millis();
   
   // Strict timing control - EXACTLY every 80ms
   if (currentTime - lastPublish < 80) {
     return; // Exit immediately if the time hasn't passed
   }
   
   // Verify MQTT connection once per send
   if (!client.connected()) {
     Serial.println("[MQTT] Disconnected, skipping send");
     return;
   }
   
   // Update timestamp BEFORE processing to avoid overlaps
   lastPublish = currentTime;
   
   // Prepare optimized JSON with improved validation
   StaticJsonDocument<512> doc;
   doc["tag_id"] = TAG_ID;
   doc["last_anchor_id"] = last_anchor_id;
   doc["timestamp_ms"] = currentTime;

   // POSITION with more robust NaN/Inf validation
   JsonObject position = doc.createNestedObject("position");
   float safe_x = (isnan(tagPositionX) || isinf(tagPositionX)) ? 0.0 : tagPositionX;
   float safe_y = (isnan(tagPositionY) || isinf(tagPositionY)) ? 0.0 : tagPositionY;
   position["x"] = safe_x;
   position["y"] = safe_y;

   // DISTANCES with strict validation
   JsonObject anchorDistances = doc.createNestedObject("anchor_distances");
   for (int i = 0; i < NUM_ANCHORS; i++) {
     String anchorKey = String(ID_PONG[i]);
     float dist = anchor_distance[i];
     
     // More strict validation: 0.1-20m realistic indoor range
     if (isnan(dist) || isinf(dist) || dist < 0.1 || dist > 20.0) {
       dist = 0.0;
     }
     anchorDistances[anchorKey] = dist;
   }

   // Serialize and send with improved error handling
   char buffer[512];
   size_t n = serializeJson(doc, buffer);

   if (client.publish(status_topic, buffer, n)) {
     // Silent
       Serial.printf("[MQTT] %d messages sent OK (12.5Hz stable)\n", successCount);
     }
   } else {
     Serial.printf("[MQTT] Error sending position at timestamp %lu\n", currentTime);
   }
}

void broadcastWebSocket(){
  static uint32_t lastWs=0;
  uint32_t now = millis();
  if(now - lastWs < WS_SEND_INTERVAL_MS) return; // limit to 30 fps
  String json = getDataJson();
  ws.textAll(json);
  lastWs = now;
}

// ===== STABILIZED BUFFERING FUNCTION =====
void addToStabilizedBuffer(float x, float y) {
  unsigned long currentTime = millis();
  
  // Add to circular buffer
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
  
  // Check if it's time to send
  if (currentTime - stable_buffer.last_output_time < stable_buffer.OUTPUT_INTERVAL) {
    return false;
  }
  
  if (stable_buffer.buffer_count == 0) {
    return false;
  }
  
  // Calculate weighted average position (more weight to recent data)
  float sum_x = 0, sum_y = 0, total_weight = 0;
  
  for (int i = 0; i < stable_buffer.buffer_count; i++) {
    int idx = (stable_buffer.buffer_head - 1 - i + 8) % 8;
    float age = currentTime - stable_buffer.timestamp_buffer[idx];
    float weight = exp(-age / 200.0); // Exponential decay
    
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

// ===== IMPROVED MQTT FLOW CONTROL =====
bool checkMQTTFlowControl() {
  unsigned long currentTime = millis();
  
  // Verify connection periodically
  if (currentTime - mqtt_flow.last_connection_check > mqtt_flow.CONNECTION_CHECK_INTERVAL) {
    mqtt_flow.last_connection_check = currentTime;
    
    if (!client.connected()) {
      mqtt_flow.consecutive_failures++;
      if (mqtt_flow.consecutive_failures >= mqtt_flow.MAX_CONSECUTIVE_FAILURES) {
        mqtt_flow.flow_control_active = true;
        Serial.println("[MQTT] Flow control activated by disconnection");
      }
      return false;
    } else {
      // Connection OK, reset counters
      mqtt_flow.consecutive_failures = 0;
      mqtt_flow.flow_control_active = false;
    }
  }
  
  return !mqtt_flow.flow_control_active;
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== UWB TAG with WiFi, Web Server, and MQTT ===
  btStop();
  esp_bt_controller_disable();
  
  setupWiFi();
  
  setupWebServer();
  
  // Setup MQTT
  client.setServer(mqtt_server, mqtt_port);
  snprintf(status_topic, sizeof(status_topic), "%s%d/status", "uwb/tag/", TAG_ID); // Build status topic example: uwb/tag/1/status
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
  Serial.println("[INFO] DW3000 initialized correctly.");

  DW3000.configureAsTX();
  DW3000.clearSystemStatus(); 

  lastActivityTime = millis();
  lastUpdate = millis();
}

void loop() {
  ws.cleanupClients(); // keep clients active (no blocks)
  // server.handleClient();  // no used with AsyncWebServer
  
  // Handle MQTT Client
  if (!client.connected()) {
    reconnectMQTT(); // Try to reconnect if disconnected
  }
  client.loop(); // Allow MQTT client to process messages/maintain connection

  unsigned long currentMillis = millis();
  
  if (!lowPowerMode && (currentMillis - lastActivityTime >= SLEEP_TIMEOUT)) {
    Serial.println("Entering low power mode...");
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
              Serial.print("Timeout REINFORCED for anchor ID: "); 
              Serial.println(ID_PONG[ii]);

              DW3000.softReset();
              delay(100); 
              DW3000.init(); 
              DW3000.configureAsTX(); 
              DW3000.clearSystemStatus(); 

              anchor_distance[ii] = 0;
              pot_sig[ii] = -120.0f; // Very low dBm to indicate bad quality/no signal
              anchor_responded[ii] = false;
              
              curr_stage = 0; 
              ranging_time = 0;
              waitingForResponse = false; 
              fin_de_com = 1; 
              
              Serial.println("[INFO] TAG DW3000 re-initialized post-timeout.");
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
                  DW3000.clearSystemStatus(); // Clear system status after reception
                  if ((rx_status == 1) && (DW3000.getDestinationID() == ID_PONG[ii])) {
                    if (DW3000.ds_isErrorFrame()) {
                      Serial.println("[WARNING] Error frame detected! Reverting to stage 0.");
                      curr_stage = 0;
                      waitingForResponse = false;
                      // We don't break the while (fin_de_com), we let it try again or timeout if the anchor is still bad
                    } else if ((DW3000.getDestinationID() != ID_PONG[ii])) {
                      // Message
                      DW3000.ds_sendErrorFrame();
                      curr_stage = 0; // Restart protocol for this anchor
                      waitingForResponse = false;
                      // We don't break the while (fin_de_com), we let it try again or timeout if the anchor is still bad
                    } else {
                      curr_stage = 2;
                      waitingForResponse = false;
                    }
                  } else { // rx_status != 1 or the ID is not correct
                    Serial.print("[ERROR] Receiver Error (case 1) or incorrect ID. RX_STATUS: ");
                    Serial.print(rx_status);
                    Serial.print(", DEST_ID: ");
                    Serial.println(DW3000.getDestinationID());
                    
                    DW3000.softReset();
                    delay(100);
                    DW3000.init();
                    DW3000.configureAsTX();
                    DW3000.clearSystemStatus();

                    anchor_distance[ii] = 0;
                    pot_sig[ii] = -120.0f; // Very low dBm to indicate bad quality/no signal
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1; 
                    Serial.println("[INFO] TAG DW3000 re-initialized post-receiver error (case 1).");
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
                  DW3000.clearSystemStatus(); // Clear system status after reception
                  if (rx_status == 1) { // We assume that the PONG does not change the Destination ID for the last msg
                    if (DW3000.ds_isErrorFrame()) {
                      Serial.println("[WARNING] Error frame detected (case 3)! Reverting to stage 0.");
                      curr_stage = 0;
                      waitingForResponse = false;
                      // We don't break the while (fin_de_com)
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
                    pot_sig[ii] = -120.0f; // Very low dBm to indicate bad quality/no signal
                    anchor_responded[ii] = false;
                    curr_stage = 0;
                    waitingForResponse = false;
                    fin_de_com = 1; 
                    Serial.println("[INFO] TAG DW3000 re-initialized post-receiver error (case 3).");
                  }
                }
                break;
                
              case 4: {
                ranging_time = DW3000.ds_processRTInfo(t_roundA, t_replyA, DW3000.read(0x12, 0x04), DW3000.read(0x12, 0x08), clock_offset);
                distance = DW3000.convertToCM(ranging_time);
                
                float distance_meters = distance / 100.0; 
                
                pot_sig[ii] = DW3000.getSignalStrength();

                anchor_responded[ii] = true; 
                if (distance_meters > 0) { 
                    anchor_distance[ii] = kalmanFilterDistance(distance_meters, ii); 
                } else {
                    anchor_distance[ii] = 0; 
                    pot_sig[ii] = -120.0f; 
                }
 
                // Format logs: TODO IN METERS for complete system consistency
                dataString = String(TAG_ID) + "," +
                                  String(millis()) + "," +
                                  String(ID_PONG[ii]) + "," +
                                  String(distance_meters, 4) + "," +       // Raw in meters (4 decimals)
                                  String(anchor_distance[ii], 4) + "," +   // Filtered in meters (4 decimals)
                                  String(pot_sig[ii], 2) + "," +
                                  String(anchor_responded[ii] ? 1 : 0); 
                
                // --- Publish SINGLE log line IMMEDIATELY --- 
                if (client.connected()) {
                    if (!client.publish(log_topic, dataString.c_str())) {
                       Serial.println("MQTT Publish Failed (single log line)"); 
                    }
                } else {
                    Serial.println("MQTT disconnected, cannot send log line."); 
                }
                // ----------------------------------------------
 
                // Respond with a PONG
                curr_stage = 0;
                fin_de_com = 1;
                
                // REMOVED: delay(50); // This was slowing down the measurement cycle
                break;
              }
                
              default:
                Serial.print("[ERROR] Unknown state (");
                Serial.print(curr_stage);
                Serial.println("). Returning to state 0.");
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
          // Calculate tag position using intelligent trilateration 
          
          float distances[NUM_ANCHORS];
          for (int i = 0; i < NUM_ANCHORS; i++) {
            distances[i] = anchor_distance[i]; // Already in meters
          }


          // === Intelligent selection of 3 anchors to avoid degeneration ===
          int responded_idx[NUM_ANCHORS];
          int r_count = 0;
          for (int i = 0; i < NUM_ANCHORS; i++) {
            if (anchor_responded[i]) {
              responded_idx[r_count++] = i;
            }
          }

          if (r_count >= 3) {
            // === INTELLIGENT TRILATERATION OPTION A ===
            int selected_anchors[3];
            bool selection_successful = selectOptimalAnchors(responded_idx, r_count, selected_anchors);
            
            int a0, a1, a2;
            if (selection_successful) {
              a0 = selected_anchors[0];
              a1 = selected_anchors[1]; 
              a2 = selected_anchors[2];
            } else {
              // Fallback to original method if intelligent selection fails
              Serial.println("[TRILAT-A] Fallback to basic method");
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
            
            // Basic trilateration equations
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
              
              // === SMOOTH LIMITS to avoid sudden jerks ===
              float bounded_x = x;
              float bounded_y = y;
              
              // Apply smooth limits with gradual transition
              if (x < -6.9f) {
                bounded_x = -6.9f + (x + 6.9f) * 0.1f; // Reduce extrapolation by 90%
              } else if (x > 6.8f) {
                bounded_x = 6.8f + (x - 6.8f) * 0.1f;
              }
              
              if (y < -3.5f) {
                bounded_y = -3.5f + (y + 3.5f) * 0.1f;
              } else if (y > 10.36f) {
                bounded_y = 10.36f + (y - 10.36f) * 0.1f;
              }
              
              // === APPLY REQUIRED KALMAN FILTER ===
              kalmanFilterPosition(bounded_x, bounded_y);
              
              // Update previous timestamp and position
              last_trilateration_time = millis();
              last_valid_position[0] = tagPositionX;
              last_valid_position[1] = tagPositionY;
              
              checkZones();
            } else {
              // If determinant is too small, keep last valid position
              if (millis() - last_trilateration_time < 2000) {
                tagPositionX = last_valid_position[0];
                tagPositionY = last_valid_position[1];
              }
            }
          }
        }
        
        for (int i = 0; i < NUM_ANCHORS; i++) {
          Serial.print("Anchor ");
          Serial.print(ID_PONG[i]);
          Serial.print(" ");
          Serial.print(anchor_distance[i], 3); 
          Serial.print(" m, Power = ");
          Serial.print(pot_sig[i]);
          Serial.println("dBm");
        }
        
        publishStatus();
        
        broadcastWebSocket();

        fin_de_com = 0;
    }
  } 

  broadcastWebSocket();
} 
