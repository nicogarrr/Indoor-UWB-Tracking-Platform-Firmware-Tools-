#include "DW3000.h"
#include <Preferences.h>

// ===== CONFIGURATION OF ANCHOR =====
// ID se carga desde NVS (Non-Volatile Storage) o envuelto en COMPILE-TIME
// Si no existe en NVS, usa DEFAULT_ANCHOR_ID definido en compilación

// Para compilar cada anchor con ID diferente:
// Opción A: Define en Arduino IDE: Tools > Board Settings > Compiler flags
//           -DDEFAULT_ANCHOR_ID=1
// Opción B: Crea config_anchor.h con #define ANCHOR_ID 1
// Opción C: Usa NVS (persistente en memoria, configurable por OTA)

#ifndef DEFAULT_ANCHOR_ID
  #define DEFAULT_ANCHOR_ID 1  // Fallback por defecto
#endif

static int ID_PONG = DEFAULT_ANCHOR_ID; // Se carga desde NVS o usa DEFAULT

// ===== COMMUNICATION VARIABLES =====
static int frame_buffer = 0;
static int rx_status;
static int tx_status;

// States of the double-sided ranging protocol
static int curr_stage = 0;
static int t_roundB = 0;
static int t_replyB = 0;
static long long rx = 0;
static long long tx = 0;

// ===== IMPROVED ACTIVITY MANAGEMENT =====
unsigned long lastSuccessfulActivityTime = 0;
unsigned long lastDebugOutput = 0;
const unsigned long ANCHOR_RESET_TIMEOUT_MS = 30000; // 30 seconds
const unsigned long DEBUG_INTERVAL_MS = 10000; // Debug every 10 seconds

// ===== PERFORMANCE STATISTICS =====
struct AnchorStats {
  unsigned long total_requests = 0;
  unsigned long successful_responses = 0;
  unsigned long error_frames = 0;
  unsigned long timeouts = 0;
  unsigned long uptime_start = 0;
} stats;

// ===== OPTIMIZED CONFIGURATIONS =====
const unsigned long RX_TIMEOUT_MS = 100; // Timeout for reception
const unsigned long RESPONSE_DELAY_US = 50; // Minimum delay between responses

void loadAnchorID() {
  // Intentar cargar ID desde NVS (persistente)
  Preferences preferences;
  preferences.begin("uwb", true); // readonly
  
  int stored_id = preferences.getInt("anchor_id", -1);
  
  if (stored_id != -1 && stored_id >= 1 && stored_id <= 5) {
    ID_PONG = stored_id;
    Serial.printf("[CONFIG] Loaded anchor ID from NVS: %d\n", ID_PONG);
  } else {
    ID_PONG = DEFAULT_ANCHOR_ID;
    Serial.printf("[CONFIG] Using default anchor ID: %d\n", ID_PONG);
  }
  
  preferences.end();
}

void saveAnchorID(int id) {
  // Guardar ID en NVS (para configuración dinámica)
  if (id < 1 || id > 5) {
    Serial.printf("[ERROR] Invalid anchor ID: %d (must be 1-5)\n", id);
    return;
  }
  
  Preferences preferences;
  preferences.begin("uwb", false); // writable
  preferences.putInt("anchor_id", id);
  preferences.end();
  
  Serial.printf("[CONFIG] Saved anchor ID to NVS: %d\n", id);
  ID_PONG = id;
}

void setup() {
  Serial.begin(115200); // Standard speed for stability
  
  // Initialize statistics
  stats.uptime_start = millis();
  
  // Cargar ID del anchor desde NVS o usar DEFAULT
  loadAnchorID();
  
  initializeDW3000();
  
  Serial.printf("> ANCHOR %d OPTIMIZED - Double-sided PONG v2.0 <\n", ID_PONG);
  Serial.printf("[INFO] Setup completed. Ready for ranging.\n");
  Serial.printf("[INFO] To change anchor ID, call saveAnchorID(new_id)\n");
  
  lastSuccessfulActivityTime = millis();
  lastDebugOutput = millis();
}

void initializeDW3000() {
  DW3000.begin();
  DW3000.hardReset();
  delay(100); // Reduced for faster startup
  
  // Verification with retries
  int retries = 0;
  while (!DW3000.checkForIDLE() && retries < 5) {
    Serial.printf("[WARNING] IDLE check failed, retry %d/5\n", ++retries);
    delay(50);
  }
  
  if (retries >= 5) {
    Serial.println("[ERROR] DW3000 initialization failed! Restarting...");
    ESP.restart();
  }
  
  DW3000.softReset();
  delay(100);
  
  if (!DW3000.checkForIDLE()) {
    Serial.println("[ERROR] DW3000 soft reset failed! Restarting...");
    ESP.restart();
  }
  
  DW3000.init();
  DW3000.setupGPIO();
  DW3000.configureAsTX();
  DW3000.clearSystemStatus();
  DW3000.standardRX();
  
  Serial.println("[INFO] DW3000 initialized correctly");
}

