#include "DW3000.h"
#include <esp_task_wdt.h> // MEJORA TFG: Watchdog para robustez
#define ID_PONG 30  // ID específico para esta ancla
#include "../common/config.h" // TFG v2.1: Configuración centralizada

// MEJORA 10: Librerías para métricas por red
#if ENABLE_MQTT_METRICS
#include <WiFi.h>
#include <PubSubClient.h>
#endif
#if ENABLE_UDP_METRICS
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#endif

// MEJORA 13: Librería para persistencia NVS
#if ENABLE_NVS_PERSISTENCE
#include <Preferences.h>
#endif

// ===== INFORMACIÓN DE FIRMWARE COHERENTE CON TAG =====
#define ANCHOR_FW_VERSION "v2.1-PRODUCTION-TFG-2024"
#define BUILD_DATE __DATE__ " " __TIME__

// TFG v2.1-PRODUCTION: Control de debug (coherente con tag)
#define DEBUG_MODE 0

#if DEBUG_MODE
  #define DEBUG_PRINT(x) Serial.print(x)
  #define DEBUG_PRINTLN(x) Serial.println(x)
#else
  #define DEBUG_PRINT(x)
  #define DEBUG_PRINTLN(x)
#endif

// ===== MEJORA 8: VALIDACIÓN DE ID DE ANCLA =====
bool isAnchorIDValid(int id) {
  return (id == 10 || id == 20 || id == 30 || id == 40 || id == 50);
}

// ===== MEJORA 12: FILTROS ANTI-FANTASMAS =====
#if ENABLE_RANGE_FILTER
bool isSignalValid() {
  // Verificar RSSI
  float rssi = DW3000.getRSSI();
  if (rssi < MIN_RSSI_THRESHOLD) {
    DEBUG_PRINT("[FILTER] RSSI débil: ");
    DEBUG_PRINTLN(rssi);
    return false;
  }
  
  // Verificar rango estimado basado en potencia de señal
  // Aproximación simple: distancia correlaciona con RSSI
  float estimatedRange = abs(rssi + 30) * 2.0; // Fórmula simplificada
  
  if (estimatedRange > MAX_RANGE_THRESHOLD_M || estimatedRange < MIN_RANGE_THRESHOLD_M) {
    DEBUG_PRINT("[FILTER] Rango anómalo estimado: ");
    DEBUG_PRINT(estimatedRange);
    DEBUG_PRINTLN("m");
    return false;
  }
  
  return true;
}
#endif

// ===== MEJORA 4: ESTADO TIPADO =====
enum class Stage {
  Await = 0,      // Esperar solicitud de ranging
  SendResp = 1,   // Enviar respuesta inicial
  AwaitSecond = 2,// Esperar segunda respuesta
  SendFinal = 3,  // Enviar información final
  Cleanup = 4     // Estado de limpieza
};

// ===== VARIABLES DE ESTADO OPTIMIZADAS =====
static int rx_status;
static Stage curr_stage = Stage::Await;  // MEJORA 4: Uso de enum tipado
static int t_roundB = 0;
static int t_replyB = 0;
static long long rx = 0;
static long long tx = 0;

// ===== SISTEMA DE AUTO-REINICIO ROBUSTO =====
unsigned long lastSuccessfulActivityTime = 0;
// MEJORA 2: Timeouts ahora definidos en config.h (ANCHOR_RESET_TIMEOUT_MS, WATCHDOG_TIMEOUT_MS)

// ===== MEJORA 10: CLIENTES DE RED PARA MÉTRICAS =====
#if ENABLE_MQTT_METRICS
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
#endif
#if ENABLE_UDP_METRICS
WiFiUDP udpClient;
#endif

// ===== MEJORA 13: CLIENTE NVS PARA PERSISTENCIA =====
#if ENABLE_NVS_PERSISTENCE
Preferences preferences;
unsigned long lastNVSSave = 0;
#endif

