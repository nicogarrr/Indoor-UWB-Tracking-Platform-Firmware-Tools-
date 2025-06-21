# TFG UWB - Sistema de Análisis de Datos

## Descripción

Este conjunto de scripts permite recoger, procesar y analizar los datos del sistema UWB para fútbol sala desarrollado en el TFG. El sistema completo incluye:

1. **Recolección de datos MQTT a CSV** (`mqtt_to_csv_collector.py`)
2. **Procesamiento y limpieza de datos** (`csv_processor.py`)
3. **Replay interactivo de movimientos** (`movement_replay.py`)

## Instalación de Dependencias

```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Para exportación de video (opcional):
# Windows: Descargar FFmpeg y añadir al PATH
# Linux: sudo apt install ffmpeg
# macOS: brew install ffmpeg
```

## Uso del Sistema

### 1. Recolección de Datos MQTT

El recolector se conecta al broker MQTT y guarda automáticamente todos los datos en archivos CSV separados por tipo.

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

**Archivos generados:**
- `ranging_data_YYYYMMDD_HHMMSS.csv` - Datos brutos de ranging UWB
- `position_data_YYYYMMDD_HHMMSS.csv` - Posiciones calculadas y velocidades
- `zones_data_YYYYMMDD_HHMMSS.csv` - Eventos de zonas de fútbol sala
- `metrics_data_YYYYMMDD_HHMMSS.csv` - Métricas de rendimiento del sistema

**Controles durante recolección:**
- `Ctrl+C` - Detener recolector y mostrar estadísticas finales
- Las estadísticas se muestran automáticamente cada 30 segundos

### 2. Procesamiento de Datos

El procesador limpia los datos brutos, elimina outliers, interpola datos faltantes y genera datasets limpios.

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

**Procesamiento realizado:**
- ✅ Filtrado de distancias fuera de rango (10cm - 60m)
- ✅ Eliminación de mediciones con RSSI inválido
- ✅ Detección de outliers usando IQR por ancla
- ✅ Filtrado de velocidades imposibles (>12 m/s para fútbol sala)
- ✅ Eliminación de saltos teleportación (>15 m/s)
- ✅ Interpolación a frecuencia constante (25 Hz)
- ✅ Suavizado con filtro Savitzky-Golay
- ✅ Generación de estadísticas resumidas

**Archivos generados:**
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

### 3. Replay de Movimientos

Sistema interactivo para visualizar y analizar los movimientos capturados.

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

**Controles del replay interactivo:**
- `SPACE` - Play/Pause
- `← →` - Frame anterior/siguiente
- `↑ ↓` - Aumentar/disminuir velocidad de replay
- `R` - Reiniciar desde el principio
- `Q` - Salir

**Características del replay:**
- 🎯 Visualización de cancha de fútbol sala (40x20m) con líneas oficiales
- 📍 Posiciones de anclas UWB optimizadas
- 🏃 Trayectoria del jugador con trail dinámico
- 🎨 Zonas de análisis deportivo (áreas de portería, centro campo, etc.)
- 📊 Panel de información en tiempo real (posición, velocidad, zona actual)
- ⚡ Velocidad de replay ajustable (0.1x a 10x)

## Estructura de Datos CSV

### Ranging Data
```csv
timestamp_system,timestamp_device,tag_id,anchor_id,distance_raw_cm,distance_filtered_cm,rssi_dbm,anchor_responded,session_id
1701434422.123,45231,1,10,234.5,235.1,-87.2,True,20241201_143022
```

### Position Data
```csv
timestamp_system,timestamp_device,tag_id,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,speed_ms,prediction_x_m,prediction_y_m,responding_anchors,update_rate_hz,session_id
1701434422.123,45231,1,15.3,8.7,2.1,0.5,2.16,15.4,8.8,5,25.0,20241201_143022
```

### Zones Data
```csv
timestamp_system,timestamp_device,tag_id,zone_name,action,position_x_m,position_y_m,velocity_x_ms,velocity_y_ms,duration_ms,session_id
1701434422.123,45231,1,Area_Porteria_1,enter,2.1,4.2,1.8,0.3,0,20241201_143022
```

