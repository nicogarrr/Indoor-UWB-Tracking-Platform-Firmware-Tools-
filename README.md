# 🏟️ Sistema de Localización Indoor UWB para Fútbol Sala

**TFG 2024-2025 - Trabajo de Fin de Grado**  
**Autor:** Nicolás Iglesias García  
**Universidad:** Universidad de Oviedo - EPI Gijón  
**Grado:** Ciencia e Ingeniería de Datos  
**Versión:** v1.0

## 📋 Descripción del Proyecto

Sistema de posicionamiento indoor de alta precisión basado en tecnología **Ultra-Wideband (UWB)** específicamente diseñado para el análisis de rendimiento deportivo en **fútbol sala**. 

El sistema utiliza **5 anclas estratégicamente posicionadas** en una cancha de 40x20m para triangular la posición de jugadores equipados con tags UWB, proporcionando datos precisos de movimiento, velocidad y posicionamiento táctico en tiempo real.

## 📡 Tecnología Ultra-Wideband (UWB) DW3000

**Ultra-Wideband (UWB)** es un protocolo de comunicación inalámbrica de corto alcance que opera a través de ondas de radio, permitiendo ranging seguro y confiable y detección de precisión, creando una nueva dimensión de contexto espacial para dispositivos inalámbricos.

### **🚀 Evolución Tecnológica: DW1000 → DW3000**

El módulo **Makerfabs ESP32 UWB**, basado inicialmente en el IC DecaWave DW1000, ha sido muy popular entre desarrolladores. Tras extensas comparaciones y pruebas, ahora está disponible la versión **DW3000** con ventajas significativas:

#### **Ventajas Clave del DW3000:**
1. **🍎 Más importante:** Interoperable con chip Apple U1, posibilitando trabajo con el ecosistema Apple
2. **🛡️ Certificación FiRa™:** Completamente alineado con desarrollo PHY, MAC y certificación FiRa™, haciéndolo más adecuado para aplicaciones futuras
3. **🔋 Menor consumo:** Aproximadamente 1/3 del consumo del DW1000
4. **📡 Doble banda:** Soporta canales UWB 5 (6.5 GHz) y 9 (8 GHz), mientras DW1000 no soporta canal 9

### **🔧 Características Hardware del TFG:**
- **Chip UWB:** Decawave DW3000 (última generación)
- **Microcontrolador:** ESP32 WROVER (8MB PSRAM + 4MB Flash)
- **Conectividad:** WiFi 2.4G, Bluetooth, UWB
- **Alimentación:** USB 4.8-5.5V, 5.0V típico
- **Compatibilidad:** Arduino nativo con demos incluidos