// ===== MÉTRICAS DE RENDIMIENTO TFG =====
struct AnchorMetrics {
  unsigned long totalTransactions = 0;
  unsigned long successfulTransactions = 0;
  unsigned long errorCount = 0;
  unsigned long timeoutCount = 0;
  unsigned long malformedFrames = 0;
  unsigned long wrongDestination = 0;
  unsigned long filteredSignals = 0; // MEJORA 12: Contador de señales filtradas
  unsigned long lastStatsReport = 0;
  unsigned long initTime = 0;
  float successRate = 0.0;
  float errorRate = 0.0;
} metrics;

// MEJORA 2: STATS_REPORT_INTERVAL ahora definido en config.h

// ===== MEJORA 9: RATE-LIMITING DE LOGS =====
struct ErrorLogState {
  unsigned long lastLogTime[7] = {0}; // Array para cada tipo de error
  unsigned long suppressedCount[7] = {0};
} logState;

// ===== GESTIÓN DE ERRORES AVANZADA =====
enum ErrorType {
  ERROR_NONE = 0,
  ERROR_RX_TIMEOUT,
  ERROR_MALFORMED_FRAME,
  ERROR_WRONG_DESTINATION,
  ERROR_WRONG_STAGE,
  ERROR_DW3000_COMM,
  ERROR_SYSTEM_RESET
};

// ===== MEJORA 11: BEACON ANTES DE RESET =====
void sendResetBeacon(const char* reason) {
  #if ENABLE_RESET_BEACON
  Serial.print("[RESET_BEACON] Reiniciando por: ");
  Serial.println(reason);
  
  #if ENABLE_MQTT_METRICS
  if (mqttClient.connected()) {
    String topic = "uwb/anchor/" + String(ID_PONG) + "/status";
    String payload = "{\"event\":\"ANCHOR_RESET\",\"reason\":\"" + String(reason) + "\",\"uptime\":" + String((millis() - metrics.initTime) / 1000) + "}";
    mqttClient.publish(topic.c_str(), payload.c_str(), true); // retained message
    mqttClient.loop();
    delay(100); // Dar tiempo para envío
  }
  #endif
  
  #if ENABLE_UDP_METRICS
  if (WiFi.status() == WL_CONNECTED) {
    udpClient.beginPacket(LOG_SERVER_IP, UDP_METRICS_PORT);
    String message = "ANCHOR_RESET:" + String(ID_PONG) + ":" + String(reason) + ":" + String((millis() - metrics.initTime) / 1000);
    udpClient.print(message);
    udpClient.endPacket();
    delay(50);
  }
  #endif
  
  // Beacon por Serial siempre
  Serial.println("ANCHOR_RESET_BEACON_SENT");
  delay(100);
  #endif
}

// ===== MEJORA 13: FUNCIONES DE PERSISTENCIA NVS =====
#if ENABLE_NVS_PERSISTENCE
void loadMetricsFromNVS() {
  if (preferences.begin(NVS_NAMESPACE, false)) {
    metrics.totalTransactions = preferences.getULong("totalTx", 0);
    metrics.successfulTransactions = preferences.getULong("successTx", 0);
    metrics.errorCount = preferences.getULong("errors", 0);
    metrics.timeoutCount = preferences.getULong("timeouts", 0);
    metrics.malformedFrames = preferences.getULong("malformed", 0);
    metrics.wrongDestination = preferences.getULong("wrongDest", 0);
    metrics.filteredSignals = preferences.getULong("filtered", 0);
    
    preferences.end();
    
    Serial.println("[NVS] Métricas cargadas desde memoria persistente");
    Serial.print("Total transacciones previas: ");
    Serial.println(metrics.totalTransactions);
  }
}

void saveMetricsToNVS() {
  if (preferences.begin(NVS_NAMESPACE, false)) {
    preferences.putULong("totalTx", metrics.totalTransactions);
    preferences.putULong("successTx", metrics.successfulTransactions);
    preferences.putULong("errors", metrics.errorCount);
    preferences.putULong("timeouts", metrics.timeoutCount);
    preferences.putULong("malformed", metrics.malformedFrames);
    preferences.putULong("wrongDest", metrics.wrongDestination);
    preferences.putULong("filtered", metrics.filteredSignals);
    preferences.putULong("lastSave", millis());
    
    preferences.end();
    
    DEBUG_PRINTLN("[NVS] Métricas guardadas");
    lastNVSSave = millis();
  }
}
#endif

