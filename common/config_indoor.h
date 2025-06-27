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
  // DIMENSIONES REALES EXACTAS DEL SALÓN
  constexpr float courtLength = 3.45f;     // 3.45 metros de ancho (medida real corregida)
  constexpr float courtWidth = 5.40f;      // 5.40 metros de largo (medida real corregida)
  constexpr float maxPlayerSpeed = 2.5f;   // Velocidad máxima en salón (caminar/trotar)
  
  // Umbrales de filtrado ajustados para salón más pequeño
  constexpr float maxRangeThreshold = 8.0f; // Máximo 8m (diagonal ~6.4m)
  constexpr float minRangeThreshold = 0.15f; // Mínimo 15cm (más preciso)
  
  // TDMA optimizado para salón compacto (menor latencia)
  constexpr int tdmaCycleMs = 200;          // Ciclo más rápido para espacio pequeño
  constexpr int tdmaSlotDurationMs = 40;    // Slots muy cortos
  constexpr int responseTimeout = 60;       // Timeout reducido
  constexpr int roundDelay = 20;            // Delay mínimo
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

// ===== ZONAS INDOOR PARA SALÓN COMPACTO (3.45x5.40m) =====
#define NUM_ZONES 4                 // Zonas principales del salón compacto

struct ZoneConfig {
  float x, y, radius;
  unsigned long minStayTime;
  const char* name;
};

// ZONAS OPTIMIZADAS PARA LA DISTRIBUCIÓN REAL DE ANCLAS (3.45x5.40m)
const ZoneConfig INDOOR_ZONES[NUM_ZONES] = {
  {0.8f, 3.8f, 0.7f, 750, "Zona_Sofa"},        // Cerca de anclas izquierdas (buena cobertura)
  {2.8f, 1.5f, 0.8f, 500, "Zona_TV"},          // Entre ambos lados (cobertura equilibrada)
  {1.7f, 2.5f, 1.0f, 1000, "Zona_Centro"},     // Centro geométrico (máxima precisión)
  {1.2f, 0.8f, 0.6f, 500, "Zona_Entrada"}      // Cerca de ancla derecha inferior
};

// ===== POSICIONES DE ANCLAS PARA SALÓN REAL (3.45x5.40m) =====
// Distribución estratégica optimizada para máxima cobertura en espacio compacto
  const float ANCHOR_POSITIONS[MAX_ANCHORS][2] = {
    {0.0f, 1.10f},      // Ancla 10 - Esquina inferior izquierda (0, 1.10)
    {0.0f, 2.25f},     // Ancla 20 - Esquina superior izquierda (0, 2.25)  
    {0.0f, 4.55f},     // Ancla 30 - Esquina inferior derecha (0.30, 0.66), 4.55
    {3.45f, 0.0f},    // Ancla 40 - Esquina superior derecha (6.30, 3.50)
    {3.45f, 0.66f}     // Ancla 50 - Centro exacto del salón (3.45, 0.66)
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
#define PIXELS_PER_M 80.0           // Más píxeles por metro para salón pequeño (máximo detalle)
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