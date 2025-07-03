Sistema de Localización Indoor UWB para Fútbol Sala
====================================================

Introducción
------------
Este proyecto implementa un sistema de localización indoor de alta precisión basado en tecnología **Ultra-Wideband (UWB)** con el chip DW3000 y placas **ESP32**. Está orientado a la captura y análisis de movimiento en fútbol sala, aunque puede adaptarse a otros deportes o entornos interiores.

El sistema consta de los siguientes componentes principales:

1. **Firmware para anclas UWB** (5 archivos `*.ino`).  
2. **Firmware para el tag UWB** (`uwb_tag.ino`).  
3. **Colector de datos MQTT** en Python (`mqtt/uwb_data_collector.py`).  
4. **Sistema de reproducción y análisis** en Python (`replay/movement_replay.py`).  
5. **Conjunto de datos de ejemplo** en formato CSV (directorio `uwb_data/`).

Características técnicas destacadas
----------------------------------
* Posicionamiento con 5 anclas DW3000 y un tag móvil.  
* Protocolo TDMA para evitar colisiones y maximizar la frecuencia de actualización.  
* Firmware optimizado para el microcontrolador ESP32 (modo dual-core).  
* Publicación de datos en tiempo real mediante MQTT.  
* Almacenamiento de mediciones y posiciones en CSV.  
* Reproductor interactivo con filtro de Kalman y predicción mediante Gaussian Process Regression.

Estructura del repositorio
-------------------------
```
TFG OFICIAL/
├── firmware/
│   ├── anchors/
│   │   ├── anchor_1.ino
│   │   ├── anchor_2.ino
│   │   ├── anchor_3.ino
│   │   ├── anchor_4.ino
│   │   └── anchor_5.ino
│   └── tag/
│       └── uwb_tag.ino
├── mqtt/
│   └── uwb_data_collector.py
├── replay/
│   └── movement_replay.py
├── uwb_data/               # Datos experimentales (CSV)
├── requirements.txt        # Dependencias Python
└── pyproject.toml          # Configuración de herramientas de desarrollo
```

Requisitos de hardware
----------------------
* 6 placas **Makerfabs ESP32 UWB DW3000** (5 anclas + 1 tag).  
* Router Wi-Fi 2.4 GHz para la transmisión MQTT.  
* Equipo con Python 3.8 o superior para el análisis de datos.  
* Fuente de alimentación estable de 5 V para las anclas.

Instalación del entorno Python
------------------------------
```bash
# Clonar el repositorio (ejemplo)
git clone https://github.com/usuario/TFG-UWB.git
cd "TFG OFICIAL"

# Crear entorno virtual (opcional)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

Programación del firmware
-------------------------
1. Instalar Arduino IDE 2.x y añadir el paquete de placas **ESP32**.  
2. Seleccionar la placa **ESP32 WROVER Module** con PSRAM habilitada.  
3. Compilar y cargar los siguientes firmwares:
   * `firmware/anchors/anchor_X.ino` (cambiar `X` por 1-5 según la ancla).  
   * `firmware/tag/uwb_tag.ino` para el tag móvil.
4. Configurar en cada archivo los parámetros de red Wi-Fi y, si es necesario, el identificador de ancla (`ID_PONG`).

Uso del sistema
---------------
1. Colocar las anclas alrededor de la pista según la geometría diseñada.  
2. Iniciar el script de captura:
   ```bash
   python mqtt/uwb_data_collector.py
   ```
   Se generarán archivos CSV en la carpeta `uwb_data/`.
3. Después de la sesión, reproducir los datos con:
   ```bash
   python replay/movement_replay.py --file ruta/al/archivo.csv
   ```
   El reproductor permite pausar, ajustar la velocidad y aplicar filtros en tiempo real.

Formato de datos
----------------
* Ranging: `uwb_ranging_YYYYMMDD_HHMMSS.csv`  
  * Columnas: `Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_m,Filtered_Distance_m,Signal_Power_dBm,Anchor_Status`
* Posiciones: `uwb_positions_YYYYMMDD_HHMMSS.csv`  
  * Columnas: `timestamp,tag_id,x,y,anchor_1_dist,anchor_2_dist,anchor_3_dist,anchor_4_dist,anchor_5_dist`

Licencia
--------
Este proyecto se distribuye con fines académicos para el Trabajo de Fin de Grado en la Universidad de Oviedo. El uso comercial está prohibido sin autorización expresa del autor.

Contacto
--------
Autor: Nicolás Iglesias García  
Correo: nico.iglesias@example.com  
Escuela Politécnica de Ingeniería de Gijón, Universidad de Oviedo