void logError(ErrorType error, const char* details = "") {
  metrics.errorCount++;
  
  // MEJORA 9: Rate-limiting de logs
  unsigned long currentTime = millis();
  if (DEBUG_MODE && error > ERROR_NONE && error <= ERROR_SYSTEM_RESET) {
    int errorIndex = error - 1; // Convertir a índice de array (0-6)
    
    if (currentTime - logState.lastLogTime[errorIndex] >= LOG_RATE_LIMIT_MS) {
      // Imprimir log normal
      DEBUG_PRINT("[ERROR] Tipo: ");
      DEBUG_PRINT(error);
      DEBUG_PRINT(" - ");
      DEBUG_PRINTLN(details);
      
      // Si había logs suprimidos, informar cuántos
      if (logState.suppressedCount[errorIndex] > 0) {
        DEBUG_PRINT("[INFO] Suprimidos ");
        DEBUG_PRINT(logState.suppressedCount[errorIndex]);
        DEBUG_PRINTLN(" logs similares");
        logState.suppressedCount[errorIndex] = 0;
      }
      
      logState.lastLogTime[errorIndex] = currentTime;
    } else {
      // Incrementar contador de suprimidos
      logState.suppressedCount[errorIndex]++;
    }
  }
  
  // Log específico por tipo de error
  switch(error) {
    case ERROR_RX_TIMEOUT:
      metrics.timeoutCount++;
      break;
    case ERROR_MALFORMED_FRAME:
      metrics.malformedFrames++;
      break;
    case ERROR_WRONG_DESTINATION:
      metrics.wrongDestination++;
      break;
    default:
      break;
  }
}

// ===== MEJORA 10: FUNCIONES DE MÉTRICAS POR RED =====
#if ENABLE_MQTT_METRICS
void initMQTT() {
  if (WiFi.status() == WL_CONNECTED) {
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    if (mqttClient.connect(("anchor_" + String(ID_PONG)).c_str())) {
      Serial.println("[MQTT] Conectado para métricas");
    }
  }
}

void publishMetricsMQTT() {
  if (!mqttClient.connected()) {
    initMQTT();
  }
  
  if (mqttClient.connected()) {
    String topic = "uwb/anchor/" + String(ID_PONG) + "/metrics";
    String payload = "{";
    payload += "\"id\":" + String(ID_PONG) + ",";
    payload += "\"total\":" + String(metrics.totalTransactions) + ",";
    payload += "\"success\":" + String(metrics.successfulTransactions) + ",";
    payload += "\"errors\":" + String(metrics.errorCount) + ",";
    payload += "\"success_rate\":" + String(metrics.successRate) + ",";
    payload += "\"uptime\":" + String((millis() - metrics.initTime) / 1000) + ",";
    payload += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
    payload += "\"stage\":\"" + String(getStateString(curr_stage)) + "\"";
    payload += "}";
    
    mqttClient.publish(topic.c_str(), payload.c_str());
    mqttClient.loop();
  }
}
#endif

#if ENABLE_UDP_METRICS
void publishMetricsUDP() {
  if (WiFi.status() == WL_CONNECTED) {
    udpClient.beginPacket(LOG_SERVER_IP, UDP_METRICS_PORT);
    
    StaticJsonDocument<512> doc;
    doc["type"] = "anchor_metrics";
    doc["id"] = ID_PONG;
    doc["total"] = metrics.totalTransactions;
    doc["success"] = metrics.successfulTransactions;
    doc["errors"] = metrics.errorCount;
    doc["success_rate"] = metrics.successRate;
    doc["uptime"] = (millis() - metrics.initTime) / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["stage"] = getStateString(curr_stage);
    
    String jsonString;
    serializeJson(doc, jsonString);
    udpClient.print(jsonString);
    udpClient.endPacket();
  }
}
#endif

