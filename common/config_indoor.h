#pragma once
#ifndef CONFIG_INDOOR_H
#define CONFIG_INDOOR_H

// ===== CONFIGURACIÓN PARA PRUEBAS INDOOR EN CASA =====
// Este archivo adapta el sistema GPS Indoor para espacios domésticos
// Ideal para validar funcionamiento antes de pruebas en pista real

// ===== CONFIGURACIÓN DE HARDWARE =====
#ifndef TAG_ID
#define TAG_ID 1                    // ID único del tag
#endif
#ifndef NUM_ANCHORS
#define NUM_ANCHORS 5               // Mantener 5 anclas para consistencia
#endif
#ifndef MAX_ANCHORS
#define MAX_ANCHORS 5               // Usar exactamente 5 anclas
#endif

// ===== CONFIGURACIÓN DE COMUNICACIÓN SERIE =====
#ifndef SERIAL_BAUD
#define SERIAL_BAUD 921600          // Baudrate serie
#endif

// ===== CONFIGURACIÓN DE ANCLAS =====
#ifndef ID_PONG
#define ID_PONG 10                  // ID del ancla (configurable por bandera -DID_PONG=XX)
#endif

// ===== VALIDACIÓN DE ID DE ANCLA =====
static_assert(ID_PONG == 10 || ID_PONG == 20 || ID_PONG == 30 || ID_PONG == 40 || ID_PONG == 50, 
              "ID_PONG debe ser 10, 20, 30, 40 o 50 según las posiciones de anclas indoor");

// ===== CONFIGURACIÓN DE TIMEOUTS (INDOOR OPTIMIZADA) =====
#ifndef ANCHOR_RESET_TIMEOUT_MS
#define ANCHOR_RESET_TIMEOUT_MS 10000  // Timeout reducido para indoor
#endif
#ifndef WATCHDOG_TIMEOUT_MS
#define WATCHDOG_TIMEOUT_MS 15000      // Timeout reducido del watchdog
#endif
#ifndef STATS_REPORT_INTERVAL
#define STATS_REPORT_INTERVAL 30000    // Reportar cada 30s en indoor
#endif
#ifndef DW3000_INIT_RETRY_DELAY_MS
#define DW3000_INIT_RETRY_DELAY_MS 50  // Delay entre reintentos
#endif

// ===== CONFIGURACIÓN DE LOGGING =====
#ifndef LOG_RATE_LIMIT_MS
#define LOG_RATE_LIMIT_MS 500          // Logs más frecuentes para debugging indoor
#endif
#ifndef ENABLE_MQTT_METRICS
#define ENABLE_MQTT_METRICS 1          // Habilitar métricas por MQTT
#endif
#ifndef ENABLE_UDP_METRICS
#define ENABLE_UDP_METRICS 0           // Deshabilitar UDP para simplificar
#endif

// ===== CONFIGURACIÓN CONSTEXPR PARA INDOOR =====
namespace cfg_indoor {
  // DIMENSIONES REALES SEGÚN PLANO DE TU CASA
  constexpr float courtLength = 8.0f;     // 8 metros de largo (estimado del plano)
  constexpr float courtWidth = 6.0f;      // 6 metros de ancho (estimado del plano)
  constexpr float maxPlayerSpeed = 3.0f;  // Velocidad máxima en casa (caminar rápido)
  
  // Umbrales de filtrado ajustados para indoor
  constexpr float maxRangeThreshold = 15.0f; // Máximo 15m en casa
  constexpr float minRangeThreshold = 0.3f;  // Mínimo 30cm
  
  // TDMA más rápido para indoor (menor latencia)
  constexpr int tdmaCycleMs = 300;          // Ciclo más rápido
  constexpr int tdmaSlotDurationMs = 60;    // Slots más cortos
  constexpr int responseTimeout = 80;       // Timeout más corto
  constexpr int roundDelay = 30;            // Delay reducido
}

// ===== CONFIGURACIÓN LEGACY (compatibilidad) =====
#define FUTSAL_COURT_LENGTH cfg_indoor::courtLength
#define FUTSAL_COURT_WIDTH cfg_indoor::courtWidth
#define MAX_PLAYER_SPEED cfg_indoor::maxPlayerSpeed
#define MAX_RANGE_THRESHOLD_M cfg_indoor::maxRangeThreshold
#define MIN_RANGE_THRESHOLD_M cfg_indoor::minRangeThreshold

// ===== CONFIGURACIÓN DE RANGING Y TDMA =====
#define TDMA_CYCLE_MS cfg_indoor::tdmaCycleMs
#define TDMA_SLOT_DURATION_MS cfg_indoor::tdmaSlotDurationMs
#define RESPONSE_TIMEOUT cfg_indoor::responseTimeout
#define ROUND_DELAY cfg_indoor::roundDelay

// ===== CONFIGURACIÓN DE FILTRADO AJUSTADA PARA INDOOR =====
#define NUM_MEASUREMENTS 3          // Mediciones por buffer
#define KALMAN_DIST_Q 0.01         // Menos ruido en indoor (más estable)
#define KALMAN_DIST_R 0.08         // Observación más precisa en indoor
#define KALMAN_POS_Q 0.02          // Posición más estable en indoor
#define KALMAN_POS_R 0.05          // Observación más precisa
#define KALMAN_VEL_Q 0.5           // Velocidad más suave en indoor

