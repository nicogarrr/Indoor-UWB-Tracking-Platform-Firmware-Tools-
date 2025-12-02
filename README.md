# TFG-UWB: Indoor UWB Tracking Platform (Firmware & Tools)

## Introduction

### UWB Hardware (Makerfabs)
This project is designed to work with **Makerfabs ESP32 UWB** boards.

#### Hardware Used
* 6x **[ESP32 UWB DW3000](https://www.makerfabs.com/esp32-uwb-dw3000.html)** boards (6 anchors + 1 tag)



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

Technical Architecture (Firmware)
---------------------------------
The firmware (`uwb_tag.ino`) is built on a **Dual-Core FreeRTOS** architecture to maximize performance and stability.

### 1. Dual-Core Distribution
The ESP32 has two cores (Core 0 and Core 1). We utilize both to decouple critical tasks:
*   **Core 1 (Real-Time Physics)**: Dedicated exclusively to UWB ranging and position calculation. It runs the `TaskUWB` loop without interruption from WiFi or network jitter.
*   **Core 0 (Communications)**: Handles WiFi, MQTT, and the WebServer (`TaskComms`). This ensures that network latency never blocks the UWB measurement process.

### 2. FreeRTOS Implementation
*   **TaskUWB**: Runs at high priority. Manages the DW3000 chip, handles the DS-TWR state machine, and calculates position using WLSQ + Kalman Filter.
*   **TaskComms**: Runs at lower priority. Reads calculated positions from a queue and broadcasts them via MQTT and WebSockets.
*   **Inter-Task Communication**:
    *   **Queue (`uwbQueue`)**: Used to pass `TagDataPacket` structures from Core 1 to Core 0 safely.
    *   **Mutex (`dataMutex`)**: Protects shared global variables to prevent race conditions when reading/writing status data.

### 3. DS-TWR Protocol (Distance Measurement)
We implement the **Double-Sided Two-Way Ranging (DS-TWR)** protocol for sub-10cm precision. Unlike Single-Sided TWR, this method cancels out clock drift errors between the Tag and Anchors.
*   **Step 1 (Poll)**: Tag sends a Poll message.
*   **Step 2 (Response)**: Anchor replies with a Response message.
*   **Step 3 (Final)**: Tag sends a Final message containing timestamps.
*   **Step 4 (Report)**: Anchor calculates the time-of-flight and sends a Report back to the Tag with the distance.

Data Format
-----------
* Ranging: `uwb_ranging_YYYYMMDD_HHMMSS.csv`  
  * Columns: `Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_m,Filtered_Distance_m,Signal_Power_dBm,Anchor_Status`
* Positions: `uwb_positions_YYYYMMDD_HHMMSS.csv`  
  * Columns: `timestamp,tag_id,x,y,anchor_1_dist,anchor_2_dist,anchor_3_dist,anchor_4_dist,anchor_5_dist`

System Performance
------------------
Based on experimental data (Nov 28, 2025), the system achieves the following precision metrics:

* **Update Frequency**: ~36 Hz (Real-Time)
* **Static Precision (Jitter)**:
  * **X-Axis**: ±0.10 m (10 cm)
  * **Y-Axis**: ±0.09 m (9 cm)
* **Dynamic Accuracy (Walking)**:
  * **Linearity (RMSE)**: ~0.20 m (20 cm)
  * **Mean Deviation**: ~0.13 m (13 cm)
* **Latency**: < 25ms per position update

Technical Resources
-------------------

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
