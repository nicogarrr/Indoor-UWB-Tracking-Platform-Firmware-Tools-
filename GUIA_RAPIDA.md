# 🚀 GUÍA RÁPIDA - Sistema UWB TFG Fútbol Sala

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
# data/uwb_data_example_20250621_150000.csv
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

### 5️⃣ **VISUALIZACIÓN INTERACTIVA**

#### Sistema de Replay:
```bash
# Reproducir movimientos en tiempo real
python movement_replay.py
```

**Controles del Replay:**
- `ESPACIO`: Play/Pausa
- `← →`: Frame anterior/siguiente  
- `↑ ↓`: Aumentar/Disminuir velocidad
- `R`: Reiniciar
- `Q`: Salir

### 6️⃣ **ANÁLISIS AVANZADO**

#### Jupyter Notebook (Opcional):
```bash
# Análisis personalizado en notebook
jupyter lab
```

---

## 🔧 **CONFIGURACIÓN RÁPIDA**

### Configuración WiFi/MQTT:
Editar `common/secrets.h`:
```cpp
#define WIFI_SSID "TU_WIFI"
#define WIFI_PASSWORD "TU_PASSWORD" 
#define MQTT_SERVER "192.168.1.100"  // IP de tu broker MQTT
```

### Posiciones de Anclas (ya optimizadas):
```cpp
A10(-1,-1)   - Esquina SW  
A20(-1,21)   - Esquina NW
A30(41,-1)   - Esquina SE
A40(41,21)   - Esquina NE
A50(20,25)   - Lateral Norte
```

---

## 📁 **ESTRUCTURA DE ARCHIVOS**

```
TFG-UWB/
├── data/                    # Datos capturados
├── processed_data/          # Datos procesados  
├── plots/                   # Visualizaciones
├── csv_processor.py         # Procesador principal
├── mqtt_to_csv_collector.py # Colector MQTT
├── movement_replay.py       # Sistema replay
├── requirements.txt         # Dependencias
└── README_DATA_ANALYSIS.md  # Documentación completa
```

---

## ⚡ **FLUJO TÍPICO DE USO**

1. **Configurar hardware** → Programar ESP32s
2. **Iniciar captura** → `python mqtt_to_csv_collector.py`
3. **Realizar pruebas** → Mover tag por la cancha  
4. **Procesar datos** → `python csv_processor.py`
5. **Visualizar** → `python movement_replay.py`
6. **Analizar** → Revisar gráficos y estadísticas

---

## 🆘 **RESOLUCIÓN RÁPIDA DE PROBLEMAS**

| Problema | Solución |
|----------|----------|
| Error de imports | `pip install -r requirements.txt` |
| No hay datos | Verificar broker MQTT y WiFi |
| Gráficos no aparecen | Instalar: `pip install matplotlib seaborn` |
| Replay lento | Usar datos filtrados más pequeños |

---

## 📊 **MÉTRICAS DEL SISTEMA**

- **Precisión**: <50cm objetivo
- **Latencia**: <200ms objetivo  
- **Frecuencia**: 25 Hz constante
- **Cobertura**: Cancha completa 40x20m

¡Tu sistema UWB está listo para analizar rendimiento deportivo! 🏆 