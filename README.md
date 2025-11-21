# TFG-UWB: Indoor UWB Tracking Platform (Firmware & Tools)

## Introduction

### UWB Hardware (Makerfabs)
This project is designed to work with **Makerfabs ESP32 UWB** boards. The following models are compatible:

#### Current Hardware Used
* 6x **[ESP32 UWB DW3000](https://www.makerfabs.com/esp32-uwb-dw3000.html)** boards (5 anchors + 1 tag)
  - **Price**: $43.80 USD per unit
  - **Chip**: DecaWave DW3000 (latest generation)
  - **Advantages**: 66% lower power consumption vs DW1000, Apple U1 compatible, FiRa™ certified
  - **Channels**: Supports UWB channels 5 (6.5 GHz) and 9 (8 GHz)
  - **Range**: Standard indoor range (~30m)

#### Alternative/Upgraded Options
* **[ESP32 UWB Pro High Power 120m](https://www.makerfabs.com/esp32-uwb-high-power-120m.html)** (Recommended for larger areas)
  - **Price**: $51.84 USD per unit (Special offer)
  - **Extended Range**: Up to 120 meters
  - **Better Performance**: Higher power output for challenging environments
  - **Same Compatibility**: Works with existing firmware

* **[ESP32 UWB Pro with Display](https://www.makerfabs.com/esp32-uwb-pro-with-display.html)**
  - **Price**: $54.80 USD per unit
  - **Features**: Built-in OLED display for real-time monitoring
  - **Ideal for**: Development and debugging phases

#### Technical Specifications
- **ESP32**: Dual-core Xtensa 32-bit LX6 (80-240MHz)
- **Memory**: 8MB PSRAM (64Mbit), 4MB Flash
- **Connectivity**: WiFi 802.11b/g/n, Bluetooth v4.2
- **Power**: Sleep mode <5µA, board supply 4.8-5.5V
- **Temperature**: Operating range -40°C to +85°C
- **Dimensions**: 18.0×31.4×3.3mm

### Additional Requirements
* 2.4 GHz Wi-Fi router for MQTT transmission  
* Computer with Python 3.8 or higher for data analysis  
* Stable 5V power supply for anchors (USB or external)

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
   * `firmware/anchors/anchor_X.ino` (change `X` to 1-6 according to anchor).  
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

4. **Analyze Data**:
   ```bash
   python uwb_data/analyze_csv.py
   ```
   Provides statistical metrics (jitter, frequency, packet loss) for a selected file.

5. **Compare Datasets**:
   ```bash
   python uwb_data/compare_csv.py
   ```
   Compares two CSV files side-by-side to evaluate improvements or changes in configuration.

Data Format
-----------
* Ranging: `uwb_ranging_YYYYMMDD_HHMMSS.csv`  
  * Columns: `Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_m,Filtered_Distance_m,Signal_Power_dBm,Anchor_Status`
* Positions: `uwb_positions_YYYYMMDD_HHMMSS.csv`  
  * Columns: `timestamp,tag_id,x,y,anchor_1_dist,anchor_2_dist,anchor_3_dist,anchor_4_dist,anchor_5_dist`

Technical Resources
------------------

### Makerfabs Documentation & Support
* **[ESP32 UWB DW3000 Wiki](https://wiki.makerfabs.com/)** - Official documentation and tutorials
* **[GitHub Repository](https://github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000)** - Official firmware examples
* **[DW3000 Datasheet](https://www.makerfabs.com/)** - Technical specifications from Qorvo/DecaWave
* **[UWB Indoor Positioning Tests](https://www.makerfabs.com/)** - Performance benchmarks and calibration guides

License
-------
This project is distributed for academic purposes for the Final Degree Project at the University of Oviedo. Commercial use is prohibited without express authorization from the author.

Contact
-------
Author: Nicolás Iglesias García  
Email: nicoiglesiasgarcia10@gmail.com  / uo288336@uniovi.es
Polytechnic School of Engineering of Gijón, University of Oviedo