void loop() {
  // Improved activity management and auto-restart
  manageActivity();
  
  // Improved periodic debug
  if (millis() - lastDebugOutput > DEBUG_INTERVAL_MS) {
    printPerformanceStats();
    lastDebugOutput = millis();
  }
  
  // Main state machine
  switch (curr_stage) {
    case 0:
      handleStage0_AwaitRanging();
      break;
      
    case 1:
      handleStage1_SendResponse();
      break;
      
    case 2:
      handleStage2_AwaitSecondResponse();
      break;
      
    case 3:
      handleStage3_SendInfo();
      break;
      
    case 4:
      handleStage4_Cleanup();
      break;
      
    default:
      handleUnknownStage();
      break;
  }
}

void manageActivity() {
  unsigned long currentTime = millis();
  
  // Auto-restart by inactivity
  if (currentTime - lastSuccessfulActivityTime > ANCHOR_RESET_TIMEOUT_MS) {
    Serial.println("[AUTO-RESET] Inactivity detected. Restarting anchor...");
    printPerformanceStats();
    delay(100);
    ESP.restart();
  }
}

void handleStage0_AwaitRanging() {
  t_roundB = 0;
  t_replyB = 0;
  
  if (rx_status = DW3000.receivedFrameSucc()) {
    DW3000.clearSystemStatus();
    stats.total_requests++;
    
    if (rx_status == 1) {
      if (DW3000.ds_isErrorFrame()) {
        Serial.println("[WARNING] Error frame detected, returning to stage 0");
        stats.error_frames++;
        resetToStage0();
        return;
      }
      
      if (DW3000.getDestinationID() != ID_PONG) {
        // Not for this anchor
        DW3000.standardRX();
        return;
      }
      
      if (DW3000.ds_getStage() != 1) {
        Serial.printf("[WARNING] Incorrect stage received: %d\n", DW3000.ds_getStage());
        DW3000.ds_sendErrorFrame();
        stats.error_frames++;
        resetToStage0();
        return;
      }
      
      // Everything is correct, advance to stage 1
      curr_stage = 1;
      
    } else {
      Serial.println("[ERROR] Error in stage 0");
      stats.timeouts++;
      DW3000.clearSystemStatus();
      resetToStage0();
    }
  }
}

void handleStage1_SendResponse() {
  DW3000.setDestinationID(ID_PONG);
  DW3000.ds_sendFrame(2);
  
  rx = DW3000.readRXTimestamp();
  tx = DW3000.readTXTimestamp();
  t_replyB = tx - rx;
  
  curr_stage = 2;
}

void handleStage2_AwaitSecondResponse() {
  if (rx_status = DW3000.receivedFrameSucc()) {
    DW3000.clearSystemStatus();
    
    if (rx_status == 1) {
      if (DW3000.ds_isErrorFrame()) {
        Serial.println("[WARNING] Error frame in stage 2");
        stats.error_frames++;
        resetToStage0();
        return;
      }
      
      if (DW3000.getDestinationID() != ID_PONG) {
        Serial.println("[DEBUG] Destination different in stage 2, cleaning");
        curr_stage = 4; // Clean and return to stage 0
        return;
      }
      
      if (DW3000.ds_getStage() != 3) {
        Serial.printf("[WARNING] Incorrect stage in stage 2: %d\n", DW3000.ds_getStage());
        DW3000.ds_sendErrorFrame();
        stats.error_frames++;
        resetToStage0();
        return;
      }
      
      curr_stage = 3;
      
    } else {
      Serial.println("[ERROR] Error in stage 2");
      stats.timeouts++;
      resetToStage0();
    }
  }
}

void handleStage3_SendInfo() {
  rx = DW3000.readRXTimestamp();
  t_roundB = rx - tx;
  
  // Send timing information
  DW3000.ds_sendRTInfo(t_roundB, t_replyB);
  
  // Transaction completed successfully
  stats.successful_responses++;
  lastSuccessfulActivityTime = millis();
  
  resetToStage0();
}

void handleStage4_Cleanup() {
  // Quick cleanup and return to stage 0
  resetToStage0();
}

void handleUnknownStage() {
  Serial.printf("[ERROR] Unknown stage (%d), restarting\n", curr_stage);
  resetToStage0();
}

void resetToStage0() {
  curr_stage = 0;
  DW3000.standardRX();
  
  // Small delay to stabilize
  delayMicroseconds(RESPONSE_DELAY_US);
}

void printPerformanceStats() {
  unsigned long uptime = millis() - stats.uptime_start;
  float success_rate = stats.total_requests > 0 ? 
    (float)stats.successful_responses / stats.total_requests * 100.0 : 0.0;
  
  Serial.printf("\n=== ANCHOR %d STATISTICS ===\n", ID_PONG);
  Serial.printf("Success rate: %.1f%%\n", success_rate);
  Serial.printf("Frames with error: %lu\n", stats.error_frames);
  Serial.printf("Timeouts: %lu\n", stats.timeouts);
  Serial.printf("Last activity: %lu ms ago\n", millis() - lastSuccessfulActivityTime);
  Serial.printf("Uptime: %lu ms\n", uptime);
  Serial.println("================================\n");
}