// ===== FUNCIONES DE SETUP ROBUSTAS =====
void setup() {
  Serial.begin(SERIAL_BAUD);  // MEJORA 3: Baudrate configurable
  metrics.initTime = millis();
  metrics.lastStatsReport = millis();
  
  // MEJORA 8: Validación de ID
  if (!isAnchorIDValid(ID_PONG)) {
    Serial.print("[CRITICAL] ID_PONG inválido: ");
    Serial.println(ID_PONG);
    Serial.println("Valores válidos: 10, 20, 30, 40, 50");
    sendResetBeacon("ID_INVALIDO");
    delay(5000);
    ESP.restart();
  }
  
  // MEJORA 13: Cargar métricas persistentes
  #if ENABLE_NVS_PERSISTENCE
  loadMetricsFromNVS();
  lastNVSSave = millis();
  #endif
  
  Serial.println("\n=== ANCLA GPS INDOOR FÚTBOL SALA - TFG v2.1 ===");
  Serial.print("Firmware: ");
  Serial.println(ANCHOR_FW_VERSION);
  Serial.print("Build: ");
  Serial.println(BUILD_DATE);
  Serial.print("[INIT] Iniciando Ancla ID: ");
  Serial.println(ID_PONG);
  Serial.print("Configurado para cancha: ");
  Serial.print(FUTSAL_COURT_LENGTH);
  Serial.print("x");
  Serial.print(FUTSAL_COURT_WIDTH);
  Serial.println("m");
  
  // MEJORA TFG: Configurar Watchdog
  esp_task_wdt_init(WATCHDOG_TIMEOUT_MS / 1000, true);
  esp_task_wdt_add(NULL);
  
  // MEJORA 10: Inicializar WiFi para métricas si está habilitado
  #if ENABLE_MQTT_METRICS || ENABLE_UDP_METRICS
  WiFi.begin(STA_SSID, STA_PASS);
  Serial.print("[WIFI] Conectando");
  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 20) {
    delay(500);
    Serial.print(".");
    wifiAttempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Conectado para métricas");
    #if ENABLE_MQTT_METRICS
    initMQTT();
    #endif
  } else {
    Serial.println("\n[WIFI] No conectado - métricas solo por Serial");
  }
  #endif
  
  // Inicialización robusta del chip DW3000
  if (!initializeDW3000()) {
    Serial.println("[CRITICAL] Fallo en inicialización DW3000. Reiniciando...");
    sendResetBeacon("DW3000_INIT_FAIL");
    delay(1000);
    ESP.restart();
  }
  
  lastSuccessfulActivityTime = millis();
  
  Serial.println("[SUCCESS] Ancla inicializada correctamente");
  Serial.println("Estado: Esperando tags...");
  Serial.println("=============================================");
}

// MEJORA 5: Inicialización DW3000 con mejor gestión de errores y watchdog
bool initializeDW3000() {
  int attempts = 0;
  const int MAX_INIT_ATTEMPTS = 3;
  
  while (attempts < MAX_INIT_ATTEMPTS) {
    attempts++;
    Serial.print("[INIT] Intento ");
    Serial.print(attempts);
    Serial.print("/");
    Serial.println(MAX_INIT_ATTEMPTS);
    
    DW3000.begin();
    DW3000.hardReset();
    delay(200);
    
    // MEJORA 5: Verificación de estado IDLE con watchdog reset
    int retries = 0;
    while (!DW3000.checkForIDLE() && retries < 10) {
      Serial.print(".");
      esp_task_wdt_reset(); // MEJORA 5: Reset watchdog durante init
      delay(DW3000_INIT_RETRY_DELAY_MS); // MEJORA 5: Delay configurable pequeño
      retries++;
    }
    Serial.println();
    
    if (retries >= 10) {
      Serial.print("[WARNING] No se alcanzó IDLE en intento ");
      Serial.println(attempts);
      if (attempts < MAX_INIT_ATTEMPTS) {
        esp_task_wdt_reset(); // MEJORA 5: Reset antes de continuar
        delay(DW3000_INIT_RETRY_DELAY_MS);
        continue;
      } else {
        return false;
      }
    }
    
    DW3000.softReset();
    delay(200);
    esp_task_wdt_reset(); // MEJORA 5: Reset después de softReset
    
    if (!DW3000.checkForIDLE()) {
      Serial.print("[WARNING] Fallo en segundo IDLE check, intento ");
      Serial.println(attempts);
      if (attempts < MAX_INIT_ATTEMPTS) {
        esp_task_wdt_reset();
        delay(DW3000_INIT_RETRY_DELAY_MS);
        continue;
      } else {
        return false;
      }
    }

    // TFG v2.1-FINAL: Verificar retorno de DW3000.init()
    if (!DW3000.init()) {
      Serial.print("[WARNING] DW3000.init() falló en intento ");
      Serial.println(attempts);
      if (attempts < MAX_INIT_ATTEMPTS) {
        esp_task_wdt_reset();
        delay(DW3000_INIT_RETRY_DELAY_MS);
        continue;
      } else {
        return false;
      }
    }
    
    DW3000.setupGPIO();
    // MEJORA 6: Eliminar configureAsTX() antes de standardRX()
    DW3000.clearSystemStatus();
    DW3000.standardRX();
    
    Serial.print("[SUCCESS] DW3000 inicializado en intento ");
    Serial.println(attempts);
    return true;
  }
  
  return false;
}

