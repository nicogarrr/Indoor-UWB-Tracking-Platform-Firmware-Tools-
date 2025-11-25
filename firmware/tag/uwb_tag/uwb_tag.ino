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


const uint32_t WS_SEND_INTERVAL_MS = 20; // 1000/20 = 50 fps - WebSocket optimized (keep!)

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
const char* log_topic = "uwb/tag/logs";       
char status_topic[30];                      
WiFiClient espClient;
PubSubClient client(espClient);

// ===== Configuration for WiFi Logging =====
const char* logServerIp = "172.20.10.5"; 
const int logServerPort = 5000;             

// ===== TDMA Configuration (INDOOR) =====
// *** Optimized for SPORTS: 20 Hz (50ms cycle) - STABLE SWEET SPOT ***
const unsigned long TDMA_CYCLE_MS = 50;  // Target: 20 Hz
const unsigned long TDMA_SLOT_DURATION_MS = 50;  // Full cycle for this tag

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
#define NUM_ANCHORS 6 
int ID_PONG[NUM_ANCHORS] = {1, 2, 3, 4, 5, 6}; 
float distance_buffer[NUM_ANCHORS][NUM_MEASUREMENTS] = { {0} };
int buffer_index[NUM_ANCHORS] = {0};
float anchor_distance[NUM_ANCHORS] = {0};
float anchor_avg[NUM_ANCHORS] = {0};
float pot_sig[NUM_ANCHORS] = {0};
static int fin_de_com = 0;
bool anchor_responded[NUM_ANCHORS] = {false}; 

// ===== DYNAMIC ANCHOR SKIPPING =====
bool anchor_is_active[NUM_ANCHORS] = {true, true, true, true, true, true};
int anchor_fail_count[NUM_ANCHORS] = {0};
unsigned long anchor_inactive_ts[NUM_ANCHORS] = {0};
const int MAX_FAILURES = 2;
const unsigned long RETRY_INTERVAL = 2000; // 2 seconds

// Variables for timeout 
unsigned long timeoutStart = 0;
bool waitingForResponse = false;
const unsigned long RESPONSE_TIMEOUT = 15; // Aggressive 15ms timeout for 20Hz

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
float kalman_z = 0.0;
float kalman_p_x = 1.0;
float kalman_p_y = 1.0;
float kalman_p_z = 1.0;
float kalman_q = 0.01; 
float kalman_r = 0.05; 

// Variables for tag position
float tagPositionX = 0.0;
float tagPositionY = 0.0;
float tagPositionZ = 0.0;

// Variables for WLSQ
unsigned long last_wlsq_time = 0;
float last_valid_position_3d[3] = {0.0, 0.0, 0.0}; 


// ===== GLOBAL ANCHOR POSITIONS (anchors 1-6) =====
// Coordinates: X, Y, Z
const float anchorsPos[NUM_ANCHORS][3] = {
  {0.0,  0.0,  1.8},   // Anchor 1 (Left Bottom Corner)
  {0.0,  7.35, 1.0},   // Anchor 2 (Left Top Corner)
  {5.3,  7.35, 1.8},   // Anchor 3 (Top Edge Midpoint)
  {10.6, 7.35, 1.0},   // Anchor 4 (Right Top Corner)
  {10.6, 0.0,  1.8},   // Anchor 5 (Right Bottom Corner)
  {5.3,  0.0,  1.0}    // Anchor 6 (Bottom Edge Midpoint)
};

// ===== HELPER FUNCTIONS =====
int getAnchorIndex(int anchor_id) {
  if (anchor_id >= 1 && anchor_id <= 6) {
    return anchor_id - 1;
  }
  return -1; 
}

int getAnchorNumber(int array_index) {
  return array_index + 1;
}

// ===== WLSQ ALGORITHM =====

