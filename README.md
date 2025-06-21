# 🏟️ Sistema de Localización Indoor UWB para Fútbol Sala

**TFG 2024 - Trabajo de Fin de Grado**  
**Autor:** Nicolás García  
**Universidad:** [Tu Universidad]  
**Versión:** v1.0

## 📋 Descripción del Proyecto

Sistema de posicionamiento indoor de alta precisión basado en tecnología **Ultra-Wideband (UWB)** específicamente diseñado para el análisis de rendimiento deportivo en **fútbol sala**. 

El sistema utiliza **5 anclas estratégicamente posicionadas** en una cancha de 40x20m para triangular la posición de jugadores equipados con tags UWB, proporcionando datos precisos de movimiento, velocidad y posicionamiento táctico en tiempo real.

## 🎯 Características del Sistema

### ✅ **Arquitectura Principal**
- **5 Anclas UWB fijas** (ESP32 + DW3000) distribuidas en la cancha
- **Tags móviles** ligeros para jugadores
- **Protocolo TDMA** para coordinación temporal
- **Conectividad WiFi/MQTT** para transmisión de datos
- **Interfaz web** para visualización en tiempo real

### ✅ **Funcionalidades Implementadas**
1. **Localización Triangular** - Posicionamiento basado en distancias UWB
2. **Configuración Centralizada** - Gestión unificada de parámetros
3. **Validación de Hardware** - Verificación de IDs y conexiones
4. **Filtrado de Señales** - Eliminación de mediciones erróneas
5. **Persistencia de Datos** - Almacenamiento de métricas en memoria no volátil
6. **Logging Inteligente** - Sistema de trazas optimizado
7. **Telemetría MQTT** - Transmisión de datos en tiempo real
8. **Diagnóstico Automático** - Detección y reporte de fallos
9. **Recuperación Automática** - Watchdog y reinicio inteligente
10. **Máquina de Estados** - Control robusto del flujo de ejecución
11. **Filtrado Kalman** - Suavizado de trayectorias de movimiento
12. **Detección de Anomalías** - Identificación de mediciones atípicas
13. **Análisis de Zonas** - Segmentación táctica de la cancha
14. **Dashboard Web** - Interfaz de monitorización visual

### ✅ **Especificaciones Técnicas**
- **Precisión objetivo:** <50cm en condiciones reales
- **Frecuencia de muestreo:** 20-40Hz
- **Latencia total:** <200ms
- **Área de cobertura:** Cancha completa 40x20m

## 🏗️ Arquitectura del Sistema

```
Cancha de Fútbol Sala (40m x 20m)
┌─────────────────────────────────────────┐
│ A20(0,20)               A40(40,20)      │
│    ┌─────────────────────────┐          │
│    │                         │          │
│    │        A50(20,10)       │          │
│    │           🎯            │          │
│    │                         │          │
│    └─────────────────────────┘          │
│ A10(0,0)                A30(40,0)       │
└─────────────────────────────────────────┘

A10-A50: Anclas UWB (ESP32+DW3000)
🎯: Tag del jugador (móvil)
```

## 📁 Estructura del Proyecto

```
TFG-UWB/
├── README.md                 # Documentación principal
├── .gitignore               # Protección de credenciales
├── common/                  # Configuración centralizada
│   ├── config.h             # Parámetros del sistema
│   └── secrets.h            # Credenciales de red (no versionado)
├── uwb_anchor_10/           # Ancla posición (0,0)
│   └── anchor_10.ino        # Firmware ancla ID=10
├── uwb_anchor_20/           # Ancla posición (0,20)
│   └── anchor_20.ino        # Firmware ancla ID=20
├── uwb_anchor_30/           # Ancla posición (40,0)
│   └── anchor_30.ino        # Firmware ancla ID=30
├── uwb_anchor_40/           # Ancla posición (40,20)
│   └── anchor_40.ino        # Firmware ancla ID=40
├── uwb_anchor_50/           # Ancla posición (20,10)
│   └── anchor_50.ino        # Firmware ancla ID=50
└── uwb_tag/                 # Tag móvil
    └── tag.ino              # Firmware tag con algoritmos de localización
```

## 🛠️ Hardware Requerido

### **Por Ancla (x5 unidades):**
- ESP32 DevKit v1 o similar
- Módulo DW3000 UWB
- Antena UWB
- Alimentación 5V/2A
- Carcasa protectora IP65

### **Por Tag (x1+ unidades):**
- ESP32 DevKit v1 
- Módulo DW3000 UWB
- Batería LiPo 3.7V/1000mAh
- Carcasa deportiva ligera

### **Infraestructura:**
- Router WiFi 2.4GHz/5GHz
- Servidor MQTT (ej: Mosquitto)
- PC/Servidor para análisis de datos

## 🚀 Instalación y Configuración

### **1. Preparación del Hardware**
```bash
# Conexiones ESP32 <-> DW3000
VCC  -> 3.3V
GND  -> GND  
CS   -> GPIO5
MOSI -> GPIO23
MISO -> GPIO19
CLK  -> GPIO18
IRQ  -> GPIO34
RST  -> GPIO27
```

### **2. Configuración de Software**

#### **Arduino IDE:**
1. Instalar **ESP32 Board Package** (v2.0.0+)
2. Instalar librerías requeridas:
   ```
   - DW3000 (compatible con ESP32)
   - PubSubClient (MQTT)
   - ArduinoJson (v6+)
   - WiFi (incluida con ESP32)
   ```

