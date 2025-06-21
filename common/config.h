#pragma once
#ifndef CONFIG_H
#define CONFIG_H

// ===== CONFIGURACIÓN CENTRALIZADA DEL SISTEMA GPS INDOOR =====
// Este archivo centraliza todas las configuraciones para facilitar
// la documentación del TFG y el mantenimiento del código

// ===== CONFIGURACIÓN DE HARDWARE =====
#ifndef TAG_ID
#define TAG_ID 1                    // ID único del tag
#endif
#ifndef NUM_ANCHORS
#define NUM_ANCHORS 5               // Número de anclas activas (TFG usa exactamente 5)
#endif
#ifndef MAX_ANCHORS
#define MAX_ANCHORS 5               // TFG v2.1: Usamos exactamente 5 anclas, no 10
#endif

// ===== CONFIGURACIÓN DE COMUNICACIÓN SERIE =====
#ifndef SERIAL_BAUD
#define SERIAL_BAUD 921600          // Baudrate serie configurable (más estable que 2000000)
#endif

// ===== CONFIGURACIÓN DE ANCLAS =====
#ifndef ID_PONG
#define ID_PONG 10                  // ID del ancla (configurable por bandera -DID_PONG=XX)
#endif

// ===== VALIDACIÓN DE ID DE ANCLA (MEJORADA) =====
// TFG MEJORA 8: Validación en tiempo de compilación para Arduino
static_assert(ID_PONG == 10 || ID_PONG == 20 || ID_PONG == 30 || ID_PONG == 40 || ID_PONG == 50, 
              "ID_PONG debe ser 10, 20, 30, 40 o 50 según las posiciones de anclas del TFG");

// ===== CONFIGURACIÓN DE TIMEOUTS Y WATCHDOG =====
#ifndef ANCHOR_RESET_TIMEOUT_MS
#define ANCHOR_RESET_TIMEOUT_MS 15000  // Timeout de auto-reinicio por inactividad
#endif
#ifndef WATCHDOG_TIMEOUT_MS
#define WATCHDOG_TIMEOUT_MS 30000      // Timeout del watchdog de sistema
#endif
#ifndef STATS_REPORT_INTERVAL
#define STATS_REPORT_INTERVAL 60000    // Intervalo de reporte de estadísticas
#endif
#ifndef DW3000_INIT_RETRY_DELAY_MS
#define DW3000_INIT_RETRY_DELAY_MS 50  // Delay pequeño entre reintentos de inicialización
#endif

// ===== CONFIGURACIÓN DE LOGGING Y MÉTRICAS =====
#ifndef LOG_RATE_LIMIT_MS
#define LOG_RATE_LIMIT_MS 1000         // TFG MEJORA 9: Suprimir logs repetidos < 1000ms
#endif
#ifndef ENABLE_MQTT_METRICS
#define ENABLE_MQTT_METRICS 1          // TFG MEJORA 10: Habilitar métricas por MQTT (1/0 en lugar de true/false)
#endif
#ifndef ENABLE_UDP_METRICS
#define ENABLE_UDP_METRICS 0           // TFG MEJORA 10: Métricas por UDP (alternativa)
#endif
#ifndef UDP_METRICS_PORT
#define UDP_METRICS_PORT 8888          // Puerto UDP para métricas
#endif

// ===== CONFIGURACIÓN DE BEACON Y FILTROS =====
#ifndef ENABLE_RESET_BEACON
#define ENABLE_RESET_BEACON 1          // TFG MEJORA 11: Enviar beacon antes de reset
#endif
#ifndef ENABLE_RANGE_FILTER
#define ENABLE_RANGE_FILTER 1          // TFG MEJORA 12: Filtro anti-fantasmas
#endif
#ifndef MIN_RSSI_THRESHOLD
#define MIN_RSSI_THRESHOLD -90         // dBm mínimo para considerar señal válida
#endif

// ===== CONFIGURACIÓN DE PERSISTENCIA =====
#ifndef ENABLE_NVS_PERSISTENCE
#define ENABLE_NVS_PERSISTENCE 1       // TFG MEJORA 13: Persistir contadores en NVS (1/0)
#endif
#ifndef NVS_NAMESPACE
#define NVS_NAMESPACE "anchor_metrics" // Namespace para datos persistentes
#endif
#ifndef NVS_SAVE_INTERVAL_MS
#define NVS_SAVE_INTERVAL_MS 300000    // Guardar en NVS cada 5 minutos
#endif