// Helper: Invert 4x4 Matrix (Gauss-Jordan)
bool invertMatrix4x4(float A[4][4], float A_inv[4][4]) {
  // Initialize A_inv as identity
  for (int i = 0; i < 4; i++) {
    for (int j = 0; j < 4; j++) {
      A_inv[i][j] = (i == j) ? 1.0f : 0.0f;
    }
  }

  // Gaussian elimination
  for (int i = 0; i < 4; i++) {
    // Find pivot
    float pivot = A[i][i];
    if (fabs(pivot) < 1e-6) return false; // Singular

    // Normalize row i
    for (int j = 0; j < 4; j++) {
      A[i][j] /= pivot;
      A_inv[i][j] /= pivot;
    }

    // Eliminate other rows
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

// Calculate Position using Weighted Least Squares (3D)
bool calculateWLSQPosition(int* available_anchors, int count, float* x, float* y, float* z) {
  if (count < 4) return false; // Need at least 4 anchors for 3D + R^2

  // Matrices
  // H: [count x 4]
  // W: [count x count] (diagonal)
  // Y: [count x 1]
  // Solution theta = (H^T * W * H)^-1 * H^T * W * Y

  // We will compute (H^T * W * H) [4x4] and (H^T * W * Y) [4x1] directly to save memory
  
  float H_T_W_H[4][4] = {0};
  float H_T_W_Y[4] = {0};

  for (int i = 0; i < count; i++) {
    int anchor_idx = available_anchors[i];
    
    float ax = anchorsPos[anchor_idx][0];
    float ay = anchorsPos[anchor_idx][1];
    float az = anchorsPos[anchor_idx][2];
    float d = anchor_distance[anchor_idx];
    float rssi = pot_sig[anchor_idx];

    // Weight based on RSSI (simple model: stronger signal = higher weight)
    // Map -90dBm to 0.1, -70dBm to 1.0
    float weight = pow(10.0f, (rssi + 90.0f) / 20.0f); 
    
    // IMPROVEMENT: Weight by inverse distance squared
    // Measurements at short distance are much more reliable (Line of Sight)
    // and less prone to multipath error.
    // We add a small epsilon (0.1) to avoid division by zero or excessive weight.
    float dist_weight = 1.0f / (d * d + 0.1f); 
    weight *= dist_weight;

    if (weight < 0.001f) weight = 0.001f;

    // Row of H: [-2x, -2y, -2z, 1]
    float h_row[4] = { -2.0f * ax, -2.0f * ay, -2.0f * az, 1.0f };
    
    // Element of Y: d^2 - (x^2 + y^2 + z^2)
    float k_i = ax*ax + ay*ay + az*az;
    float y_val = d*d - k_i;

    // Accumulate H^T * W * H
    for (int r = 0; r < 4; r++) {
      for (int c = 0; c < 4; c++) {
        H_T_W_H[r][c] += h_row[r] * weight * h_row[c];
      }
    }

    // Accumulate H^T * W * Y
    for (int r = 0; r < 4; r++) {
      H_T_W_Y[r] += h_row[r] * weight * y_val;
    }
  }

  // Invert (H^T * W * H)
  float H_T_W_H_inv[4][4];
  if (!invertMatrix4x4(H_T_W_H, H_T_W_H_inv)) {
    return false; // Matrix singular
  }

  // Calculate theta = H_T_W_H_inv * H_T_W_Y
  float theta[4] = {0};
  for (int r = 0; r < 4; r++) {
    for (int c = 0; c < 4; c++) {
      theta[r] += H_T_W_H_inv[r][c] * H_T_W_Y[c];
    }
  }

  *x = theta[0];
  *y = theta[1];
  *z = theta[2];
  // theta[3] is R^2, we can use it for validation if needed (x^2+y^2+z^2 ~ theta[3])

  return true;
}



// Variables for MQTT and State 
unsigned long lastMqttReconnectAttempt = 0;
unsigned long lastStatusUpdate = 0;
const long statusUpdateInterval = 40; // Sync with ~20Hz (50ms) - faster to avoid buffer buildup
String last_anchor_id = "N/A"; 

// ===== SYSTEM BUFFERING =====
struct StabilizedBuffer {
  float position_x_buffer[8];
  float position_y_buffer[8];
  unsigned long timestamp_buffer[8];
  int buffer_head = 0;
  int buffer_count = 0;
  unsigned long last_output_time = 0;
  const unsigned long OUTPUT_INTERVAL = 45; // Sync with ~20Hz
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

    // Ultra-smooth animation at 60 fps using requestAnimationFrame
    function animateTag() {
      // Adaptive interpolation - faster when far, slower when close
      const dx = tagTarget.x - tagPosition.x;
      const dy = tagTarget.y - tagPosition.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      // Smooth lerp with adaptive speed (0.08-0.25 range)
      const baseLerp = 0.12;
      const adaptiveLerp = Math.min(0.25, baseLerp + distance * 0.002);
      
      tagPosition.x += dx * adaptiveLerp;
      tagPosition.y += dy * adaptiveLerp;

      if (vizElements.tagPoint) {
        // Use transform for hardware acceleration
        vizElements.tagPoint.style.transform = `translate(${tagPosition.x - 7}px, ${tagPosition.y - 7}px)`;
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
        // Physical space configuration INDOOR (updated to 10.60 x 7.35)
        const minX = -0.5;
        const maxX = 11.1; // 10.6 + 0.5 padding
        const minY = -0.5;
        const maxY = 7.85; // 7.35 + 0.5 padding

        const areaWidth  = maxX - minX; 
        const areaHeight = maxY - minY;
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

        const minX = -0.5;
        const maxX = 11.1; // Updated for 10.6m width + padding
        const minY = -0.5;
        const maxY = 7.85;

        const areaWidth  = maxX - minX; 
        const areaHeight = maxY - minY;
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

        // Rectangle vertices in meters (in order) for 10.60 x 7.35
        const hexVertices = [
          { x: 0.0,  y: 0.0 },
          { x: 0.0,  y: 7.35 },
          { x: 10.6, y: 7.35 },
          { x: 10.6, y: 0.0 }
        ];

        // Anchor positions with IDs (updated to new layout for 10.60 x 7.35)
        const anchorsPosMetros = [
          { id: 1, x: 0.0,  y: 0.0  }, // Left Bottom Corner
          { id: 2, x: 0.0,  y: 7.35 }, // Left Top Corner
          { id: 3, x: 5.3,  y: 7.35 }, // Top Edge Midpoint
          { id: 4, x: 10.6, y: 7.35 }, // Right Top Corner
          { id: 5, x: 10.6, y: 0.0  }, // Right Bottom Corner
          { id: 6, x: 5.3,  y: 0.0  }  // Bottom Edge Midpoint
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
        tagPoint.style.left = '0px';
        tagPoint.style.top = '0px';
        tagPoint.style.transform = `translate(${tagPosition.x - 7}px, ${tagPosition.y - 7}px)`; 
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

        // Tag position updates are handled by requestAnimationFrame for ultra-smooth animation
        // No need to update here as animateTag() handles all position updates at 60fps
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

// Kalman filter for 3D position with Adaptive Q
void kalmanFilterPosition3D(float measured_x, float measured_y, float measured_z) {
  // Calculate distance moved (innovation) to adjust Q
  float dist_moved = sqrt(pow(measured_x - kalman_x, 2) + 
                          pow(measured_y - kalman_y, 2) + 
                          pow(measured_z - kalman_z, 2));
                          
  // Adaptive Q: 
  // If moving fast (dist > 0.5m), increase Q to be more reactive
  // If static (dist < 0.1m), decrease Q to be smoother
  // Base Q = 0.01
  
  float adaptive_q = 0.01;
  
  if (dist_moved > 0.5) {
      adaptive_q = 0.1; // Fast movement -> Trust measurement more
  } else if (dist_moved > 0.2) {
      adaptive_q = 0.05; // Medium movement
  } else {
      adaptive_q = 0.005; // Static -> Trust model more (smooth)
  }
  
  kalman_p_x = kalman_p_x + adaptive_q;
  kalman_p_y = kalman_p_y + adaptive_q;
  kalman_p_z = kalman_p_z + adaptive_q;
  
  float k_x = kalman_p_x / (kalman_p_x + kalman_r);
  float k_y = kalman_p_y / (kalman_p_y + kalman_r);
  float k_z = kalman_p_z / (kalman_p_z + kalman_r);
  
  kalman_x = kalman_x + k_x * (measured_x - kalman_x);
  kalman_y = kalman_y + k_y * (measured_y - kalman_y);
  kalman_z = kalman_z + k_z * (measured_z - kalman_z);
  
  kalman_p_x = (1 - k_x) * kalman_p_x;
  kalman_p_y = (1 - k_y) * kalman_p_y;
  kalman_p_z = (1 - k_z) * kalman_p_z;
  
  tagPositionX = kalman_x;
  tagPositionY = kalman_y;
  tagPositionZ = kalman_z;
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
      // Set maximum WiFi power for best performance
      WiFi.setTxPower(WIFI_POWER_19_5dBm);
      Serial.println("WiFi power set to maximum (19.5dBm)");
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
                       JSON_OBJECT_SIZE(3) + 
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
  positionObject["z"] = isnan(tagPositionZ) || isinf(tagPositionZ) ? 0.0 : tagPositionZ;

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


// Check if the tag is inside any defined zone - DISABLED
void checkZones() {
  /*
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
  */
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
   // OPTIMIZED FOR 20Hz - 50ms interval
   static unsigned long lastPublish = 0;
   unsigned long currentTime = millis();
   
   // Strict timing control - EXACTLY every 45ms (allow slight overlap for 50ms cycle)
   if (currentTime - lastPublish < 45) {
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
   float safe_z = (isnan(tagPositionZ) || isinf(tagPositionZ)) ? 0.0 : tagPositionZ;
   position["x"] = safe_x;
   position["y"] = safe_y;
   position["z"] = safe_z;

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
     // Silent success - reduced logging for performance
   } else {
     Serial.printf("[MQTT] Error sending position at timestamp %lu\n", currentTime);
   }
}

void broadcastWebSocket(){
  static uint32_t lastWs=0;
  uint32_t now = millis();
  if(now - lastWs < WS_SEND_INTERVAL_MS) return; // limit to 50 fps - ultra smooth
  
  // Only generate JSON when we're actually going to send it
  String json = getDataJson();
  if (ws.count() > 0) { // Only send if there are connected clients
    ws.textAll(json);
  }
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
  Serial.println("\n=== UWB TAG with WiFi, Web Server, and MQTT ===");
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
  SPI.setFrequency(8000000); // Set SPI to 8MHz for stable communication (20MHz can be unstable)
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
          // ===== DYNAMIC SKIPPING: PRE-CHECK =====
          if (!anchor_is_active[ii]) {
             if (millis() - anchor_inactive_ts[ii] < RETRY_INTERVAL) {
                 // Still in penalty box, skip
                 anchor_responded[ii] = false;
                 anchor_distance[ii] = 0; 
                 pot_sig[ii] = -120.0f;
                 continue; 
             } 
             // Else: Time to retry (Ping) -> Proceed to ranging
          }

          DW3000.setDestinationID(ID_PONG[ii]);
          fin_de_com = 0;
          
          while (fin_de_com == 0) {
            if (waitingForResponse && ((millis() - timeoutStart) >= RESPONSE_TIMEOUT)) {
              Serial.print("Timeout REINFORCED for anchor ID: "); 
              Serial.println(ID_PONG[ii]);

              // ===== DYNAMIC SKIPPING: FAILURE (Timeout) =====
              anchor_fail_count[ii]++;
              if (anchor_fail_count[ii] >= MAX_FAILURES) {
                  anchor_is_active[ii] = false;
                  anchor_inactive_ts[ii] = millis();
                  anchor_fail_count[ii] = 0; 
                  Serial.print("[SKIP] Anchor ");
                  Serial.print(ID_PONG[ii]);
                  Serial.println(" marked INACTIVE (Timeout)");
              } else if (!anchor_is_active[ii]) {
                  // Retry failed
                  anchor_inactive_ts[ii] = millis(); 
              }

              DW3000.softReset();
              delay(1); // Reduced to 1ms for 20Hz target
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
                    
                    // ===== DYNAMIC SKIPPING: FAILURE (RX Error) =====
                    anchor_fail_count[ii]++;
                    if (anchor_fail_count[ii] >= MAX_FAILURES) {
                        anchor_is_active[ii] = false;
                        anchor_inactive_ts[ii] = millis();
                        anchor_fail_count[ii] = 0; 
                    } else if (!anchor_is_active[ii]) {
                        anchor_inactive_ts[ii] = millis(); 
                    }

                    DW3000.softReset();
                    delay(1); // Reduced to 1ms
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

                    // ===== DYNAMIC SKIPPING: FAILURE (RX Error) =====
                    anchor_fail_count[ii]++;
                    if (anchor_fail_count[ii] >= MAX_FAILURES) {
                        anchor_is_active[ii] = false;
                        anchor_inactive_ts[ii] = millis();
                        anchor_fail_count[ii] = 0; 
                    } else if (!anchor_is_active[ii]) {
                        anchor_inactive_ts[ii] = millis(); 
                    }

                    DW3000.softReset();
                    delay(1); // Reduced to 1ms
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
                
                // ===== DYNAMIC SKIPPING: SUCCESS =====
                anchor_is_active[ii] = true;
                anchor_fail_count[ii] = 0;

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
                /* DISABLED FOR PERFORMANCE - Blocking MQTT here causes lag
                if (client.connected()) {
                    if (!client.publish(log_topic, dataString.c_str())) {
                       Serial.println("MQTT Publish Failed (single log line)"); 
                    }
                } else {
                    Serial.println("MQTT disconnected, cannot send log line."); 
                }
                */
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

        // Only calculate position if enough anchors responded
        if (responding_anchors >= 4) { 
          // Collect available anchors
          int responded_idx[NUM_ANCHORS];
          int r_count = 0;
          for (int i = 0; i < NUM_ANCHORS; i++) {
            if (anchor_responded[i]) {
              responded_idx[r_count++] = i;
            }
          }

          float x, y, z;
          if (calculateWLSQPosition(responded_idx, r_count, &x, &y, &z)) {
              // === SMOOTH LIMITS to avoid sudden jerks ===
              float bounded_x = x;
              float bounded_y = y;
              float bounded_z = z;

              // Apply smooth limits with gradual transition (0.0 to 10.6)
              if (x < 0.0f) {
                bounded_x = 0.0f + x * 0.1f; 
              } else if (x > 10.6f) {
                bounded_x = 10.6f + (x - 10.6f) * 0.1f;
              }
              
              // Apply smooth limits with gradual transition (0.0 to 7.35)
              if (y < 0.0f) {
                bounded_y = 0.0f + y * 0.1f;
              } else if (y > 7.35f) {
                bounded_y = 7.35f + (y - 7.35f) * 0.1f;
              }

              // Apply smooth limits for Z (0.0 to 3.0m approx)
              if (z < 0.0f) {
                bounded_z = 0.0f + z * 0.1f;
              } else if (z > 3.0f) {
                bounded_z = 3.0f + (z - 3.0f) * 0.1f;
              }
              

              // === APPLY REQUIRED KALMAN FILTER ===
              kalmanFilterPosition3D(bounded_x, bounded_y, bounded_z);
              
              // FORCE Z STABILITY FOR FUTSAL (Flat floor)
              // If calculated Z is crazy (>2.5m or <0m), force it to waist height (1.0m)
              // This prevents Z noise from ruining the visualization
              if (tagPositionZ < 0.0 || tagPositionZ > 2.5) {
                  tagPositionZ = 1.0; 
                  kalman_z = 1.0; // Update Kalman state to maintain consistency
              }
              last_wlsq_time = millis();
              last_valid_position_3d[0] = tagPositionX;
              last_valid_position_3d[1] = tagPositionY;
              last_valid_position_3d[2] = tagPositionZ;
              

              

              // checkZones(); // Disabled for now
          } else {
             // WLSQ Failed (Singular matrix?)
             Serial.println("[WLSQ] Matrix inversion failed");
          }
        } else {
           // Not enough anchors
           if (millis() - last_wlsq_time < 2000) {
             // Keep last known position for 2 seconds
             tagPositionX = last_valid_position_3d[0];
             tagPositionY = last_valid_position_3d[1];
             tagPositionZ = last_valid_position_3d[2];
           }
        }
        
        /* DISABLED FOR PERFORMANCE - Serial printing takes ~20ms (blocking)
        for (int i = 0; i < NUM_ANCHORS; i++) {
          Serial.print("Anchor ");
          Serial.print(ID_PONG[i]);
          Serial.print(" ");
          Serial.print(anchor_distance[i], 3); 
          Serial.print(" m, Power = ");
          Serial.print(pot_sig[i]);
          Serial.println("dBm");
        }
        */
        
        publishStatus();

        fin_de_com = 0;
    }
  } 

  // Single WebSocket broadcast - smooth and efficient
  broadcastWebSocket();
}