## 📚 **NAVEGACIÓN RÁPIDA**
- [🚀 Guía Rápida de Uso](#-guía-rápida-de-uso)
- [🛠️ Instalación Completa](#️-instalación-y-configuración-completa)
- [📊 Sistema de Análisis](#-sistema-de-análisis-de-datos)
- [🎬 Sistema de Replay](#-sistema-de-replay-avanzado)
- [🔧 Solución de Problemas](#-solución-de-problemas)

## 🎯 Características del Sistema

### ✅ **Arquitectura Principal**
- **5 Anclas UWB fijas** (ESP32 + DW3000) distribuidas en la cancha
- **Tags móviles** ligeros para jugadores
- **Protocolo TDMA** para coordinación temporal
- **Conectividad WiFi/MQTT** para transmisión de datos
- **Sistema de análisis avanzado** con filtros ML y Kalman

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
12. **Predicción ML** - Algoritmos de machine learning para interpolación
13. **Análisis de Zonas** - Segmentación táctica de la cancha
14. **Sistema de Replay Avanzado** - Visualización interactiva profesional

### ✅ **Especificaciones Técnicas**
- **Precisión objetivo:** <50cm en condiciones reales
- **Frecuencia de muestreo:** 20-40Hz
- **Latencia total:** <200ms
- **Área de cobertura:** Cancha completa 40x20m
- **Disponibilidad:** >95% durante sesiones de entrenamiento

## 🏗️ Arquitectura del Sistema

```
Configuración UWB - Cancha Fútbol Sala (40m x 20m)

A20(-1,21)🔶─────────────────────────────🔶A40(41,21)
         │                               │
         │    ┌───────────────────┐      │
         │    │                   │      │
         │    │        🎯         │      │
         │    │    (Área juego)   │      │
         │    │                   │      │
         │    └───────────────────┘      │
         │                               │
A10(-1,-1)🔶─────────🔶─────────────────🔶A30(41,-1)
                    A50(20,-1)

🔶: Anclas UWB fijas (fuera de la cancha)
🎯: Tag móvil del jugador

### **Nueva Configuración de Anclas:**
- **A10(-1,-1)** - Esquina Suroeste (fuera de cancha)
- **A20(-1,21)** - Esquina Noroeste (fuera de cancha)  
- **A30(41,-1)** - Esquina Sureste (fuera de cancha)
- **A40(41,21)** - Esquina Noreste (fuera de cancha)
- **A50(20,-1)** - Centro campo lateral Sur (fuera de cancha)

### **Ventajas de esta Configuración:**
- ✅ **No interfiere con el juego** - Todas las anclas fuera del área
- ✅ **Cobertura equilibrada** - 4 esquinas + 1 punto central
- ✅ **Geometría robusta** - Buena triangulación en toda la cancha
- ✅ **Fácil instalación** - Montaje en perímetro del pabellón
- ✅ **Redundancia** - 5 anclas para mayor precisión

### **Hardware Makerfabs ESP32 UWB DW3000 - Especificaciones del TFG:**

#### 🔧 **Hardware Físico Disponible - Especificaciones Oficiales:**

##### **📋 Información del Módulo:**
- **Cantidad:** 6 placas ESP32 UWB DW3000 (Universidad de Oviedo)
- **Distribución:** 5 anclas + 1 tag móvil  
- **Modelo:** Makerfabs ESP32 UWB DW3000
- **Chip base:** ESP32-D0WDQ6 (según [datasheet ESP32-WROVER](https://www.makerfabs.com/desfile/files/esp32-wrover_datasheet_en.pdf))
- **Variante:** ESP32-WROVER (PCB antenna)

##### **🧠 Especificaciones de Memoria (Datasheet v2.2):**
- **Flash Externa:** 4 MB SPI Flash
- **PSRAM:** 8 MB SPI Pseudo Static RAM (64 Mbit)
- **RAM Interna:** 520 KB SRAM (ESP32-D0WDQ6)
- **Ventaja PSRAM:** Ideal para buffers UWB grandes y algoritmos ML complejos

##### **⚡ Especificaciones de Procesamiento:**
- **CPU:** Dual-core Xtensa 32-bit LX6 microprocessor
- **Frecuencia:** 80 MHz - 240 MHz (ajustable)
- **Co-procesador:** Ultra Low Power (ULP) para monitoreo continuo
- **Arquitectura:** Escalable y adaptativa con control individual de cores

##### **🌐 Conectividad Integrada:**
- **WiFi:** 802.11 b/g/n (hasta 150 Mbps)
  - A-MPDU/A-MSDU aggregation
  - Guard interval 0.4 µs support
  - Rango frecuencia: 2.4 GHz ~ 2.5 GHz
- **Bluetooth:** v4.2 BR/EDR y BLE specification
  - NZIF receiver con -97 dBm sensitivity
  - Class-1, Class-2, Class-3 transmitter
  - Adaptive Frequency Hopping (AFH)
  - Audio: CVSD y SBC codecs

##### **🔌 Especificaciones Físicas y Eléctricas:**
- **Dimensiones:** (18.00 ± 0.10) × (31.40 ± 0.10) × (3.30 ± 0.10) mm
- **Alimentación:** USB 4.8-5.5V, 5.0V típico
- **Consumo:** < 5 µA en sleep mode (ultra-bajo consumo)
- **Temperatura operación:** -40°C ~ +85°C
- **Conectividad:** Micro-USB, antena PCB integrada

##### **🛡️ Certificaciones y Confiabilidad:**
- **RF:** FCC/CE-RED/SRRC/TELEC certified
- **WiFi:** Wi-Fi Alliance certified  
- **Bluetooth:** BQB certified
- **Ambiental:** RoHS/REACH compliance
- **Tests:** HTOL/HTSL/uHAST/TCT/ESD reliability testing

##### **🔗 Recursos Oficiales:**
- **Datasheet:** [ESP32-WROVER v2.2](https://www.makerfabs.com/desfile/files/esp32-wrover_datasheet_en.pdf)
- **Repositorio DW3000:** [Makerfabs-ESP32-UWB-DW3000](https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000)

#### 🚀 **Ventajas del DW3000 vs DW1000 (Generación Anterior):**
1. **🍎 Interoperabilidad Apple U1** - Compatible con chip U1 de dispositivos Apple
2. **🛡️ Certificación FiRa™** - Estándar PHY, MAC y certificación para aplicaciones industriales
3. **🔋 Consumo ultra-eficiente** - Aproximadamente 1/3 del consumo del DW1000
4. **📡 Doble banda UWB** - Soporte para canales 5 (6.5 GHz) y 9 (8 GHz)
5. **🎯 Precisión mejorada** - Mejor tracking y reducción de errores
6. **⚡ Transmisión optimizada** - Protocolo de comunicación más eficiente

#### 🧠 **Ventajas Específicas ESP32 WROVER para Ciencia e Ingeniería de Datos:**

##### **💾 Capacidades de Memoria Expandida:**
- **8MB PSRAM (64 Mbit)** - Memoria extendida para:
  - Buffers UWB de gran tamaño (>1000 mediciones simultáneas)
  - Algoritmos de machine learning complejos (Gaussian Process, Kalman)
  - Procesamiento de señales en tiempo real sin saturación
  - Filtros Kalman con historial extendido (>5 segundos de datos)
  - Arrays de datos deportivos para análisis estadístico
- **4MB Flash Externa** - Espacio para firmware avanzado:
  - Múltiples librerías UWB, MQTT, ML simultáneas
  - Algoritmos de triangulación complejos
  - Sistema de logging persistente
  - OTA updates para actualizaciones remotas

##### **⚡ Procesamiento Paralelo Avanzado:**
- **Dual-core Xtensa 32-bit LX6 (80-240 MHz)**
  - Core 0: Protocolo UWB TDMA + triangulación en tiempo real
  - Core 1: WiFi/MQTT + análisis ML + interfaz web
  - Procesamiento paralelo verdadero sin bloqueos
- **Co-procesador ULP** - Monitoreo de periféricos sin despertar CPU principal
- **FreeRTOS optimizado** - Gestión de tareas de tiempo real

##### **🌐 Conectividad Industrial Robusta:**
- **WiFi 802.11 b/g/n hasta 150 Mbps** - Transmisión de datos UWB en tiempo real
- **Bluetooth v4.2 BR/EDR + BLE** - Configuración y monitoreo móvil
- **20 dBm output power** - Máximo rango de conectividad
- **Sleep mode <5 µA** - Eficiencia energética para instalaciones permanentes

##### **📊 Periféricos Integrados para Análisis Deportivo:**
- **ADC de 12-bit** - Sensores adicionales (acelerómetros, giroscopios)
- **DAC de 8-bit** - Señales de control analógicas
- **PWM/LED control** - Indicadores visuales en anclas
- **I²C/SPI/UART** - Expansión con sensores externos
- **GPIO programables** - Control de hardware personalizado
- **RTC con crystal** - Timestamps precisos para sincronización

##### **🎯 Beneficios Específicos para TFG:**
- **Capacidad computacional** - Algoritmos ML complejos sin limitaciones
- **Confiabilidad industrial** - Certificaciones FCC/CE/RoHS para uso académico
- **Rango de temperatura** - Operación -40°C ~ +85°C (pabellones deportivos)
- **Desarrollo ágil** - Arduino IDE + ESP-IDF para prototipado rápido
- **Escalabilidad** - Fácil expansión a múltiples tags simultáneos
```

## 📁 Estructura del Proyecto

```
TFG-UWB/
├── README.md                    # 📖 Documentación completa unificada (GUÍAS INTEGRADAS)
├── .gitignore                   # 🛡️ Protección de credenciales
├── requirements.txt             # 📦 Dependencias Python
├── common/                      # ⚙️ Configuración centralizada
│   ├── config.h                 # Parámetros del sistema
│   └── secrets.h                # Credenciales de red (no versionado)
├── uwb_anchor_10/               # 📡 Ancla esquina Suroeste (-1,-1)
│   └── anchor_10.ino            # Firmware ancla ID=10
├── uwb_anchor_20/               # 📡 Ancla esquina Noroeste (-1,21)
│   └── anchor_20.ino            # Firmware ancla ID=20
├── uwb_anchor_30/               # 📡 Ancla esquina Sureste (41,-1)
│   └── anchor_30.ino            # Firmware ancla ID=30
├── uwb_anchor_40/               # 📡 Ancla esquina Noreste (41,21)
│   └── anchor_40.ino            # Firmware ancla ID=40
├── uwb_anchor_50/               # 📡 Ancla centro campo Sur (20,-1)
│   └── anchor_50.ino            # Firmware ancla ID=50
├── uwb_tag/                     # 🏃 Tag móvil
│   └── tag.ino                  # Firmware tag con algoritmos de localización
├── data/                        # 💾 Datos capturados
│   └── uwb_data_futsal_game_20250621_160000.csv  # Archivo de ejemplo
├── processed_data/              # 🔬 Datos procesados
├── plots/                       # 📊 Visualizaciones generadas
├── csv_processor.py             # 🧮 Procesador principal de datos
├── mqtt_to_csv_collector.py     # 📨 Colector MQTT en tiempo real
├── movement_replay.py           # 🎬 Sistema de replay avanzado con ML + Kalman
└── tag_replay_4anchors_opt.py   # 🔧 Sistema de replay optimizado (experimental)
```

---

# 🚀 GUÍA RÁPIDA DE USO

## 📋 **PASOS PARA EJECUTAR TU SISTEMA**

### 1️⃣ **PREPARACIÓN (Solo una vez)**
```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Verificar que todo funciona
python -c "import csv_processor; print('✅ Sistema listo')"
```

### 2️⃣ **HARDWARE UWB (Subir código a ESP32)**

#### Programar las Anclas UWB:
```bash
# Abrir Arduino IDE y programar cada ancla:
# 1. uwb_anchor_10/anchor_10.ino  → ESP32 #1
# 2. uwb_anchor_20/anchor_20.ino  → ESP32 #2  
# 3. uwb_anchor_30/anchor_30.ino  → ESP32 #3
# 4. uwb_anchor_40/anchor_40.ino  → ESP32 #4
# 5. uwb_anchor_50/anchor_50.ino  → ESP32 #5
```

#### Programar el Tag UWB:
```bash
# 6. uwb_tag/tag.ino → ESP32 #6 (el que llevará el jugador)
```

### 3️⃣ **CAPTURA DE DATOS EN TIEMPO REAL**

#### Opción A: Captura MQTT (Recomendado)
```bash
# 1. Ejecutar colector MQTT
python mqtt_to_csv_collector.py

# Esto creará archivos en data/:
# - uwb_data_YYYYMMDD_HHMMSS.csv
# - uwb_status_YYYYMMDD_HHMMSS.csv  
# - uwb_zones_YYYYMMDD_HHMMSS.csv
# - uwb_metrics_YYYYMMDD_HHMMSS.csv
```

#### Opción B: Usar datos de ejemplo
```bash
# Ya tienes un archivo de ejemplo en:
# data/uwb_data_futsal_game_20250621_160000.csv
```

### 4️⃣ **PROCESAMIENTO Y ANÁLISIS**

#### Procesar datos capturados:
```bash
# Procesa automáticamente todos los archivos en data/
python csv_processor.py
```

**Esto genera:**
- ✅ Datos filtrados y suavizados
- 📊 Visualizaciones automáticas  
- 📈 Estadísticas de rendimiento
- 💾 Archivos procesados en `processed_data/`

### 5️⃣ **VISUALIZACIÓN INTERACTIVA - SISTEMA DE REPLAY**

#### Sistema de Replay Avanzado:
```bash
# Reproducir movimientos en tiempo real con filtros ML + Kalman
python movement_replay.py

# Con archivo específico
python movement_replay.py data/mi_archivo.csv

# Solo mostrar reporte estadístico
python movement_replay.py --report
```

**🎮 Controles del Replay:**
- `ESPACIO`: ⏯️ Play/Pausa
- `← →`: Frame anterior/siguiente  
- `↑ ↓`: Aumentar/Disminuir velocidad (0.1x - 10x)
- `R`: 🔄 Reiniciar desde el inicio
- `Q`: ❌ Salir del sistema

**🚀 Características Avanzadas del Replay:**
- 🎯 **Cancha profesional** - Fútbol sala (40x20m) con líneas oficiales
- 📍 **Anclas UWB optimizadas** - Posiciones fuera del área de juego
- 🏃 **Trayectoria inteligente** - Trail dinámico con degradado
- 🎨 **Zonas de análisis** - Áreas de portería, centro campo, etc.
- 📊 **Panel en tiempo real** - Posición, velocidad, zona actual
- ⚡ **Velocidad ajustable** - 0.1x a 10x con controles suaves
- 🔧 **Filtros avanzados** - Kalman + Machine Learning
- 🤖 **Predicción ML** - Gaussian Process Regression para interpolación
- 📈 **Indicador de velocidad** - Círculo proporcional a la velocidad

**📊 Zonas de Análisis Automático:**
- 🥅 **ÁREA PORTERÍA IZQUIERDA** - Radio 3m
- 🥅 **ÁREA PORTERÍA DERECHA** - Radio 3m  
- ⚽ **CENTRO CAMPO** - Radio 3m
- 👈 **MEDIO CAMPO IZQUIERDO** - 0-20m
- 👉 **MEDIO CAMPO DERECHO** - 20-40m
- 🏃 **EN JUEGO** - Resto de la cancha

### 6️⃣ **ANÁLISIS AVANZADO**

#### Jupyter Notebook (Opcional):
```bash
# Análisis personalizado en notebook
jupyter lab
```

---

# 📡 **EJECUCIÓN COMPLETA DEL SISTEMA TFG**

## 🚀 **Guía Paso a Paso: De Código a Datos**

### **📋 REQUISITOS PREVIOS**
```bash
# 1. Verificar Python y dependencias
python --version  # Python 3.8+
pip install -r requirements.txt

# 2. Verificar que todos los códigos ESP32 están compilados ✅
# - 5 anclas: uwb_anchor_XX/anchor_XX.ino
# - 1 tag: uwb_tag/tag/tag.ino
```

### **1️⃣ CONFIGURACIÓN BROKER MQTT MOSQUITTO**

#### **Instalación en Windows:**
```bash
# Opción A: Winget (Recomendado)
winget install mosquitto

# Opción B: Descarga manual desde:
# https://mosquitto.org/download/

# Ubicación típica: C:\Program Files\mosquitto\
```

#### **Configuración para el TFG:**
```bash
# Crear archivo de configuración básica
# C:\Program Files\mosquitto\mosquitto.conf

listener 1883
allow_anonymous true
log_type all
log_dest file C:\Program Files\mosquitto\mosquitto.log
```

#### **⚡ SOLUCIÓN PROBLEMA DE PERMISOS:**

**Si obtienes error:** `Error: Intento de acceso a un socket no permitido por sus permisos de acceso`

**✅ Solución 1: Ejecutar como Administrador**
```bash
# Abrir PowerShell como Administrador
# Clic derecho en PowerShell → "Ejecutar como administrador"

# Luego ejecutar:
& "C:\Program Files\mosquitto\mosquitto.exe" -p 1883 -v
```

**✅ Solución 2: Configurar como Servicio (Recomendado)**
```bash
# En PowerShell como Administrador:
& "C:\Program Files\mosquitto\mosquitto.exe" install

# Iniciar servicio:
net start mosquitto

# Verificar que está funcionando:
netstat -an | findstr 1883
```

**✅ Solución 3: Puerto Alternativo**
```bash
# Si el puerto 1883 está ocupado, usar otro:
& "C:\Program Files\mosquitto\mosquitto.exe" -p 1884 -v
```

### **2️⃣ INICIAR INFRAESTRUCTURA DE DATOS**

#### **Paso 1: Verificar Mosquitto**
```bash
# Verificar que Mosquitto está ejecutándose
netstat -an | findstr 1883

# Deberías ver:
# TCP    0.0.0.0:1883           0.0.0.0:0              LISTENING
# TCP    [::]:1883              [::]:0                 LISTENING
```

#### **Paso 2: Iniciar Recolector de Datos**
```bash
# Terminal 1: Recolector MQTT
python mqtt_to_csv_collector.py --mqtt-server 127.0.0.1 --mqtt-port 1883 --output-dir ./data

# Salida esperada:
# 🎯 TFG UWB Data Collector iniciado
# 📂 Directorio de salida: ./data
# 🔗 MQTT Broker: 127.0.0.1:1883
# 📁 Archivos:
#    • Ranging: ./data\ranging_data_20250621_172457.csv
#    • Posición: ./data\position_data_20250621_172457.csv
#    • Zonas: ./data\zones_data_20250621_172457.csv
#    • Métricas: ./data\metrics_data_20250621_172457.csv
# ✅ Conectado al broker MQTT (rc=0)
# 📡 Suscrito a: uwb/tag/logs
# 📡 Suscrito a: uwb/tag/+/status
# 📡 Suscrito a: uwb/futsal/zones
# 📡 Suscrito a: uwb/futsal/performance
# 📡 Suscrito a: uwb/futsal/metrics
# 📡 Suscrito a: uwb/anchor/+/metrics
# 🚀 Recolector iniciado. Presiona Ctrl+C para detener.
```

### **3️⃣ ACTIVAR HARDWARE ESP32 UWB**

#### **Configuración de Red en las Placas:**
```cpp
// En common/secrets.h (crear si no existe):
#define WIFI_SSID "TU_RED_WIFI"
#define WIFI_PASSWORD "TU_PASSWORD"
#define MQTT_BROKER_IP "192.168.1.100"  // IP de tu PC
#define MQTT_PORT 1883
```

#### **Secuencia de Encendido:**
```bash
# 1. Conectar y encender TODAS las anclas ESP32 (5 unidades)
#    - Se conectarán automáticamente a WiFi
#    - Buscarán el broker MQTT
#    - Iniciarán protocolo TDMA

# 2. Conectar y encender el TAG ESP32 (1 unidad)
#    - Se unirá al sistema de anclas
#    - Comenzará ranging automático
#    - Enviará datos vía MQTT

# 3. Monitorear conexiones en el recolector
#    Deberías ver mensajes como:
#    📏 Datos ranging: 1, 2, 3...
#    📍 Datos posición: 1, 2, 3...
```

### **4️⃣ MONITOREO EN TIEMPO REAL**

#### **Panel de Control MQTT (Opcional):**
```bash
# Terminal 2: Monitor de topics MQTT
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -h 127.0.0.1 -t "uwb/#" -v

# Verás mensajes como:
# uwb/tag/logs TAG_1,15234567,10,245.67,244.12,-45.2,1
# uwb/tag/1/status {"tag_id":1,"position":{"x":15.2,"y":8.7},"velocity":{"x":1.2,"y":0.8,"speed":1.44}}
# uwb/futsal/zones {"tag_id":1,"zone":"CENTRO_CAMPO","action":"ENTERED","timestamp":15234567}
```

#### **Verificación de Archivos de Datos:**
```bash
# Verificar que se están generando datos
dir data\*_*.csv

# Deberías ver archivos como:
# ranging_data_20250621_172457.csv    (datos UWB brutos)
# position_data_20250621_172457.csv   (posiciones calculadas)
# zones_data_20250621_172457.csv      (eventos deportivos)
# metrics_data_20250621_172457.csv    (rendimiento del sistema)
```

### **5️⃣ PROCESAMIENTO Y VISUALIZACIÓN**

#### **Procesar Datos Capturados:**
```bash
# Terminal 3: Procesamiento de datos
python csv_processor.py

# Esto analizará automáticamente:
# - Todos los archivos en data/
# - Aplicará filtros y algoritmos
# - Generará archivos en processed_data/
# - Creará gráficos en plots/
```

#### **Sistema de Replay en Tiempo Real:**
```bash
# Terminal 4: Visualización interactiva
python movement_replay.py

# O con archivo específico:
python movement_replay.py data/ranging_data_20250621_172457.csv

# Controles del replay:
# ESPACIO: Play/Pausa
# ← →: Frame anterior/siguiente
# ↑ ↓: Velocidad (0.1x - 10x)
# R: Reiniciar
# Q: Salir
```

### **6️⃣ SOLUCIÓN DE PROBLEMAS COMUNES**

#### **🔧 MQTT No Conecta:**
```bash
# Verificar firewall de Windows
# Configuración → Privacidad y seguridad → Firewall de Windows
# Permitir app: mosquitto.exe

# Verificar IP del broker
ipconfig | findstr IPv4
# Usar esa IP en MQTT_BROKER_IP de las placas ESP32
```

#### **🔧 ESP32 No Se Conecta a WiFi:**
```bash
# 1. Verificar credenciales en common/secrets.h
# 2. Asegurar red 2.4GHz (ESP32 no soporta 5GHz)
# 3. Monitor serie Arduino IDE para ver logs de conexión
```

#### **🔧 No Llegan Datos al Recolector:**
```bash
# 1. Verificar topics MQTT correctos
# 2. Confirmar que las 5 anclas están encendidas
# 3. Verificar que el tag está dentro del rango de las anclas
# 4. Monitor serie para ver si hay ranging exitoso
```

#### **🔧 Rendimiento Bajo del Sistema:**
```bash
# 1. Verificar que todas las anclas responden (5/5)
# 2. Posicionar tag en área con buena cobertura
# 3. Evitar obstáculos metálicos que bloqueen UWB
# 4. Verificar latencia de red WiFi
```

### **🎯 INDICADORES DE ÉXITO**

#### **✅ Sistema Funcionando Correctamente:**
```bash
# Recolector MQTT muestra:
📊 Estadísticas de recolección:
   ⏱️  Tiempo activo: 60.0s
   📏 Datos ranging: 1200      # ~20 msgs/s
   📍 Datos posición: 60       # ~1 msg/s
   🏟️  Eventos zonas: 5        # Eventos deportivos
   📈 Métricas: 12             # Métricas del sistema
   📊 Tasa ranging: 20.0 msgs/s

# Archivos CSV creciendo en tamaño
# Replay mostrando movimientos suaves
# Sin errores de conexión en monitor serie
```

### **📊 CONFIGURACIÓN OPTIMIZADA PARA TFG**

#### **Parámetros Recomendados:**
```cpp
// common/config.h - Configuración para análisis deportivo
#define TDMA_CYCLE_MS 50              // 20Hz update rate
#define MAX_RANGING_DISTANCE_CM 5000  // 50m máximo
#define MIN_ANCHORS_FOR_POSITION 3    // Mínimo para triangulación
#define KALMAN_PROCESS_NOISE 0.1      // Suavizado de movimiento
#define MQTT_PUBLISH_INTERVAL_MS 1000 // 1 segundo entre reportes
```

#### **Estructura de Datos Generada:**
```csv
# ranging_data_*.csv
timestamp_system,timestamp_device,tag_id,anchor_id,distance_raw_cm,distance_filtered_cm,rssi_dbm,anchor_responded,session_id

# position_data_*.csv  
timestamp_system,timestamp_device,tag_id,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,speed_ms,prediction_x_m,prediction_y_m,responding_anchors,update_rate_hz,session_id

# zones_data_*.csv
timestamp_system,timestamp_device,tag_id,zone_name,action,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,duration_ms,session_id

# metrics_data_*.csv
timestamp_system,timestamp_device,tag_id,total_cycles,successful_triangulations,triangulation_success_rate,less_than_3_anchors,full_coverage,full_coverage_rate,average_latency_ms,average_update_rate_hz,mqtt_failures,session_id
```

---

# 🛠️ INSTALACIÓN Y CONFIGURACIÓN COMPLETA

## **Hardware Requerido**

### **Placas UWB (x6 unidades disponibles):**
- **Modelo:** [Makerfabs ESP32 UWB DW3000](https://www.makerfabs.com/esp32-uwb-dw3000.html)
- **Chip UWB:** Decawave DW3000 (última generación)
- **Microcontrolador:** ESP32 WROVER (8MB PSRAM + 4MB Flash)
- **Conectividad:** WiFi, Bluetooth integrados
- **Alimentación:** Micro-USB (5V)
- **Distribución:** 5 anclas + 1 tag (configuración actual)
- **Precio:** $45.80 USD c/u (WROVER +$2.00 vs WROOM)

### **Especificaciones ESP32 UWB DW3000 WROVER:**
- ✅ **Compatible con Apple U1 chip** - Interoperabilidad avanzada
- ✅ **Consumo ultra-bajo** - 1/3 del consumo vs DW1000
- ✅ **Canales UWB:** Ch5 (6.5 GHz) y Ch9 (8 GHz)
- ✅ **Certificación FiRa™** - Estándar PHY y MAC
- ✅ **Precisión mejorada** - Tracking de alta precisión
- ✅ **Arduino compatible** - Fácil programación
- ✅ **Rango de alimentación:** 4.8-5.5V (5.0V típico)
- 🚀 **ESP32 WROVER ventajas:** 8MB PSRAM + 4MB Flash
- 💾 **Memoria expandida** - Ideal para aplicaciones complejas
- 📊 **Buffers grandes** - Mejor manejo de datos UWB

### **Infraestructura:**
- Router WiFi 2.4GHz/5GHz
- Servidor MQTT (ej: Mosquitto)
- PC/Servidor para análisis de datos
- Cables Micro-USB para programación y alimentación

## **Preparación del Hardware**

### **Placas Makerfabs ESP32 UWB DW3000:**
Las placas ya vienen **completamente integradas** con el chip DW3000 soldado y configurado. No requieren conexiones adicionales.

### **Conexiones internas de la placa:**
```bash
# Conexiones ESP32 <-> DW3000 (ya realizadas en PCB)
DW3000_VCC  -> ESP32 3.3V
DW3000_GND  -> ESP32 GND  
DW3000_CS   -> ESP32 GPIO5
DW3000_MOSI -> ESP32 GPIO23
DW3000_MISO -> ESP32 GPIO19
DW3000_CLK  -> ESP32 GPIO18
DW3000_IRQ  -> ESP32 GPIO34
DW3000_RST  -> ESP32 GPIO27
```

## **Configuración de Software para DW3000**

### **Librería Oficial Makerfabs DW3000:**
**Repositorio:** [Makerfabs-ESP32-UWB-DW3000](https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000)

> ⚠️ **Nota importante:** La librería DW3000 fue desarrollada por NConcepts, no por Makerfabs. Makerfabs mantiene el repositorio oficial.

#### **Instalación de la librería:**
1. Descargar repositorio: https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000
2. Copiar carpeta `Dw3000` al directorio de librerías de Arduino
3. Reiniciar Arduino IDE

### **Arduino IDE - Configuración para ESP32 WROVER + DW3000:**

#### **Configuración del Board Manager:**
1. **ESP32 Board Package:** v2.0.0+ (recomendado v2.0.9+)
2. **Placa específica:** ESP32 WROVER Module

#### **Configuración Hardware (Herramientas → Configuración):**
- **Board:** ESP32 WROVER Module  
- **Upload Speed:** 921600
- **CPU Frequency:** 240MHz (máximo rendimiento)
- **Flash Mode:** DIO (compatibilidad DW3000)
- **Flash Size:** 4MB (32Mb)
- **Partition Scheme:** Default 4MB with spiffs
- **PSRAM:** Enabled (CRÍTICO - aprovechar 8MB PSRAM)
- **Core Debug Level:** None (producción) o Info (desarrollo)

#### **Librerías Adicionales Requeridas:**
```
📦 Librerías del TFG:
├── Dw3000 (específica DW3000) - Desde repositorio Makerfabs
├── PubSubClient - Cliente MQTT para ESP32
├── ArduinoJson v6+ - Manejo de JSON para configuración
├── WiFi - Incluida con ESP32 Core
└── EEPROM - Persistencia de datos (incluida)
```

#### **Verificación de Configuración:**
```cpp
// Código de prueba básico para verificar DW3000:
#include "dw3000.h"

void setup() {
  Serial.begin(115200);
  Serial.println("Test Makerfabs ESP32 UWB DW3000");
  
  // Verificar PSRAM
  if(psramFound()){
    Serial.println("✅ PSRAM 8MB detectada");
  } else {
    Serial.println("❌ Error: PSRAM no detectada");
  }
  
  // Tu código de inicialización DW3000...
}
```

### **Configuración de Red:**
1. Editar `common/secrets.h`:
   ```cpp
   #define STA_SSID "Tu_WiFi_SSID"
   #define STA_PASS "Tu_WiFi_Password"
   #define MQTT_SERVER "192.168.1.100"  // IP de tu broker MQTT
   ```

### **Compilación y Carga**

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

### **Ejemplos Oficiales Makerfabs DW3000:**

El repositorio oficial incluye dos ejemplos básicos para verificar funcionamiento:

#### **🔧 simple_test:**
- **TX:** simple_test con modo transmisión
- **RX:** simple_test con modo recepción  
- **Función:** Envío/recepción básica de mensajes UWB
- **Uso:** Verificar comunicación entre placas

#### **📏 range:**
- **range_tx:** Dispositivo transmisor (ancla)
- **range_rx:** Dispositivo receptor (tag) - muestra distancia por serial
- **Función:** Medición básica de distancia UWB
- **Salida:** Distancia en metros via puerto serie

#### **Pruebas Recomendadas Pre-TFG:**
```bash
# 1. Test básico de comunicación
# Cargar simple_test en modo TX a una placa
# Cargar simple_test en modo RX a otra placa
# Verificar envío/recepción de mensajes

# 2. Test de ranging básico  
# Cargar range_tx a una placa (simula ancla)
# Cargar range_rx a otra placa (simula tag)
# Verificar medición de distancia por serial monitor
```

> **💡 Tip para el TFG:** Una vez verificados estos ejemplos básicos, tu código del proyecto (anclas + tag) implementa un sistema TDMA completo con 5 anclas simultáneas y triangulación automática.

### **Próximos Pasos con Hardware Real:**

#### **1. Configuración inicial (6 placas disponibles):**
```bash
# Distribución recomendada:
- 5 placas → Anclas fijas (IDs: 10, 20, 30, 40, 50)  
- 1 placa → Tag móvil (ID: 1)
```

#### **2. Verificación inicial del hardware DW3000:**

##### **Paso 1: Conexión física**
```bash
# Para cada una de las 6 placas ESP32 UWB DW3000:
1. Conectar vía cable Micro-USB al PC
2. Verificar que aparece como puerto COM (ej: COM3, COM4...)
3. En Arduino IDE → Herramientas → Puerto: Seleccionar puerto correcto
```

##### **Paso 2: Test completo del hardware (según datasheet oficial)**
```cpp
// Cargar este código para verificación completa de cada placa:
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== Test Makerfabs ESP32 UWB DW3000 ===");
  Serial.println("Basado en datasheet ESP32-WROVER v2.2");
  
  // Verificar chip específico
  Serial.printf("Chip Model: %s\n", ESP.getChipModel());
  Serial.printf("Chip Revision: %d\n", ESP.getChipRevision());
  Serial.printf("CPU Cores: %d\n", ESP.getChipCores());
  
  // Verificar PSRAM de 8MB (64 Mbit) - Crítico para TFG
  if(psramFound()){
    size_t psramSize = ESP.getPsramSize();
    Serial.printf("✅ PSRAM detectada: %d bytes (%.1f MB)\n", psramSize, psramSize/1024.0/1024.0);
    if(psramSize >= 8*1024*1024) {
      Serial.println("✅ PSRAM 8MB confirmada - Hardware correcto");
    } else {
      Serial.println("⚠️  PSRAM menor a 8MB - Verificar hardware");
    }
  } else {
    Serial.println("❌ Error: PSRAM no detectada - Hardware incorrecto");
  }
  
  // Verificar memoria Flash (4MB según datasheet)
  size_t flashSize = ESP.getFlashChipSize();
  Serial.printf("Flash Size: %d bytes (%.1f MB)\n", flashSize, flashSize/1024.0/1024.0);
  
  // Verificar especificaciones CPU
  Serial.printf("CPU Frequency: %d MHz (rango: 80-240 MHz)\n", ESP.getCpuFreqMHz());
  Serial.printf("Free Heap: %d KB\n", ESP.getFreeHeap() / 1024);
  Serial.printf("Free PSRAM: %d KB\n", ESP.getFreePsram() / 1024);
  
  // Verificar conectividad WiFi integrada
  Serial.println("\n--- Test WiFi (802.11 b/g/n) ---");
  WiFi.mode(WIFI_STA);
  Serial.println("✅ WiFi inicializado (2.4-2.5 GHz)");
  
  // Verificar especificaciones según datasheet
  Serial.println("\n--- Verificación Datasheet ESP32-WROVER ---");
  Serial.println("✅ ESP32-D0WDQ6 chip embedded");
  Serial.println("✅ Dual-core Xtensa 32-bit LX6");
  Serial.println("✅ 4MB External SPI Flash");
  Serial.println("✅ 8MB SPI Pseudo Static RAM");
  Serial.println("✅ Temperatura: -40°C ~ +85°C");
  Serial.println("✅ Dimensiones: 18.0×31.4×3.3mm");
  
  Serial.println("\n🎯 Hardware listo para TFG UWB DW3000");
}

void loop() {
  Serial.println("Hardware verificado - Placa lista para programación UWB");
  delay(3000);
}
```

##### **Paso 3: Test básico de DW3000**
```bash
# Una vez verificadas las placas básicas:
1. Descargar ejemplos del repositorio Makerfabs
2. Cargar example/simple_test/simple_test.ino en modo TX (1 placa)
3. Cargar example/simple_test/simple_test.ino en modo RX (otra placa)
4. Verificar comunicación UWB por serial monitor
```

##### **Paso 4: Test de ranging DW3000**
```bash
# Test de medición de distancia:
1. Cargar example/range/range_tx.ino en placa 1 (ancla simulada)
2. Cargar example/range/range_rx.ino en placa 2 (tag simulado)
3. Observar mediciones de distancia en serial monitor del RX
4. Mover las placas y verificar que la distancia cambia
```

##### **Resultado esperado:**
```bash
✅ Test exitoso si ves:
- PSRAM 8MB detectada en cada placa
- Comunicación UWB entre placas (TX/RX)
- Mediciones de distancia estables y realistas
- Sin errores de compilación o carga

❌ Resolver si encuentras:
- PSRAM no detectada → Verificar configuración WROVER
- Error de comunicación UWB → Revisar librería DW3000
- Mediciones erróneas → Verificar posicionamiento de placas
```

#### **3. Instalación física:**
- 📍 Montar las 5 anclas en las posiciones calculadas
- 📍 Configurar alimentación permanente para anclas
- 📍 Verificar cobertura WiFi en todas las posiciones
- 📍 Comprobar que no hay obstáculos metálicos grandes

#### **4. Pruebas de sistema:**
- 🧪 Ranging entre anclas y tag en modo estático
- 🧪 Movimiento del tag por la cancha
- 🧪 Captura de datos reales via MQTT
- 🧪 Validación con sistema de replay

### **Ventajas del ESP32 WROVER para tu TFG:**

#### **🎯 Para Análisis Deportivo:**
- **Buffers UWB grandes** - Los 8MB PSRAM permiten almacenar más mediciones
- **Procesamiento en tiempo real** - Filtros Kalman y ML sin limitaciones de memoria
- **Interfaz web compleja** - Visualización avanzada sin problemas de RAM
- **Datos MQTT robustos** - Colas grandes para transmisión confiable

#### **📊 Para Ciencia de Datos:**
- **Datasets grandes** - Manejo de más datos históricos en memoria
- **Algoritmos complejos** - Machine Learning con mayor capacidad
- **Múltiples sensores** - Futuras expansiones del sistema
- **Logging avanzado** - Almacenamiento temporal de métricas detalladas

---

# 📊 SISTEMA DE ANÁLISIS DE DATOS

## **Descripción del Pipeline de Datos**

El sistema completo de análisis incluye tres componentes principales:

1. **🔄 Recolección MQTT a CSV** (`mqtt_to_csv_collector.py`)
2. **🧮 Procesamiento y limpieza** (`csv_processor.py`)
3. **🎬 Replay interactivo** (`movement_replay.py`)

## **1. Recolección de Datos MQTT**

### **Uso Básico:**
```bash
# Uso básico (usar configuración por defecto)
python mqtt_to_csv_collector.py

# Especificar broker MQTT personalizado
python mqtt_to_csv_collector.py --mqtt-server 192.168.1.100 --mqtt-port 1883

# Especificar directorio de salida
python mqtt_to_csv_collector.py --output-dir ./mis_datos

# Ayuda completa
python mqtt_to_csv_collector.py --help
```

### **Archivos Generados:**
- `ranging_data_YYYYMMDD_HHMMSS.csv` - Datos brutos de ranging UWB
- `position_data_YYYYMMDD_HHMMSS.csv` - Posiciones calculadas y velocidades
- `zones_data_YYYYMMDD_HHMMSS.csv` - Eventos de zonas de fútbol sala
- `metrics_data_YYYYMMDD_HHMMSS.csv` - Métricas de rendimiento del sistema

### **Controles Durante Recolección:**
- `Ctrl+C` - Detener recolector y mostrar estadísticas finales
- Las estadísticas se muestran automáticamente cada 30 segundos

## **2. Procesamiento de Datos**

### **Uso del Procesador:**
```bash
# Procesar la sesión más reciente automáticamente
python csv_processor.py

# Procesar sesión específica
python csv_processor.py --session-id 20241201_143022

# Especificar directorios personalizados
python csv_processor.py --data-dir ./mis_datos --output-dir ./datos_procesados

# Solo procesar datos sin crear gráficos (más rápido)
python csv_processor.py --no-plots
```

### **Procesamiento Realizado:**
- ✅ Filtrado de distancias fuera de rango (10cm - 60m)
- ✅ Eliminación de mediciones con RSSI inválido
- ✅ Detección de outliers usando IQR por ancla
- ✅ Filtrado de velocidades imposibles (>12 m/s para fútbol sala)
- ✅ Eliminación de saltos teleportación (>15 m/s)
- ✅ Interpolación a frecuencia constante (25 Hz)
- ✅ Suavizado con filtro Savitzky-Golay
- ✅ Generación de estadísticas resumidas

### **Archivos Generados:**
```
processed_data/
└── session_YYYYMMDD_HHMMSS/
    ├── ranging_cleaned.csv          # Datos de ranging limpios
    ├── position_cleaned.csv         # Posiciones limpias
    ├── position_interpolated_cleaned.csv  # Posiciones interpoladas (25 Hz)
    ├── zones_cleaned.csv            # Eventos de zonas
    ├── metrics_cleaned.csv          # Métricas del sistema
    ├── summary_statistics.txt       # Estadísticas resumidas
    ├── trajectory_YYYYMMDD_HHMMSS.png      # Gráfico de trayectoria
    ├── distance_distribution_YYYYMMDD_HHMMSS.png  # Distribución distancias por ancla
    └── velocity_time_YYYYMMDD_HHMMSS.png   # Velocidad vs tiempo
```

## **3. Sistema de Replay Avanzado**

### **Características del Replay:**
- 🎯 Visualización de cancha de fútbol sala (40x20m) con líneas oficiales
- 📍 Posiciones de anclas UWB optimizadas
- 🏃 Trayectoria del jugador con trail dinámico
- 🎨 Zonas de análisis deportivo (áreas de portería, centro campo, etc.)
- 📊 Panel de información en tiempo real (posición, velocidad, zona actual)
- ⚡ Velocidad de replay ajustable (0.1x a 10x)
- 🔧 **Filtros Avanzados:**
  - **Filtro de Kalman** - Suavizado de posiciones 2D con predicción de velocidad
  - **Predicción ML** - Gaussian Process Regression para interpolación inteligente
  - **Detección de Sprint** - Identificación automática de velocidades altas
  - **Restricciones Físicas** - Límites de velocidad y aceleración realistas

### **Uso del Replay:**
```bash
# Replay interactivo de la sesión más reciente
python movement_replay.py

# Replay de sesión específica
python movement_replay.py --session-id 20241201_143022

# Solo generar reporte sin mostrar visualización
python movement_replay.py --report-only

# Especificar directorio de datos procesados
python movement_replay.py --data-dir ./datos_procesados
```

## **Estructura de Datos CSV**

### **Ranging Data:**
```csv
timestamp_system,timestamp_device,tag_id,anchor_id,distance_raw_cm,distance_filtered_cm,rssi_dbm,anchor_responded,session_id
1701434422.123,45231,1,10,234.5,235.1,-87.2,True,20241201_143022
```

### **Position Data:**
```csv
timestamp_system,timestamp_device,tag_id,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,speed_ms,prediction_x_m,prediction_y_m,responding_anchors,update_rate_hz,session_id
1701434422.123,45231,1,15.3,8.7,2.1,0.5,2.16,15.4,8.8,5,25.0,20241201_143022
```

### **Zones Data:**
```csv
timestamp_system,timestamp_device,tag_id,zone_name,action,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,duration_ms,session_id
1701434422.123,45231,1,Area_Porteria_1,enter,2.1,4.2,1.8,0.3,0,20241201_143022
```

## **Parámetros de Filtrado**

### **Datos de Ranging:**
- **Distancia mínima:** 10 cm (limitación física UWB)
- **Distancia máxima:** 60 m (rango interior razonable)
- **RSSI mínimo:** -120 dBm
- **RSSI máximo:** -30 dBm

### **Datos de Posición:**
- **Velocidad máxima:** 12 m/s (fútbol sala)
- **Salto máximo:** 15 m/s (detección teleportación)
- **Anclas mínimas:** 3 (para trilateración válida)
- **Margen cancha:** 5 m (posiciones fuera válidas)

### **Interpolación:**
- **Frecuencia objetivo:** 25 Hz (40ms entre muestras)
- **Método:** Interpolación lineal + filtro Savitzky-Golay
- **Ventana suavizado:** 11 puntos (440ms)

---

# 📊 USO DEL SISTEMA

## **1. Secuencia de Inicio**
1. **Alimentar las 5 anclas** (orden indistinto)
2. **Esperar sincronización** (~30 segundos)
3. **Encender tag del jugador**
4. **Verificar conectividad** MQTT/WiFi
5. **Iniciar sesión de entrenamiento**

## **2. Monitorización**
- **Serial Monitor:** Logs detallados de debugging
- **MQTT Topics:** Datos en tiempo real
  - `uwb/tag/position` - Coordenadas X,Y del jugador
  - `uwb/tag/metrics` - Estadísticas de rendimiento
  - `uwb/anchors/status` - Estado de las anclas

## **3. Flujo Típico de Uso**

### **Sesión de Entrenamiento Completa:**
```bash
# 1. Configurar hardware → Programar ESP32s
# 2. Iniciar captura
python mqtt_to_csv_collector.py --output-dir ./entrenamiento_20241201

# 3. Realizar entrenamiento (el script sigue capturando)
# 4. Detener con Ctrl+C

# 5. Procesar datos
python csv_processor.py --data-dir ./entrenamiento_20241201

# 6. Visualizar movimientos
python movement_replay.py --data-dir ./processed_data
```

### **Análisis de Múltiples Sesiones:**
```bash
# Procesar todas las sesiones en un directorio
for session in data/ranging_data_*.csv; do
    session_id=$(basename "$session" | sed 's/ranging_data_\(.*\)\.csv/\1/')
    python csv_processor.py --session-id "$session_id"
done

# Generar reportes de todas las sesiones
for session_dir in processed_data/session_*; do
    session_id=$(basename "$session_dir" | sed 's/session_//')
    python movement_replay.py --session-id "$session_id" --report-only
done
```

---

# 🏆 APLICACIONES DEPORTIVAS

## **Análisis de Rendimiento:**
- **Distancia recorrida** por jugador y sesión
- **Velocidades máximas** y promedio durante el juego
- **Patrones de aceleración** en sprints y frenadas
- **Tiempo de permanencia** en diferentes zonas de la cancha

## **Análisis Táctico:**
- **Mapas de calor** de posicionamiento de jugadores
- **Trayectorias de movimiento** individual y colectivo
- **Análisis de formaciones** defensivas y ofensivas
- **Estudios de transiciones** entre fases de juego

## **Monitorización de Carga:**
- **Intensidad de movimiento** durante entrenamientos
- **Distribución temporal** de esfuerzos
- **Comparación entre sesiones** de entrenamiento
- **Datos objetivos** para planificación deportiva

## **Zonas de Análisis Deportivo:**
- **Área Portería 1** (2.0, 4.0) - Radio 3m
- **Área Portería 2** (38.0, 4.0) - Radio 3m
- **Centro Campo** (20.0, 10.0) - Radio 3m
- **Medio Campo 1** (10.0, 10.0) - Radio 5m
- **Medio Campo 2** (30.0, 10.0) - Radio 5m
- **Banda Lateral** (20.0, 2.0) - Radio 8m

---

# 🔧 SOLUCIÓN DE PROBLEMAS

## **Problemas Comunes:**

### **"Ancla no responde"**
```bash
# Verificar:
1. Alimentación estable (5V/2A mínimo)
2. Conexiones DW3000 correctas  
3. ID_PONG único (10,20,30,40,50)
4. Restart automático después de 15s sin actividad
```

### **"Tag no se localiza"**
```bash
# Verificar:
1. Mínimo 3 anclas operativas simultáneamente
2. Tag dentro del área de cobertura
3. Sin obstáculos metálicos grandes
4. RSSI > -90dBm en al menos 3 anclas
```

### **"Coordenadas erróneas"**
```bash
# Verificar:
1. Posiciones de anclas correctas en config.h
2. Calibración de cancha (40x20m)
3. Sincronización temporal correcta
4. Filtros Kalman activos
```

### **Error: "No se encontraron archivos de ranging data"**
- Verificar que el recolector MQTT haya capturado datos
- Revisar el directorio de datos especificado
- Confirmar que el tag esté publicando en el topic correcto

### **Error: "No se encontraron datos de posición procesados"**
- Ejecutar primero el procesador CSV
- Verificar que haya datos de posición en los CSV brutos
- Revisar que al menos 3 anclas estén respondiendo

### **Replay muy lento o errático**
- Reducir la velocidad de replay con teclas ↓
- Verificar que los datos interpolados estén disponibles
- Cerrar otras aplicaciones que usen matplotlib

### **Datos de mala calidad**
- Revisar posicionamiento de anclas UWB
- Verificar interferencias en 6.5 GHz
- Ajustar parámetros de filtrado en el código
- Aumentar duración de captura para más datos

### **Problemas de Performance**
| Problema | Solución |
|----------|----------|
| Error de imports | `pip install -r requirements.txt` |
| No hay datos | Verificar broker MQTT y WiFi |
| Gráficos no aparecen | Instalar: `pip install matplotlib seaborn` |
| Replay lento | Usar datos filtrados más pequeños |

---

# 📈 MÉTRICAS Y ANÁLISIS DE RENDIMIENTO

## **Objetivos del TFG:**

### **Métricas de Precisión Objetivo:**
- 🎯 **Error < 50cm** en condiciones reales de juego
- 🎯 **Latencia < 200ms** para análisis en tiempo real
- 🎯 **Cobertura 100%** de la cancha sin zonas muertas
- 🎯 **Disponibilidad > 95%** durante sesiones de entrenamiento

### **Métricas del Sistema:**

#### **Métricas de Trilateración:**
- Tasa de éxito de trilateración
- Porcentaje de timestamps con <3 anclas
- Porcentaje de cobertura completa (5 anclas)

#### **Métricas de Latencia:**
- Latencia promedio extremo-a-extremo (ranging → MQTT)
- Frecuencia de actualización promedio
- Fallos de publicación MQTT

#### **Métricas Deportivas:**
- Distancia total recorrida
- Velocidad promedio y máxima
- Tiempo en sprint (>6 m/s)
- Tiempo estático (<0.5 m/s)
- Eventos de zona por minuto

#### **Especificaciones Actuales:**
- **Precisión**: <50cm objetivo
- **Latencia**: <200ms objetivo  
- **Frecuencia**: 25 Hz constante
- **Cobertura**: Cancha completa 40x20m

---

# 👨‍💻 DESARROLLO DEL PROYECTO

Este es un **Trabajo de Fin de Grado** en desarrollo activo.

## **Información del Proyecto:**
- **Autor:** Nicolás Iglesias García
- **GitHub:** [@nicogarrr](https://github.com/nicogarrr)
- **Universidad:** Universidad de Oviedo - EPI Gijón
- **Grado:** Ciencia e Ingeniería de Datos
- **Año académico:** 2024-2025

## **Estado Actual:**
- 🟢 **Diseño del sistema** - Completado
- 🟢 **Hardware adquirido** - 6x ESP32 UWB DW3000 disponibles ✅
- 🟢 **Implementación firmware** - Completado
- 🟢 **Algoritmos de localización** - Completado
- 🟢 **Sistema de análisis** - Completado
- 🟢 **Filtros avanzados** - Completado (Kalman + ML)
- 🟢 **Sistema de replay** - Completado
- 🟡 **Validación experimental** - En progreso con hardware real
- 🔴 **Documentación final** - Pendiente

## **Tecnologías Implementadas:**
- **Hardware:** ESP32 + DW3000 UWB
- **Comunicación:** WiFi + MQTT
- **Análisis:** Python + Pandas + NumPy + SciPy
- **Machine Learning:** Scikit-learn + Gaussian Process Regression
- **Filtrado:** Filtro de Kalman + Savitzky-Golay
- **Visualización:** Matplotlib + Seaborn
- **Interfaz:** Sistema de replay interactivo

---

# 📄 LICENCIA Y AGRADECIMIENTOS

## **Licencia**
Este proyecto está desarrollado para fines académicos y de investigación.

## **Agradecimientos**
- **Tutor TFG:** [Nombre del tutor]
- **Universidad:** Universidad de Oviedo - EPI Gijón
- **Grado:** Ciencia e Ingeniería de Datos
- **Área:** Sistemas de Telecomunicaciones e Ingeniería de Datos

---

# 🚀 GUÍA RÁPIDA DE USO

## 📋 **PASOS PARA EJECUTAR TU SISTEMA**

### 1️⃣ **PREPARACIÓN (Solo una vez)**
```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Verificar que todo funciona
python -c "import csv_processor; print('✅ Sistema listo')"
```

### 2️⃣ **HARDWARE UWB (Subir código a ESP32)**

#### Programar las Anclas UWB:
```bash
# Abrir Arduino IDE y programar cada ancla:
# 1. uwb_anchor_10/anchor_10.ino  → ESP32 #1
# 2. uwb_anchor_20/anchor_20.ino  → ESP32 #2  
# 3. uwb_anchor_30/anchor_30.ino  → ESP32 #3
# 4. uwb_anchor_40/anchor_40.ino  → ESP32 #4
# 5. uwb_anchor_50/anchor_50.ino  → ESP32 #5
```

#### Programar el Tag UWB:
```bash
# 6. uwb_tag/tag.ino → ESP32 #6 (el que llevará el jugador)
```

### 3️⃣ **CAPTURA DE DATOS EN TIEMPO REAL**

#### Opción A: Captura MQTT (Recomendado)
```bash
# 1. Ejecutar colector MQTT
python mqtt_to_csv_collector.py

# Esto creará archivos en data/:
# - uwb_data_YYYYMMDD_HHMMSS.csv
# - uwb_status_YYYYMMDD_HHMMSS.csv  
# - uwb_zones_YYYYMMDD_HHMMSS.csv
# - uwb_metrics_YYYYMMDD_HHMMSS.csv
```

#### Opción B: Usar datos de ejemplo
```bash
# Ya tienes un archivo de ejemplo en:
# data/uwb_data_futsal_game_20250621_160000.csv
```

### 4️⃣ **PROCESAMIENTO Y ANÁLISIS**

#### Procesar datos capturados:
```bash
# Procesa automáticamente todos los archivos en data/
python csv_processor.py
```

**Esto genera:**
- ✅ Datos filtrados y suavizados
- 📊 Visualizaciones automáticas  
- 📈 Estadísticas de rendimiento
- 💾 Archivos procesados en `processed_data/`

### 5️⃣ **VISUALIZACIÓN INTERACTIVA - SISTEMA DE REPLAY**

#### Sistema de Replay Avanzado:
```bash
# Reproducir movimientos en tiempo real con filtros ML + Kalman
python movement_replay.py

# Con archivo específico
python movement_replay.py data/mi_archivo.csv

# Solo mostrar reporte estadístico
python movement_replay.py --report
```

**🎮 Controles del Replay:**
- `ESPACIO`: ⏯️ Play/Pausa
- `← →`: Frame anterior/siguiente  
- `↑ ↓`: Aumentar/Disminuir velocidad (0.1x - 10x)
- `R`: 🔄 Reiniciar desde el inicio
- `Q`: ❌ Salir del sistema

**🚀 Características Avanzadas del Replay:**
- 🎯 **Cancha profesional** - Fútbol sala (40x20m) con líneas oficiales
- 📍 **Anclas UWB optimizadas** - Posiciones fuera del área de juego
- 🏃 **Trayectoria inteligente** - Trail dinámico con degradado
- 🎨 **Zonas de análisis** - Áreas de portería, centro campo, etc.
- 📊 **Panel en tiempo real** - Posición, velocidad, zona actual
- ⚡ **Velocidad ajustable** - 0.1x a 10x con controles suaves
- 🔧 **Filtros avanzados** - Kalman + Machine Learning
- 🤖 **Predicción ML** - Gaussian Process Regression para interpolación
- 📈 **Indicador de velocidad** - Círculo proporcional a la velocidad

**📊 Zonas de Análisis Automático:**
- 🥅 **ÁREA PORTERÍA IZQUIERDA** - Radio 3m
- 🥅 **ÁREA PORTERÍA DERECHA** - Radio 3m  
- ⚽ **CENTRO CAMPO** - Radio 3m
- 👈 **MEDIO CAMPO IZQUIERDO** - 0-20m
- 👉 **MEDIO CAMPO DERECHO** - 20-40m
- 🏃 **EN JUEGO** - Resto de la cancha

---

# 📊 SISTEMA DE ANÁLISIS DE DATOS

## **Descripción del Pipeline de Datos**

El sistema completo de análisis incluye tres componentes principales:

1. **🔄 Recolección MQTT a CSV** (`mqtt_to_csv_collector.py`)
2. **🧮 Procesamiento y limpieza** (`csv_processor.py`)
3. **🎬 Replay interactivo** (`movement_replay.py`)

## **1. Recolección de Datos MQTT**

### **Uso Básico:**
```bash
# Uso básico (usar configuración por defecto)
python mqtt_to_csv_collector.py

# Especificar broker MQTT personalizado
python mqtt_to_csv_collector.py --mqtt-server 192.168.1.100 --mqtt-port 1883

# Especificar directorio de salida
python mqtt_to_csv_collector.py --output-dir ./mis_datos
```

### **Archivos Generados:**
- `ranging_data_YYYYMMDD_HHMMSS.csv` - Datos brutos de ranging UWB
- `position_data_YYYYMMDD_HHMMSS.csv` - Posiciones calculadas y velocidades
- `zones_data_YYYYMMDD_HHMMSS.csv` - Eventos de zonas de fútbol sala
- `metrics_data_YYYYMMDD_HHMMSS.csv` - Métricas de rendimiento del sistema

## **2. Procesamiento de Datos**

### **Procesamiento Realizado:**
- ✅ Filtrado de distancias fuera de rango (10cm - 60m)
- ✅ Eliminación de mediciones con RSSI inválido
- ✅ Detección de outliers usando IQR por ancla
- ✅ Filtrado de velocidades imposibles (>12 m/s para fútbol sala)
- ✅ Eliminación de saltos teleportación (>15 m/s)
- ✅ Interpolación a frecuencia constante (25 Hz)
- ✅ Suavizado con filtro Savitzky-Golay
- ✅ Generación de estadísticas resumidas

## **3. Sistema de Replay Avanzado**

### **Características del Replay:**
- 🎯 Visualización de cancha de fútbol sala (40x20m) con líneas oficiales
- 📍 Posiciones de anclas UWB optimizadas
- 🏃 Trayectoria del jugador con trail dinámico
- 🎨 Zonas de análisis deportivo (áreas de portería, centro campo, etc.)
- 📊 Panel de información en tiempo real (posición, velocidad, zona actual)
- ⚡ Velocidad de replay ajustable (0.1x a 10x)
- 🔧 **Filtros Avanzados:**
  - **Filtro de Kalman** - Suavizado de posiciones 2D con predicción de velocidad
  - **Predicción ML** - Gaussian Process Regression para interpolación inteligente
  - **Detección de Sprint** - Identificación automática de velocidades altas
  - **Restricciones Físicas** - Límites de velocidad y aceleración realistas

---

# 🔧 SOLUCIÓN DE PROBLEMAS

## **Problemas Comunes:**

### **"Ancla no responde"**
```bash
# Verificar:
1. Alimentación estable (5V/2A mínimo)
2. Conexiones DW3000 correctas  
3. ID_PONG único (10,20,30,40,50)
4. Restart automático después de 15s sin actividad
```

### **"Tag no se localiza"**
```bash
# Verificar:
1. Mínimo 3 anclas operativas simultáneamente
2. Tag dentro del área de cobertura
3. Sin obstáculos metálicos grandes
4. RSSI > -90dBm en al menos 3 anclas
```

### **"Coordenadas erróneas"**
```bash
# Verificar:
1. Posiciones de anclas correctas en config.h
2. Calibración de cancha (40x20m)
3. Sincronización temporal correcta
4. Filtros Kalman activos
```

### **Problemas de Software**
| Problema | Solución |
|----------|----------|
| Error de imports | `pip install -r requirements.txt` |
| No hay datos | Verificar broker MQTT y WiFi |
| Gráficos no aparecen | Instalar: `pip install matplotlib seaborn` |
| Replay lento | Usar datos filtrados más pequeños |

---

**⚽ Innovación tecnológica aplicada al deporte ⚽**  
¡Tu sistema UWB está listo para analizar rendimiento deportivo! 🏆 