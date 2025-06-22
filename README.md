# 🏟️ Sistema de Localización Indoor UWB para Fútbol Sala

**TFG 2024-2025 - Trabajo de Fin de Grado**  
**Autor:** Nicolás Iglesias García  
**Universidad:** Universidad de Oviedo - EPI Gijón  
**Grado:** Ciencia e Ingeniería de Datos  
**Versión:** v2.1-FINAL

## 📋 Descripción del Proyecto

Sistema de posicionamiento indoor de alta precisión basado en tecnología **Ultra-Wideband (UWB)** específicamente diseñado para el análisis de rendimiento deportivo en **fútbol sala**. 

El sistema utiliza **5 anclas estratégicamente posicionadas** en una cancha de 40x20m para triangular la posición de jugadores equipados con tags UWB, proporcionando datos precisos de movimiento, velocidad y posicionamiento táctico en tiempo real.

## 🚀 **CARACTERÍSTICAS PRINCIPALES**

### ✅ **Sistema Completo Funcional**
- **🔧 Hardware:** 6 placas ESP32 UWB DW3000 (5 anclas + 1 tag)
- **📊 Análisis en tiempo real:** Pipeline completo de procesamiento de datos
- **🎬 Visualización avanzada:** Sistema de replay interactivo con filtros ML + Kalman
- **🌐 Interfaz web:** Sistema embebido en ESP32 para monitoreo en tiempo real
- **📡 Comunicación:** Sistema MQTT robusto para transmisión de datos
- **🎯 Precisión:** <50cm objetivo en condiciones reales de juego

### ✅ **Tecnologías Implementadas**
- **Hardware:** ESP32 WROVER + DW3000 UWB (8MB PSRAM + 4MB Flash)
- **Comunicación:** WiFi 802.11 b/g/n + MQTT + Bluetooth v4.2
- **Análisis:** Python + Pandas + NumPy + SciPy + Scikit-learn
- **Machine Learning:** Gaussian Process Regression + Filtro de Kalman
- **Visualización:** Matplotlib + Seaborn + Sistema de replay interactivo
- **Web Interface:** HTML5 Canvas + CSS3 + JavaScript ES6 embebido en ESP32

## 📡 Tecnología Ultra-Wideband (UWB) DW3000

**Ultra-Wideband (UWB)** es un protocolo de comunicación inalámbrica de corto alcance que opera a través de ondas de radio, permitiendo ranging seguro y confiable con precisión de centímetros.

### **🚀 Ventajas del DW3000 vs DW1000:**
1. **🍎 Interoperabilidad Apple U1** - Compatible con chip U1 de dispositivos Apple
2. **🛡️ Certificación FiRa™** - Estándar PHY, MAC y certificación industrial
3. **🔋 Consumo ultra-eficiente** - Aproximadamente 1/3 del consumo del DW1000
4. **📡 Doble banda UWB** - Canales 5 (6.5 GHz) y 9 (8 GHz)

