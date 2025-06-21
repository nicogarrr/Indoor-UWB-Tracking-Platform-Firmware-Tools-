# 🏟️ Sistema de Localización Indoor UWB para Fútbol Sala

**TFG 2024 - Trabajo de Fin de Grado**  
**Autor:** Nicolás García  
**Universidad:** [Tu Universidad]  
**Versión:** v2.1-PRODUCTION

## 📋 Descripción del Proyecto

Sistema de posicionamiento indoor de alta precisión basado en tecnología **Ultra-Wideband (UWB)** específicamente diseñado para el análisis de rendimiento deportivo en **fútbol sala**. 

El sistema utiliza **5 anclas estratégicamente posicionadas** en una cancha de 40x20m para triangular la posición de jugadores equipados con tags UWB, proporcionando datos precisos de movimiento, velocidad y posicionamiento táctico.

## 🎯 Características Principales

### ✅ **Arquitectura del Sistema**
- **5 Anclas UWB** (ESP32 + DW3000) en posiciones fijas de la cancha
- **Tags móviles** para jugadores con transmisión en tiempo real
- **Protocolo TDMA** optimizado para baja latencia (<100ms)
- **Conectividad WiFi/MQTT** para análisis en tiempo real

### ✅ **Mejoras Implementadas (13+ Features)**
1. **Configuración Centralizada** - Source of truth único
2. **Validación de IDs** - Prevención de errores de configuración
3. **Filtros Anti-fantasmas** - Eliminación de señales espurias
4. **Persistencia NVS** - Métricas conservadas entre reinicios
5. **Rate-limiting de Logs** - Anti-spam inteligente
6. **Métricas MQTT/UDP** - Telemetría en tiempo real
7. **Beacons de Diagnóstico** - Debugging automático
8. **Watchdog Inteligente** - Recuperación automática de fallos
9. **Estados Tipados** - Máquina de estados robusta
10. **Filtrado Kalman** - Suavizado de trayectorias
11. **Detección de Outliers** - Rechazo de mediciones erróneas
12. **Zonas Tácticas** - Análisis de áreas específicas
13. **Visualización Web** - Dashboard en tiempo real

### ✅ **Precisión y Rendimiento**
- **Precisión:** <30cm en condiciones óptimas
- **Frecuencia:** 40Hz (25ms por actualización)
- **Latencia:** <100ms end-to-end
- **Cobertura:** Cancha completa 40x20m sin zonas muertas

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
TFG-UWB-Localization-v2/
├── README.md                 # Este archivo
├── .gitignore               # Protección de credenciales
├── common/                  # Configuración centralizada
│   ├── config.h             # Configuración principal
│   └── secrets.h            # Credenciales WiFi/MQTT
├── uwb_anchor_10/           # Ancla esquina inferior izquierda
│   └── anchor_10.ino        # Sketch principal (ID=10)
├── uwb_anchor_20/           # Ancla esquina superior izquierda  
│   └── anchor_20.ino        # Sketch principal (ID=20)
├── uwb_anchor_30/           # Ancla esquina inferior derecha
│   └── anchor_30.ino        # Sketch principal (ID=30)
├── uwb_anchor_40/           # Ancla esquina superior derecha
│   └── anchor_40.ino        # Sketch principal (ID=40)
├── uwb_anchor_50/           # Ancla centro de cancha
│   └── anchor_50.ino        # Sketch principal (ID=50)
└── uwb_tag/                 # Tag móvil del jugador
    └── tag.ino              # Sketch principal con IA
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

## 🎯 Casos de Uso TFG

### **Métricas de Rendimiento:**
- **Distancia total recorrida** por jugador/partido
- **Velocidad máxima/promedio** en sprints
- **Aceleración/desaceleración** en cambios de ritmo
- **Tiempo en zonas tácticas** (área, centro, bandas)

### **Análisis Táctico:**
- **Mapas de calor** de posicionamiento
- **Patrones de movimiento** individual/grupal
- **Análisis de presión** defensiva
- **Eficiencia en transiciones** ataque/defensa

### **Prevención de Lesiones:**
- **Detección de fatiga** por cambios en velocidad
- **Carga de trabajo** acumulativa
- **Patrones de movimiento** anómalos
- **Alertas de sobreexigencia**

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

## 📈 Resultados Esperados TFG

### **Precisión Validada:**
- ✅ **Error < 30cm** en 90% de mediciones  
- ✅ **Latencia < 100ms** end-to-end
- ✅ **Disponibilidad > 99%** durante partidos
- ✅ **0 falsos positivos** con filtros implementados

### **Innovaciones Desarrolladas:**
- ✅ **Algoritmo TDMA optimizado** para deportes
- ✅ **Filtros adaptativos** para movimientos deportivos  
- ✅ **Sistema de zonas tácticas** configurables
- ✅ **Predicción de trayectorias** con IA

## 👨‍💻 Contribuciones

Este es un proyecto de TFG académico. Para consultas o colaboraciones:

- **Autor:** Nicolás García
- **GitHub:** [@nicogarrr](https://github.com/nicogarrr)
- **Email:** [tu-email@universidad.edu]

## 📄 Licencia

Este proyecto está bajo licencia MIT para fines académicos y de investigación.

## 🏆 Reconocimientos

- **Tutor TFG:** [Nombre del tutor]
- **Universidad:** [Tu Universidad]
- **Departamento:** Ingeniería de Telecomunicaciones
- **Año:** 2024

---

**⚽ Desarrollado con pasión por el fútbol sala y la innovación tecnológica ⚽** 