// ===== CONFIGURACIÓN CONSTEXPR TYPE-SAFE =====
namespace cfg {
  // Dimensiones de cancha (constexpr para type-safety)
  constexpr float courtLength = 40.0f;    // FUTSAL_COURT_LENGTH
  constexpr float courtWidth = 20.0f;     // FUTSAL_COURT_WIDTH
  constexpr float maxPlayerSpeed = 8.0f;  // MAX_PLAYER_SPEED
  
  // Umbrales de filtrado
  constexpr float maxRangeThreshold = 50.0f; // MAX_RANGE_THRESHOLD_M
  constexpr float minRangeThreshold = 0.5f;  // MIN_RANGE_THRESHOLD_M
  
  // Configuración de TDMA
  constexpr int tdmaCycleMs = 500;          // TDMA_CYCLE_MS
  constexpr int tdmaSlotDurationMs = 100;   // TDMA_SLOT_DURATION_MS
  constexpr int responseTimeout = 100;      // RESPONSE_TIMEOUT
  constexpr int roundDelay = 50;            // ROUND_DELAY
}

// ===== CONFIGURACIÓN LEGACY (para compatibilidad) =====
#ifndef FUTSAL_COURT_LENGTH
#define FUTSAL_COURT_LENGTH cfg::courtLength
#endif
#ifndef FUTSAL_COURT_WIDTH
#define FUTSAL_COURT_WIDTH cfg::courtWidth
#endif
#ifndef MAX_PLAYER_SPEED
#define MAX_PLAYER_SPEED cfg::maxPlayerSpeed
#endif
#ifndef MAX_RANGE_THRESHOLD_M
#define MAX_RANGE_THRESHOLD_M cfg::maxRangeThreshold
#endif
#ifndef MIN_RANGE_THRESHOLD_M
#define MIN_RANGE_THRESHOLD_M cfg::minRangeThreshold
#endif

// ===== CONFIGURACIÓN DE RANGING Y TDMA =====
#ifndef TDMA_CYCLE_MS
#define TDMA_CYCLE_MS cfg::tdmaCycleMs
#endif
#ifndef TDMA_SLOT_DURATION_MS
#define TDMA_SLOT_DURATION_MS cfg::tdmaSlotDurationMs
#endif
#ifndef RESPONSE_TIMEOUT
#define RESPONSE_TIMEOUT cfg::responseTimeout
#endif
#ifndef ROUND_DELAY
#define ROUND_DELAY cfg::roundDelay
#endif

// ===== CONFIGURACIÓN DE FILTRADO =====
#define NUM_MEASUREMENTS 3          // Mediciones por buffer de ancla
#define KALMAN_DIST_Q 0.02         // Ruido de proceso para distancias
#define KALMAN_DIST_R 0.15         // Ruido de observación para distancias
#define KALMAN_POS_Q 0.05          // Ruido de proceso para posición
#define KALMAN_POS_R 0.08          // Ruido de observación para posición
#define KALMAN_VEL_Q 2.0           // Ruido de proceso para velocidad

// ===== CONFIGURACIÓN DE RED =====
#ifndef USE_AP_MODE
#define USE_AP_MODE 0              // Usar modo Access Point (0/1)
#endif
#ifndef HTTP_PORT
#define HTTP_PORT 80               // Puerto del servidor web
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883             // Puerto MQTT
#endif

// ===== CREDENCIALES (incluir secrets.h si existe, sino usar defaults) =====
#ifdef __has_include
  #if __has_include("../common/secrets.h")
    #include "../common/secrets.h"
  #else
    // Valores por defecto si no existe secrets.h
    #ifndef AP_SSID
    #define AP_SSID "UWB_TAG_AP"
    #endif
    #ifndef AP_PASS
    #define AP_PASS "12345678"
    #endif
    #ifndef STA_SSID
    #define STA_SSID "iPhone de Nicolas"
    #endif
    #ifndef STA_PASS
    #define STA_PASS "12345678"
    #endif
    #ifndef MQTT_SERVER
    #define MQTT_SERVER "172.20.10.3"
    #endif
    #ifndef LOG_SERVER_IP
    #define LOG_SERVER_IP "172.20.10.3"
    #endif
    #ifndef LOG_SERVER_PORT
    #define LOG_SERVER_PORT 5000
    #endif
  #endif