### **🔧 Hardware del TFG - Especificaciones:**
- **Chip UWB:** Decawave DW3000 (última generación)
- **Microcontrolador:** ESP32-D0WDQ6 WROVER (8MB PSRAM + 4MB Flash)
- **CPU:** Dual-core Xtensa 32-bit LX6 (80-240 MHz)
- **Conectividad:** WiFi 2.4G, Bluetooth v4.2, UWB
- **Temperatura:** -40°C ~ +85°C
- **Dimensiones:** 18.0×31.4×3.3mm

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
```

### **Configuración de Anclas Optimizada:**
- **A10(-1,-1)** - Esquina Suroeste (fuera de cancha)
- **A20(-1,21)** - Esquina Noroeste (fuera de cancha)  
- **A30(41,-1)** - Esquina Sureste (fuera de cancha)
- **A40(41,21)** - Esquina Noreste (fuera de cancha)
- **A50(20,-1)** - Centro campo lateral Sur (fuera de cancha)

### **Ventajas de esta Configuración:**
- ✅ **No interfiere con el juego** - Todas las anclas fuera del área
- ✅ **Cobertura equilibrada** - 4 esquinas + 1 punto central
- ✅ **Geometría robusta** - Trilateración estable en toda la cancha
- ✅ **Fácil instalación** - Montaje en perímetro del pabellón
- ✅ **Redundancia** - 5 anclas para mayor precisión y tolerancia a fallos

## 📁 Estructura del Proyecto

```
TFG OFICIAL/
├── README.md                    # 📖 Documentación completa
├── requirements.txt             # 📦 Dependencias Python
├── common/                      # ⚙️ Configuración centralizada
│   └── config.h                 # Parámetros del sistema UWB
├── uwb_anchor_10/               # 📡 Ancla esquina Suroeste (-1,-1)
│   └── anchor_10/
│       └── anchor_10.ino        # Firmware ancla ID=10
├── uwb_anchor_20/               # 📡 Ancla esquina Noroeste (-1,21)
│   └── anchor_20/
│       └── anchor_20.ino        # Firmware ancla ID=20
├── uwb_anchor_30/               # 📡 Ancla esquina Sureste (41,-1)
│   └── anchor_30/
│       └── anchor_30.ino        # Firmware ancla ID=30
├── uwb_anchor_40/               # 📡 Ancla esquina Noreste (41,21)
│   └── anchor_40/
│       └── anchor_40.ino        # Firmware ancla ID=40
├── uwb_anchor_50/               # 📡 Ancla centro campo Sur (20,-1)
│   └── anchor_50/
│       └── anchor_50.ino        # Firmware ancla ID=50
├── uwb_tag/                     # 🏃 Tag móvil con interfaz web
│   └── tag/
│       └── tag.ino              # Firmware tag + algoritmos de localización + web server
├── data/                        # 💾 Datos capturados
│   └── uwb_data_futsal_game_20250621_160000.csv  # Archivo de ejemplo
├── processed_data/              # 🔬 Datos procesados
│   └── latest_processed.csv     # Último archivo procesado
├── outputs/                     # 📊 ESTRUCTURA CONSOLIDADA DE RESULTADOS
│   ├── heatmaps/               # 📊 Mapas de calor y visualizaciones de densidad
│   ├── reports/                # 📋 Reportes de análisis en texto
│   ├── comparisons/            # 🔄 Comparaciones entre sesiones
│   └── dashboards/             # 📈 Dashboards y visualizaciones combinadas
├── backup_scripts_20250622_210240/  # 💾 Scripts especializados de respaldo
├── uwb_analyzer.py             # 🧮 Sistema principal de análisis y mapas de calor
├── uwb_comparator.py           # 🔄 Comparador de sesiones deportivas
├── movement_replay.py          # 🎬 Sistema de replay avanzado con ML + Kalman
├── mqtt_to_csv_collector.py    # 📨 Colector MQTT en tiempo real
├── integration_scripts/        # 🌐 Integración con sistemas externos
│   └── wordpress_auto_upload.py # 📤 Automatización WordPress
└── wordpress_plugin/           # 🌐 Plugin WordPress profesional
    └── tfg-uwb-analytics/       # 📊 Sistema web completo
```

## 🚀 **GUÍA RÁPIDA DE USO**

### 1️⃣ **PREPARACIÓN INICIAL**
```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Verificar instalación
python -c "import numpy, pandas, matplotlib; print('✅ Sistema listo')"
```

### 2️⃣ **CONFIGURACIÓN HARDWARE**
```bash
# 1. Programar ESP32 con Arduino IDE:
#    - 5 anclas: uwb_anchor_XX/anchor_XX/anchor_XX.ino
#    - 1 tag: uwb_tag/tag/tag.ino

# 2. Configurar red WiFi en common/config.h:
#    - SSID y password de la red
#    - IP del broker MQTT
```

### 3️⃣ **CAPTURA DE DATOS EN TIEMPO REAL**
```bash
# Ejecutar colector MQTT
python mqtt_to_csv_collector.py

# Esto creará automáticamente archivos en data/:
# - uwb_data_futsal_game_YYYYMMDD_HHMMSS.csv
# - Archivos adicionales de métricas y zonas
```

### 4️⃣ **ANÁLISIS Y VISUALIZACIÓN**
```bash
# Sistema de análisis principal
python uwb_analyzer.py

# Sistema de replay interactivo (RECOMENDADO)
python movement_replay.py

# Comparador de sesiones
python uwb_comparator.py
```

### 5️⃣ **CONTROLES DEL SISTEMA DE REPLAY**
```bash
🎮 CONTROLES INTERACTIVOS:
   SPACE: ⏯️  Play/Pause
   ←/→: Frame anterior/siguiente  
   ↑/↓: Velocidad +/- (0.1x - 10x)
   R: 🔄 Reiniciar
   Q: ❌ Salir

🔧 FUNCIONES AVANZADAS:
   Sliders: Ajustar velocidad de reproducción
   Botón Kalman: Activar/desactivar filtro de Kalman
   Botón ML Pred: Activar/desactivar predicción ML