// ===== CONFIGURACIÓN DE RED (IGUAL) =====
#ifndef USE_AP_MODE
#define USE_AP_MODE 0              // Usar modo Station
#endif
#ifndef HTTP_PORT
#define HTTP_PORT 80               // Puerto del servidor web
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883             // Puerto MQTT
#endif

// ===== CREDENCIALES (mismo sistema) =====
#ifdef __has_include
  #if __has_include("../common/secrets.h")
    #include "../common/secrets.h"
  #else
    #ifndef AP_SSID
    #define AP_SSID "UWB_INDOOR_AP"
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
  #define AP_SSID "UWB_INDOOR_AP"
  #define AP_PASS "12345678"
  #define STA_SSID "iPhone de Nicolas"
  #define STA_PASS "12345678"
  #define MQTT_SERVER "172.20.10.3"
  #define LOG_SERVER_IP "172.20.10.3"
  #define LOG_SERVER_PORT 5000
#endif

// ===== CONFIGURACIÓN DE MÉTRICAS (MÁS FRECUENTE PARA DEBUGGING) =====
#define UPDATE_INTERVAL_MS 20       // 50Hz para mejor respuesta en indoor
#define STATUS_UPDATE_INTERVAL 1000 // Estado cada segundo
#define METRICS_REPORT_INTERVAL 15000 // Métricas cada 15s

// ===== ZONAS INDOOR PARA PRUEBAS =====
#define NUM_ZONES 4                 // Menos zonas para casa

struct ZoneConfig {
  float x, y, radius;
  unsigned long minStayTime;
  const char* name;
};

// ZONAS ADAPTADAS SEGÚN PLANO REAL DE TU CASA (8x6m)
const ZoneConfig INDOOR_ZONES[NUM_ZONES] = {
  {1.5f, 5.0f, 1.2f, 500, "Zona_Sofa"},      // Zona del sofá (esquina superior izquierda)
  {6.5f, 5.0f, 1.0f, 500, "Zona_TV"},        // Zona de la TV (esquina superior derecha)
  {2.5f, 3.0f, 1.0f, 1000, "Zona_Mesa_Centro"}, // Mesa del centro
  {2.0f, 1.5f, 1.0f, 500, "Zona_Mesa_Sur"}   // Mesa inferior
};

// ===== POSICIONES DE ANCLAS SEGÚN PLANO REAL (8x6m) =====
// Posiciones exactas según tu dibujo
const float ANCHOR_POSITIONS[MAX_ANCHORS][2] = {
  {-0.5f, -0.5f},   // Ancla 10 - Esquina inferior izquierda
  {-0.5f, 6.5f},    // Ancla 20 - Esquina superior izquierda  
  {8.5f, -0.5f},    // Ancla 30 - Esquina inferior derecha
  {8.5f, 6.5f},     // Ancla 40 - Esquina superior derecha
  {4.0f, -0.5f}     // Ancla 50 - Centro inferior
};

// IDs de las 5 anclas (mantener igual)
const int ANCHOR_IDS[MAX_ANCHORS] = {10, 20, 30, 40, 50};

// ===== VALIDACIÓN DE TAMAÑOS =====
static_assert(sizeof(ANCHOR_POSITIONS)/sizeof(ANCHOR_POSITIONS[0]) == MAX_ANCHORS, 
              "ANCHOR_POSITIONS desfasado de MAX_ANCHORS");
static_assert(sizeof(ANCHOR_IDS)/sizeof(ANCHOR_IDS[0]) == MAX_ANCHORS, 
              "ANCHOR_IDS desfasado de MAX_ANCHORS");

// ===== CONFIGURACIÓN DE VISUALIZACIÓN INDOOR =====
#ifndef PIXELS_PER_M
#define PIXELS_PER_M 50.0           // Más pixels por metro para indoor (mayor zoom)
#endif

// ===== CONFIGURACIÓN DE MEMORIA =====
#ifndef JSON_BUFFER_SIZE
#define JSON_BUFFER_SIZE 2048       // Mantener tamaño de JSON
#endif
#ifndef MQTT_MAX_PACKET_SIZE
#define MQTT_MAX_PACKET_SIZE 2048   // Mantener tamaño MQTT
#endif

// ===== CONFIGURACIÓN DE BAJO CONSUMO (DESHABILITADO PARA PRUEBAS) =====
#define SLEEP_TIMEOUT 600000        // Timeout más largo para debugging indoor (10 min)

// ===== CONFIGURACIÓN DE DEBUG MEJORADA PARA INDOOR =====
#ifndef DEBUG_MODE
#define DEBUG_MODE 1                // Habilitar debug por defecto en indoor
#endif

// ===== CONFIGURACIÓN DE INTERFAZ WEB (HABILITADA PARA MONITOREO) =====
#ifndef ENABLE_WEB_INTERFACE
#define ENABLE_WEB_INTERFACE 1      // Mantener interfaz web para monitoreo
#endif

#endif // CONFIG_INDOOR_H 