## Configuración del Sistema UWB

### Posiciones de Anclas Optimizadas
```
A10(-1,-1)   - Esquina SW (fuera cancha)
A20(-1,21)   - Esquina NW (fuera cancha)  
A30(41,-1)   - Esquina SE (fuera cancha)
A40(41,21)   - Esquina NE (fuera cancha)
A50(20,25)   - Lateral Norte (fuera cancha)
```

### Zonas de Análisis Deportivo
- **Área Portería 1** (2.0, 4.0) - Radio 3m
- **Área Portería 2** (38.0, 4.0) - Radio 3m
- **Centro Campo** (20.0, 10.0) - Radio 3m
- **Medio Campo 1** (10.0, 10.0) - Radio 5m
- **Medio Campo 2** (30.0, 10.0) - Radio 5m
- **Banda Lateral** (20.0, 2.0) - Radio 8m

## Parámetros de Filtrado

### Datos de Ranging
- **Distancia mínima:** 10 cm (limitación física UWB)
- **Distancia máxima:** 60 m (rango interior razonable)
- **RSSI mínimo:** -120 dBm
- **RSSI máximo:** -30 dBm

### Datos de Posición
- **Velocidad máxima:** 12 m/s (fútbol sala)
- **Salto máximo:** 15 m/s (detección teleportación)
- **Anclas mínimas:** 3 (para trilateración válida)
- **Margen cancha:** 5 m (posiciones fuera válidas)

### Interpolación
- **Frecuencia objetivo:** 25 Hz (40ms entre muestras)
- **Método:** Interpolación lineal + filtro Savitzky-Golay
- **Ventana suavizado:** 11 puntos (440ms)

## Análisis de Rendimiento

El sistema genera automáticamente métricas de rendimiento:

### Métricas de Trilateración
- Tasa de éxito de trilateración
- Porcentaje de timestamps con <3 anclas
- Porcentaje de cobertura completa (5 anclas)

### Métricas de Latencia
- Latencia promedio extremo-a-extremo (ranging → MQTT)
- Frecuencia de actualización promedio
- Fallos de publicación MQTT

### Métricas Deportivas
- Distancia total recorrida
- Velocidad promedio y máxima
- Tiempo en sprint (>6 m/s)
- Tiempo estático (<0.5 m/s)
- Eventos de zona por minuto

## Troubleshooting

### Error: "No se encontraron archivos de ranging data"
- Verificar que el recolector MQTT haya capturado datos
- Revisar el directorio de datos especificado
- Confirmar que el tag esté publicando en el topic correcto

### Error: "No se encontraron datos de posición procesados"
- Ejecutar primero el procesador CSV
- Verificar que haya datos de posición en los CSV brutos
- Revisar que al menos 3 anclas estén respondiendo

### Replay muy lento o errático
- Reducir la velocidad de replay con teclas ↓
- Verificar que los datos interpolados estén disponibles
- Cerrar otras aplicaciones que usen matplotlib

### Datos de mala calidad
- Revisar posicionamiento de anclas UWB
- Verificar interferencias en 6.5 GHz
- Ajustar parámetros de filtrado en el código
- Aumentar duración de captura para más datos

## Ejemplos de Uso Típicos

### Sesión de Entrenamiento Completa
```bash
# 1. Iniciar recolección
python mqtt_to_csv_collector.py --output-dir ./entrenamiento_20241201

# 2. Realizar entrenamiento (el script sigue capturando)
# 3. Detener con Ctrl+C

# 4. Procesar datos
python csv_processor.py --data-dir ./entrenamiento_20241201

# 5. Analizar movimientos
python movement_replay.py --data-dir ./processed_data
```

### Análisis de Múltiples Sesiones
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

## Contacto y Soporte

Para dudas sobre el sistema de análisis de datos del TFG UWB:
- Revisar logs de error en la consola
- Verificar configuración de broker MQTT
- Comprobar que las anclas estén transmitiendo correctamente

---

**TFG - Sistema GPS Indoor para Fútbol Sala**  
**Universidad:** [Tu Universidad]  
**Autor:** [Tu Nombre]  
**Año:** 2024 