```

## 🎬 **SISTEMA DE REPLAY AVANZADO**

### **🏟️ Visualización Profesional:**
- **Cancha oficial** de fútbol sala (40x20m) con líneas reglamentarias
- **5 Anclas UWB** posicionadas optimalmente fuera de la cancha
- **Jugador en tiempo real** con trail de trayectoria (últimos 100 puntos)
- **Zonas deportivas** automáticas (áreas de portería, centro campo, etc.)
- **Panel de información** con posición, velocidad, zona actual y progreso
- **Indicador de velocidad** visual proporcional al movimiento

### **🔬 Filtros Avanzados de Datos:**
- **Filtro de Kalman** - Suavizado de posiciones 2D con predicción de velocidad
- **Predicción ML** - Gaussian Process Regression para interpolación inteligente  
- **Filtro de velocidades** - Eliminación de movimientos imposibles
- **Interpolación inteligente** - Relleno de gaps con algoritmos ML
- **Restricciones físicas** - Límites realistas de velocidad y aceleración

### **📊 Análisis Deportivo Automático:**
- **Velocidades instantáneas** calculadas frame a frame
- **Distancia total recorrida** durante la sesión
- **Tiempo en zonas** específicas de la cancha
- **Identificación de zonas** automática (portería, centro campo, etc.)
- **Detección de sprints** automática (>5 m/s)

## 🌐 **INTERFAZ WEB INTEGRADA**

### **📱 Acceso a la Interfaz Web del ESP32:**
```
1. ESP32 conectado a WiFi → http://[IP_ESP32]/
2. Endpoint de datos: http://[IP_ESP32]/data
3. Actualización automática cada 150ms
```

### **🎯 Características de la Interfaz Web:**
- **Canvas interactivo** de cancha de fútbol sala (40x20m)
- **Visualización en tiempo real** de posición del jugador
- **Distancias de las 5 anclas** UWB en tiempo real
- **Indicadores de velocidad** y zona actual
- **Panel de estadísticas** con métricas instantáneas
- **Responsive design** para móviles y tablets

## 📊 **ESTRUCTURA DE DATOS**

### **Datos de Entrada (data/):**
```csv
# Formato principal: uwb_data_futsal_game_YYYYMMDD_HHMMSS.csv
timestamp,tag_id,x,y,anchor_10_dist,anchor_20_dist,anchor_30_dist,anchor_40_dist,anchor_50_dist
```

### **Datos Procesados (processed_data/):**
- **latest_processed.csv** - Último archivo procesado con filtros aplicados
- **Filtrado automático** de outliers y velocidades imposibles
- **Interpolación a 25 Hz** constantes para análisis suave

### **Resultados Organizados (outputs/):**
- **📊 heatmaps/** - Mapas de calor y visualizaciones de densidad
- **📋 reports/** - Reportes de análisis en formato texto
- **🔄 comparisons/** - Comparaciones entre sesiones
- **📈 dashboards/** - Dashboards y visualizaciones combinadas

## 🎯 **APLICACIONES DEPORTIVAS**

### **📈 Análisis de Rendimiento:**
- **Distancia recorrida** por jugador y sesión
- **Velocidades máximas** y promedio durante el juego
- **Patrones de aceleración** en sprints y frenadas
- **Tiempo de permanencia** en diferentes zonas de la cancha

### **🎯 Análisis Táctico:**
- **Mapas de calor** de posicionamiento de jugadores
- **Trayectorias de movimiento** individual y colectivo
- **Análisis de formaciones** defensivas y ofensivas
- **Estudios de transiciones** entre fases de juego

### **⚡ Zonas de Análisis Automático:**
- **🥅 ÁREA PORTERÍA IZQUIERDA** - Radio 3m desde (2.0, 4.0)
- **🥅 ÁREA PORTERÍA DERECHA** - Radio 3m desde (38.0, 4.0)
- **⚽ CENTRO CAMPO** - Radio 3m desde (20.0, 10.0)
- **👈 MEDIO CAMPO IZQUIERDO** - Radio 5m desde (10.0, 10.0)
- **👉 MEDIO CAMPO DERECHO** - Radio 5m desde (30.0, 10.0)
- **🏃 BANDA LATERAL** - Radio 8m desde (20.0, 2.0)

## 📈 **MÉTRICAS DE RENDIMIENTO**

### **🎯 Objetivos del Sistema:**
- **Precisión:** <50cm en condiciones reales de juego
- **Latencia:** <200ms para análisis en tiempo real
- **Frecuencia:** 25-40 Hz de actualización constante
- **Cobertura:** 100% de la cancha sin zonas muertas
- **Disponibilidad:** >95% durante sesiones de entrenamiento

### **📊 Métricas Monitoreadas:**
- **Tasa de éxito de trilateración** (objetivo: >90%)
- **Porcentaje de cobertura** con las 5 anclas
- **Latencia extremo-a-extremo** (ranging → visualización)
- **Frecuencia de actualización** promedio y estabilidad
- **Errores de comunicación** MQTT y WiFi

## 🌐 **INTEGRACIÓN WORDPRESS**

### **🔧 Plugin WordPress Profesional:**
El sistema incluye un **plugin WordPress completo** (`wordpress_plugin/tfg-uwb-analytics/`) que permite:

- **📊 Dashboard analytics** completo con canvas interactivo
- **📡 Posición en vivo** desde ESP32 vía WiFi
- **📈 Estadísticas de jugador** con métricas automáticas
- **🗄️ Base de datos MySQL** integrada para almacenamiento persistente
- **🤖 Automatización Python-WordPress** para subida automática de datos

### **📱 Script de Automatización:**
```bash
# Monitoreo automático de nuevos archivos CSV
python integration_scripts/wordpress_auto_upload.py