// ===== LOOP PRINCIPAL OPTIMIZADO =====
void loop() {
  unsigned long currentTime = millis();
  
  // MEJORA TFG: Reset watchdog periódico
  esp_task_wdt_reset();
  
  // Auto-reinicio por inactividad (coherente con tag)
  if (currentTime - lastSuccessfulActivityTime > ANCHOR_RESET_TIMEOUT_MS) { // MEJORA 2: Timeout configurable
    Serial.println("[AUTO-RESET] Timeout de inactividad detectado");
    reportErrorStats();
    logError(ERROR_SYSTEM_RESET, "Timeout inactividad");
    
    // MEJORA 13: Guardar métricas antes del reset
    #if ENABLE_NVS_PERSISTENCE
    saveMetricsToNVS();
    #endif
    
    sendResetBeacon("TIMEOUT_INACTIVIDAD");
    delay(200);
    ESP.restart();
  }
  
  // MEJORA 13: Guardado periódico de métricas en NVS
  #if ENABLE_NVS_PERSISTENCE
  if (currentTime - lastNVSSave > NVS_SAVE_INTERVAL_MS) {
    saveMetricsToNVS();
  }
  #endif
  
  // Reporte de estadísticas periódico
  if (currentTime - metrics.lastStatsReport > STATS_REPORT_INTERVAL) { // MEJORA 2: Intervalo configurable
    reportStats();
    
    // MEJORA 10: Publicar métricas por red si está habilitado
    #if ENABLE_MQTT_METRICS
    publishMetricsMQTT();
    #endif
    #if ENABLE_UDP_METRICS
    publishMetricsUDP();
    #endif
    
    metrics.lastStatsReport = currentTime;
  }

  // Máquina de estados del protocolo de ranging (optimizada)
  switch (curr_stage) {
    case Stage::Await: // Esperar solicitud de ranging
      handleAwaitRanging();
      break;
      
    case Stage::SendResp: // Enviar respuesta inicial
      handleSendResponse();
      break;
      
    case Stage::AwaitSecond: // Esperar segunda respuesta
      handleAwaitSecondResponse();
      break;
      
    case Stage::SendFinal: // Enviar información final
      handleSendFinalInfo();
      break;
      
    case Stage::Cleanup: // Estado de limpieza
      handleCleanup();
      break;
      
    default:
      handleUnknownState();
      break;
  }
}

// ===== FUNCIONES DE MANEJO DE ESTADOS OPTIMIZADAS =====