#### **Configuración de Red:**
1. Editar `common/secrets.h`:
   ```cpp
   #define STA_SSID "Tu_WiFi_SSID"
   #define STA_PASS "Tu_WiFi_Password"
   #define MQTT_SERVER "192.168.1.100"  // IP de tu broker MQTT
   ```

### **3. Compilación y Carga**

#### **Para cada Ancla:**
```bash
# Arduino IDE
1. Abrir carpeta del ancla (ej: uwb_anchor_10/)
2. Compilar sketch (Ctrl+R)
3. Cargar a ESP32 (Ctrl+U)
4. Repetir para las 5 anclas
```

#### **Para el Tag:**
```bash
# Arduino IDE  
1. Abrir uwb_tag/tag.ino
2. Compilar y cargar al ESP32 del tag
```

## 📊 Uso del Sistema

### **1. Secuencia de Inicio**
1. **Alimentar las 5 anclas** (orden indistinto)
2. **Esperar sincronización** (~30 segundos)
3. **Encender tag del jugador**
4. **Verificar conectividad** MQTT/WiFi
5. **Iniciar sesión de entrenamiento**

### **2. Monitorización**
- **Serial Monitor:** Logs detallados de debugging
- **MQTT Topics:** Datos en tiempo real
  - `uwb/tag/position` - Coordenadas X,Y del jugador
  - `uwb/tag/metrics` - Estadísticas de rendimiento
  - `uwb/anchors/status` - Estado de las anclas

### **3. Análisis de Datos**
El sistema genera datos CSV compatibles con:
- **Excel/Google Sheets** - Análisis básico
- **Python/Pandas** - Análisis avanzado  
- **R/MATLAB** - Procesamiento estadístico
- **Tableau/PowerBI** - Visualización profesional

## 🎯 Aplicaciones Deportivas

### **Análisis de Rendimiento:**
- **Distancia recorrida** por jugador y sesión
- **Velocidades máximas** y promedio durante el juego
- **Patrones de aceleración** en sprints y frenadas
- **Tiempo de permanencia** en diferentes zonas de la cancha

### **Análisis Táctico:**
- **Mapas de calor** de posicionamiento de jugadores
- **Trayectorias de movimiento** individual y colectivo
- **Análisis de formaciones** defensivas y ofensivas
- **Estudios de transiciones** entre fases de juego

### **Monitorización de Carga:**
- **Intensidad de movimiento** durante entrenamientos
- **Distribución temporal** de esfuerzos
- **Comparación entre sesiones** de entrenamiento
- **Datos objetivos** para planificación deportiva

## 🔧 Solución de Problemas

### **Problemas Comunes:**

#### **"Ancla no responde"**
```bash
# Verificar:
1. Alimentación estable (5V/2A mínimo)
2. Conexiones DW3000 correctas  
3. ID_PONG único (10,20,30,40,50)
4. Restart automático después de 15s sin actividad
```

#### **"Tag no se localiza"**
```bash
# Verificar:
1. Mínimo 3 anclas operativas simultáneamente
2. Tag dentro del área de cobertura
3. Sin obstáculos metálicos grandes
4. RSSI > -90dBm en al menos 3 anclas
```

#### **"Coordenadas erróneas"**
```bash
# Verificar:
1. Posiciones de anclas correctas en config.h
2. Calibración de cancha (40x20m)
3. Sincronización temporal correcta
4. Filtros Kalman activos
```

## 📈 Objetivos del TFG

### **Métricas de Precisión Objetivo:**
- 🎯 **Error < 50cm** en condiciones reales de juego
- 🎯 **Latencia < 200ms** para análisis en tiempo real
- 🎯 **Cobertura 100%** de la cancha sin zonas muertas
- 🎯 **Disponibilidad > 95%** durante sesiones de entrenamiento

### **Funcionalidades a Desarrollar:**
- 🔄 **Protocolo TDMA eficiente** para múltiples dispositivos
- 🔄 **Algoritmos de filtrado** para datos de movimiento deportivo
- 🔄 **Sistema de zonas deportivas** para análisis táctico
- 🔄 **Interfaz de visualización** para entrenadores

## 👨‍💻 Desarrollo del Proyecto

Este es un **Trabajo de Fin de Grado** en desarrollo activo.

### **Información del Proyecto:**
- **Autor:** Nicolás García
- **GitHub:** [@nicogarrr](https://github.com/nicogarrr)
- **Universidad:** [Tu Universidad]
- **Año académico:** 2024

### **Estado Actual:**
- 🟢 **Diseño del sistema** - Completado
- 🟢 **Implementación hardware** - En desarrollo
- 🟡 **Algoritmos de localización** - En progreso
- 🟡 **Interfaz de usuario** - Planificado
- 🔴 **Validación experimental** - Pendiente

## 📄 Licencia

Este proyecto está desarrollado para fines académicos y de investigación.

## 🏆 Agradecimientos

- **Tutor TFG:** [Nombre del tutor]
- **Universidad:** [Tu Universidad]
- **Departamento:** [Tu Departamento]
- **Área:** Sistemas de Telecomunicaciones

---

**⚽ Innovación tecnológica aplicada al deporte ⚽** 