#else
  // Fallback para compiladores antiguos
  #define AP_SSID "UWB_TAG_AP"
  #define AP_PASS "12345678"
  #define STA_SSID "iPhone de Nicolas"
  #define STA_PASS "12345678"
  #define MQTT_SERVER "172.20.10.3"
  #define LOG_SERVER_IP "172.20.10.3"
  #define LOG_SERVER_PORT 5000
#endif

// ===== CONFIGURACIÓN DE MÉTRICAS TFG =====
#define UPDATE_INTERVAL_MS 25       // Intervalo de actualización (40Hz)
#define STATUS_UPDATE_INTERVAL 2000 // Intervalo de estado MQTT
#define METRICS_REPORT_INTERVAL 30000 // Intervalo de reporte de métricas

// ===== CONFIGURACIÓN DE ZONAS DE FÚTBOL SALA =====
#define NUM_ZONES 6                 // Número de zonas definidas

// Estructura de zona
struct ZoneConfig {
  float x, y, radius;
  unsigned long minStayTime;
  const char* name;
};

// Definición de zonas específicas de fútbol sala
const ZoneConfig FUTSAL_ZONES[NUM_ZONES] = {
  {2.0f, 4.0f, 3.0f, 1000, "Area_Porteria_1"},
  {38.0f, 4.0f, 3.0f, 1000, "Area_Porteria_2"}, 
  {20.0f, 10.0f, 3.0f, 2000, "Centro_Campo"},
  {10.0f, 10.0f, 5.0f, 1500, "Medio_Campo_1"},
  {30.0f, 10.0f, 5.0f, 1500, "Medio_Campo_2"},
  {20.0f, 2.0f, 8.0f, 500, "Banda_Lateral"}
};

// ===== POSICIONES ÓPTIMAS DE ANCLAS UWB PARA FÚTBOL SALA =====
// Configuración optimizada para evitar líneas paralelas y maximizar precisión
const float ANCHOR_POSITIONS[MAX_ANCHORS][2] = {
  {-1.0f, -1.0f},   // Ancla 10 - Fuera esquina inferior izquierda
  {-1.0f, 21.0f},   // Ancla 20 - Fuera esquina superior izquierda  
  {41.0f, -1.0f},   // Ancla 30 - Fuera esquina inferior derecha
  {41.0f, 21.0f},   // Ancla 40 - Fuera esquina superior derecha
  {20.0f, 25.0f}    // Ancla 50 - Centrada fuera de banda superior
};

// IDs de las 5 anclas del TFG
const int ANCHOR_IDS[MAX_ANCHORS] = {10, 20, 30, 40, 50};

// ===== VALIDACIÓN DE TAMAÑOS =====
static_assert(sizeof(ANCHOR_POSITIONS)/sizeof(ANCHOR_POSITIONS[0]) == MAX_ANCHORS, 
              "ANCHOR_POSITIONS desfasado de MAX_ANCHORS");
static_assert(sizeof(ANCHOR_IDS)/sizeof(ANCHOR_IDS[0]) == MAX_ANCHORS, 
              "ANCHOR_IDS desfasado de MAX_ANCHORS");

// ===== CONFIGURACIÓN DE VISUALIZACIÓN =====
#ifndef PIXELS_PER_M
#define PIXELS_PER_M 15.0           // Pixels por metro en visualización web
#endif

// ===== CONFIGURACIÓN DE MEMORIA Y BUFFERS =====
#ifndef JSON_BUFFER_SIZE
#define JSON_BUFFER_SIZE 2048       // Tamaño máximo para documentos JSON
#endif
#ifndef MQTT_MAX_PACKET_SIZE
#define MQTT_MAX_PACKET_SIZE 2048   // TFG v2.1: Ampliado para robustez (5 anclas)
#endif

// ===== CONFIGURACIÓN DE BAJO CONSUMO =====
#define SLEEP_TIMEOUT 300000        // Timeout para modo de bajo consumo (ms)

#endif // CONFIG_H 