void handleAwaitRanging() {
  t_roundB = 0;
  t_replyB = 0;

  if (rx_status = DW3000.receivedFrameSucc()) {
    DW3000.clearSystemStatus();
    
    if (rx_status == 1) {
      metrics.totalTransactions++;
      
      // MEJORA 12: Filtro anti-fantasmas antes de procesar
      #if ENABLE_RANGE_FILTER
      if (!isSignalValid()) {
        metrics.filteredSignals++;
        DEBUG_PRINTLN("[FILTER] Señal filtrada por anti-fantasmas");
        DW3000.standardRX();
        return;
      }
      #endif
      
      // MEJORA TFG: Validación robusta de frames
      if (DW3000.ds_isErrorFrame()) {
        DEBUG_PRINTLN("[WARNING] Frame de error detectado");
        logError(ERROR_MALFORMED_FRAME, "Error frame stage 0");
        curr_stage = Stage::Await;
        DW3000.standardRX();
        return;
      }
      
      // Verificar si es para esta ancla
      if (DW3000.getDestinationID() != ID_PONG) {
        // No es para esta ancla, seguir escuchando (no es error)
        logError(ERROR_WRONG_DESTINATION, "Mensaje para otra ancla");
        DW3000.standardRX();
        return;
      }
      
      // Verificar stage correcto
      if (DW3000.ds_getStage() != 1) {
        DEBUG_PRINTLN("[WARNING] Stage incorrecto recibido");
        DW3000.ds_sendErrorFrame();
        // MEJORA 7: Actualizar actividad cuando se envía error frame
        lastSuccessfulActivityTime = millis();
        DW3000.standardRX();
        logError(ERROR_WRONG_STAGE, "Stage incorrecto en await");
        curr_stage = Stage::Await;
        return;
      }
      
      // Todo correcto, proceder al siguiente stage
      DEBUG_PRINTLN("[SUCCESS] Ranging request válido recibido");
      curr_stage = Stage::SendResp;
      
    } else {
      DEBUG_PRINTLN("[ERROR] Error en recepción RX");
      logError(ERROR_RX_TIMEOUT, "Fallo receivedFrameSucc");
      DW3000.clearSystemStatus();
    }
  }
}

void handleSendResponse() {
  DW3000.setDestinationID(ID_PONG);
  DW3000.ds_sendFrame(2);

  rx = DW3000.readRXTimestamp();
  tx = DW3000.readTXTimestamp();
  t_replyB = tx - rx;
  
  DEBUG_PRINTLN("[TX] Respuesta inicial enviada");
  curr_stage = Stage::AwaitSecond;
}

void handleAwaitSecondResponse() {
  if (rx_status = DW3000.receivedFrameSucc()) {
    DW3000.clearSystemStatus();
    
    if (rx_status == 1) {
      // MEJORA TFG: Validación robusta de frames
      if (DW3000.ds_isErrorFrame()) {
        DEBUG_PRINTLN("[WARNING] Frame de error en stage 2");
        logError(ERROR_MALFORMED_FRAME, "Error frame stage 2");
        curr_stage = Stage::Await;
        DW3000.standardRX();
        return;
      }
      
      // Verificar destinatario
      if (DW3000.getDestinationID() != ID_PONG) {
        // Mensaje para otra ancla, limpiar y continuar
        DEBUG_PRINTLN("[INFO] Mensaje para otra ancla en stage 2");
        curr_stage = Stage::Cleanup;
        return;
      }
      
      // Verificar stage
      if (DW3000.ds_getStage() != 3) {
        DEBUG_PRINTLN("[WARNING] Stage incorrecto en segunda respuesta");
        DW3000.ds_sendErrorFrame();
        // MEJORA 7: Actualizar actividad cuando se envía error frame
        lastSuccessfulActivityTime = millis();
        DW3000.standardRX();
        logError(ERROR_WRONG_STAGE, "Stage incorrecto stage 2");
        curr_stage = Stage::Await;
        return;
      }
      
      DEBUG_PRINTLN("[SUCCESS] Segunda respuesta válida recibida");
      curr_stage = Stage::SendFinal;
      
    } else {
      DEBUG_PRINTLN("[ERROR] Error en segunda respuesta");
      logError(ERROR_RX_TIMEOUT, "Fallo segunda respuesta");
      DW3000.clearSystemStatus();
    }
  }
}

void handleSendFinalInfo() {
  rx = DW3000.readRXTimestamp();
  t_roundB = rx - tx;
  
  DW3000.ds_sendRTInfo(t_roundB, t_replyB);
  
  // MEJORA TFG: Transacción completada exitosamente
  metrics.successfulTransactions++;
  curr_stage = Stage::Await;
  DW3000.standardRX();
  lastSuccessfulActivityTime = millis();
  
  DEBUG_PRINTLN("[SUCCESS] Transacción de ranging completada");
}

