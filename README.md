UWB Indoor Localization System for Futsal
==========================================

Introduction
------------
This project implements a high-precision indoor localization system based on **Ultra-Wideband (UWB)** technology with the DW3000 chip and **ESP32** boards. It is oriented towards capturing and analyzing movement in futsal, although it can be adapted to other sports or indoor environments.

The system consists of the following main components:

1. **UWB anchor firmware** (5 `*.ino` files).  
2. **UWB tag firmware** (`uwb_tag.ino`).  
3. **MQTT data collector** in Python (`mqtt/uwb_data_collector.py`).  
4. **Replay and analysis system** in Python (`replay/movement_replay.py`).  
5. **Sample dataset** in CSV format (`uwb_data/` directory).

Key Technical Features
---------------------
* Positioning with 5 DW3000 anchors and one mobile tag.  
* TDMA protocol to avoid collisions and maximize update frequency.  
* Firmware optimized for ESP32 microcontroller (dual-core mode).  
* Real-time data publishing via MQTT.  
* Storage of measurements and positions in CSV format.  
* Interactive player with Kalman filter and prediction using Gaussian Process Regression.

Repository Structure
-------------------
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
├── uwb_data/               # Experimental data (CSV)
├── requirements.txt        # Python dependencies
└── pyproject.toml          # Development tool configuration
```

Hardware Requirements
--------------------
* 6 **Makerfabs ESP32 UWB DW3000** boards (5 anchors + 1 tag).  
* 2.4 GHz Wi-Fi router for MQTT transmission.  
* Computer with Python 3.8 or higher for data analysis.  
* Stable 5V power supply for anchors.

Python Environment Setup
------------------------
```bash
# Clone repository (example)
git clone https://github.com/user/TFG-UWB.git
cd "TFG OFICIAL"

# Create virtual environment (optional)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Firmware Programming
--------------------
1. Install Arduino IDE 2.x and add the **ESP32** board package.  
2. Select **ESP32 WROVER Module** board with PSRAM enabled.  
3. Compile and upload the following firmware:
   * `firmware/anchors/anchor_X.ino` (change `X` to 1-5 according to anchor).  
   * `firmware/tag/uwb_tag.ino` for the mobile tag.
4. Configure Wi-Fi network parameters in each file and, if necessary, the anchor identifier (`ID_PONG`).

System Usage
------------
1. Place anchors around the court according to the designed geometry.  
2. Start the capture script:
   ```bash
   python mqtt/uwb_data_collector.py
   ```
   CSV files will be generated in the `uwb_data/` folder.
3. After the session, replay the data with:
   ```bash
   python replay/movement_replay.py --file path/to/file.csv
   ```
   The player allows pausing, adjusting speed, and applying filters in real time.

Data Format
-----------
* Ranging: `uwb_ranging_YYYYMMDD_HHMMSS.csv`  
  * Columns: `Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_m,Filtered_Distance_m,Signal_Power_dBm,Anchor_Status`
* Positions: `uwb_positions_YYYYMMDD_HHMMSS.csv`  
  * Columns: `timestamp,tag_id,x,y,anchor_1_dist,anchor_2_dist,anchor_3_dist,anchor_4_dist,anchor_5_dist`

License
-------
This project is distributed for academic purposes for the Final Degree Project at the University of Oviedo. Commercial use is prohibited without express authorization from the author.

Contact
-------
Author: Nicolás Iglesias García  
Email: nico.iglesias@example.com  
Polytechnic School of Engineering of Gijón, University of Oviedo