# Características:
# ✅ Detección automática de archivos nuevos
# ✅ API REST WordPress con autenticación
# ✅ Procesamiento automático de métricas UWB
# ✅ Generación de posts HTML automáticos
```

## 🔧 **SOLUCIÓN DE PROBLEMAS**

### **Hardware:**
- **Ancla no responde** → Verificar alimentación (5V/2A mínimo) y ID único
- **Tag no se localiza** → Mínimo 3 anclas operativas, sin obstáculos metálicos
- **Coordenadas erróneas** → Verificar posiciones de anclas en config.h

### **Software:**
- **Error de imports** → `pip install -r requirements.txt`
- **No hay datos** → Verificar broker MQTT y conectividad WiFi
- **Replay lento** → Usar archivos de datos más pequeños o reducir velocidad

### **Red:**
- **MQTT no conecta** → Verificar firewall y IP del broker
- **ESP32 no conecta WiFi** → Verificar red 2.4GHz y credenciales

## 🏆 **RESULTADOS ESPERADOS**

### **✅ Precisión de Localización:**
- **Error típico:** 30-50cm en condiciones reales
- **Error máximo:** <1m en situaciones adversas
- **Estabilidad:** Trayectorias suaves sin saltos erráticos

### **✅ Rendimiento del Sistema:**
- **Latencia total:** 150-200ms (ranging → visualización)
- **Frecuencia de actualización:** 25-40 Hz constante
- **Disponibilidad:** >95% durante sesiones de 60+ minutos

### **✅ Análisis Deportivo:**
- **Detección automática** de sprints, cambios de dirección y zonas
- **Métricas precisas** de distancia, velocidad y tiempo en zonas
- **Visualización profesional** comparable a sistemas comerciales

## 👨‍💻 **INFORMACIÓN DEL PROYECTO**

### **🎓 TFG 2024-2025:**
- **Autor:** Nicolás Iglesias García
- **Universidad:** Universidad de Oviedo - EPI Gijón
- **Grado:** Ciencia e Ingeniería de Datos
- **Versión:** v2.1-FINAL

### **🚀 Estado del Proyecto:**
- ✅ **Diseño del sistema** - Completado
- ✅ **Hardware adquirido** - 6x ESP32 UWB DW3000 disponibles
- ✅ **Implementación firmware** - Completado
- ✅ **Algoritmos de localización** - Completado
- ✅ **Sistema de análisis** - Completado
- ✅ **Filtros avanzados** - Completado (Kalman + ML)
- ✅ **Sistema de replay** - Completado
- ✅ **Interfaz web integrada** - Completado
- ✅ **Plugin WordPress** - Completado
- 🟡 **Validación experimental** - En progreso con hardware real

### **💡 Valor Agregado:**
- **Sistema escalable** - Desde prototipo académico a solución profesional
- **Integración completa** - Hardware + Software + Web + Base de datos
- **Aplicación real** - Análisis deportivo funcional para fútbol sala
- **Innovación técnica** - Filtros ML + Kalman + UWB + MQTT + WordPress

---

**⚽ Sistema UWB completo para análisis deportivo en fútbol sala ⚽**  
**🌐 Solución integral: Hardware + Software + Web + Análisis IA 🌐**  
**🏆 TFG 2024-2025 - Universidad de Oviedo - EPI Gijón 🏆**