void handleCleanup() {
  DEBUG_PRINTLN("[CLEANUP] Limpiando estado");
  curr_stage = Stage::Await;
  DW3000.standardRX();
}

void handleUnknownState() {
  Serial.print("[ERROR] Estado desconocido: ");
  Serial.println(static_cast<int>(curr_stage)); // Cast para imprimir el valor del enum
  logError(ERROR_SYSTEM_RESET, "Estado máquina desconocido");
  curr_stage = Stage::Await;
  DW3000.standardRX();
}

// ===== FUNCIONES DE REPORTING MEJORADAS =====

void reportStats() {
  // Calcular métricas actualizadas
  if (metrics.totalTransactions > 0) {
    metrics.successRate = (float)metrics.successfulTransactions / metrics.totalTransactions * 100.0;
    metrics.errorRate = (float)metrics.errorCount / metrics.totalTransactions * 100.0;
  }
  
  unsigned long uptime = millis() / 1000;
  unsigned long timeSinceLastActivity = (millis() - lastSuccessfulActivityTime) / 1000;
  
  Serial.println("========== ESTADÍSTICAS ANCLA TFG v2.1 ==========");
  Serial.print("ID Ancla: ");
  Serial.println(ID_PONG);
  Serial.print("Firmware: ");
  Serial.println(ANCHOR_FW_VERSION);
  Serial.print("Uptime: ");
  Serial.print(uptime);
  Serial.println(" segundos");
  Serial.println("--- Transacciones ---");
  Serial.print("Total: ");
  Serial.println(metrics.totalTransactions);
  Serial.print("Exitosas: ");
  Serial.println(metrics.successfulTransactions);
  Serial.print("Tasa éxito: ");
  Serial.print(metrics.successRate);
  Serial.println("%");
  Serial.println("--- Errores ---");
  Serial.print("Total errores: ");
  Serial.println(metrics.errorCount);
  Serial.print("Timeouts: ");
  Serial.println(metrics.timeoutCount);
  Serial.print("Frames malformados: ");
  Serial.println(metrics.malformedFrames);
  Serial.print("Destino incorrecto: ");
  Serial.println(metrics.wrongDestination);
  Serial.print("Señales filtradas: ");
  Serial.println(metrics.filteredSignals);
  Serial.print("Tasa error: ");
  Serial.print(metrics.errorRate);
  Serial.println("%");
  Serial.println("--- Estado ---");
  Serial.print("Última actividad hace: ");
  Serial.print(timeSinceLastActivity);
  Serial.println(" segundos");
  Serial.print("Estado actual: ");
  Serial.println(getStateString(curr_stage));
  Serial.print("Memoria libre: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  Serial.println("===============================================");
}

void reportErrorStats() {
  Serial.println("========== REPORTE DE ERRORES TFG ==========");
  Serial.print("Ancla ID: ");
  Serial.println(ID_PONG);
  Serial.print("Uptime total: ");
  Serial.print((millis() - metrics.initTime) / 1000);
  Serial.println(" segundos");
  Serial.print("Errores totales: ");
  Serial.println(metrics.errorCount);
  Serial.print("Última actividad exitosa hace: ");
  Serial.print((millis() - lastSuccessfulActivityTime) / 1000);
  Serial.println(" segundos");
  Serial.print("Transacciones exitosas: ");
  Serial.print(metrics.successfulTransactions);
  Serial.print("/");
  Serial.println(metrics.totalTransactions);
  Serial.println("=========================================");
}

// MEJORA TFG: Función auxiliar para debugging con soporte para enum
const char* getStateString(Stage state) {
  switch(state) {
    case Stage::Await: return "AWAIT_RANGING";
    case Stage::SendResp: return "SEND_RESPONSE";
    case Stage::AwaitSecond: return "AWAIT_SECOND";
    case Stage::SendFinal: return "SEND_FINAL";
    case Stage::Cleanup: return "CLEANUP";
    default: return "UNKNOWN";
  }
}