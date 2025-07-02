# TFG UWB Data Collector Ultimate - Optimized for anchors 1-5
"""
Optimized UWB data collector with:
- Automatic MQTT broker detection
- Thread-safe high frequency data capture
- No real-time filtering (post-processing)
- Real-time statistics
- Compatible with anchors 1, 2, 3, 4, 5
- All distances in meters (no unit conversion needed)
"""

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import datetime
import os
import time
import json
import argparse
import signal
import sys
from threading import Lock

# ===== CONFIGURACIONES OPTIMIZADAS =====
DEFAULT_BROKERS = [
    ("172.20.10.2", "iPhone Hotspot"),
    ("192.168.1.100", "WiFi Home"),
    ("192.168.4.1", "ESP32 AP"),
    ("127.0.0.1", "Local Test")
]

# OPTIMIZADO: Timeouts reducidos para eliminar gaps
MQTT_CONNECT_TIMEOUT = 1  # REDUCIDO: 1s vs 3s
MQTT_KEEPALIVE = 15       # REDUCIDO: Keep-alive más agresivo
MQTT_LOOP_TIMEOUT = 0.01  # OPTIMIZADO: Loop más responsivo

class UWBDataCollector:
    def __init__(self, mqtt_server=None, mqtt_port=1883, output_dir="uwb_data"):
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.output_dir = output_dir
        
        # Crear directorio de salida
        os.makedirs(output_dir, exist_ok=True)
        
        # Archivos con timestamp único
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # *** ARCHIVOS PRINCIPALES PARA ANCLAS 1-5 ***
        self.ranging_file = os.path.join(output_dir, f"uwb_ranging_{timestamp}.csv")
        self.positions_file = os.path.join(output_dir, f"uwb_positions_{timestamp}.csv")
        
        # Headers - all distances in meters (no conversion needed)
        self.RANGING_HEADER = "Tag_ID,Timestamp_ms,Anchor_ID,Raw_Distance_m,Filtered_Distance_m,Signal_Power_dBm,Anchor_Status"
        self.POSITIONS_HEADER = "timestamp,tag_id,x,y,anchor_1_dist,anchor_2_dist,anchor_3_dist,anchor_4_dist,anchor_5_dist"
        
        # Archivos handles
        self.ranging_handle = None
        self.positions_handle = None
        
        # Thread safety
        self.file_lock = Lock()
        
        # Estadísticas mejoradas
        self.stats = {
            'total_messages': 0,
            'ranging_messages': 0,
            'position_messages': 0,
            'positions_in_bounds': 0,
            'positions_out_bounds': 0,
            'weak_signals': 0,
            'strong_signals': 0,
            'last_position': None,
            'last_timestamp': None,
            'start_time': time.time(),
            'anchor_stats': {str(i): {'total': 0, 'responses': 0, 'rssi_sum': 0} for i in [1, 2, 3, 4, 5]},
            'session_id': timestamp
        }
        
        # Cliente MQTT (API v2)
        client_id = f"uwb-collector-{timestamp}-{os.getpid()}"
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Configuración optimizada para alta frecuencia
        self.client.max_inflight_messages_set(200)
        self.client.max_queued_messages_set(1000)
        
        # Inicializar archivos
        self.init_csv_files()
        
        print(f"TFG UWB Data Collector ULTIMATE")
        print(f"Output directory: {output_dir}")
        print(f"Configuration: Anchors 1-5, maximum capture, all data in meters")
        print("=" * 60)

    def init_csv_files(self):
        """Initialize CSV files with headers"""
        try:
            # Archivo de ranging (datos brutos)
            self.ranging_handle = open(self.ranging_file, 'w', buffering=1)
            self.ranging_handle.write(self.RANGING_HEADER + '\n')
            print(f"Ranging file: {os.path.basename(self.ranging_file)}")
            
            # Archivo de posiciones (para replay)
            self.positions_handle = open(self.positions_file, 'w', buffering=1) 
            self.positions_handle.write(self.POSITIONS_HEADER + '\n')
            print(f"Positions file: {os.path.basename(self.positions_file)}")
            
        except Exception as e:
            print(f"Error creating files: {e}")
            sys.exit(1)

    def detect_mqtt_broker(self):
        """Detect available MQTT broker automatically"""
        if self.mqtt_server:
            # Broker especificado manualmente
            return self.mqtt_server, "Manual"
            
        print("Detecting MQTT broker automatically...")
        
        for broker_ip, network_name in DEFAULT_BROKERS:
            try:
                print(f"   Testing {broker_ip} ({network_name})...")
                test_client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="uwb_test")
                test_client.connect(broker_ip, self.mqtt_port, MQTT_CONNECT_TIMEOUT)  # OPTIMIZADO: 1s timeout
                test_client.loop_start()
                time.sleep(0.5)  # REDUCIDO: 0.5s vs 1s
                test_client.disconnect()
                test_client.loop_stop()
                
                print(f"Broker found: {broker_ip} ({network_name})")
                return broker_ip, network_name
                
            except Exception as e:
                print(f"   Failed {broker_ip}: {str(e)[:40]}...")
                continue
        
        return None, None

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connection callback"""
        if rc == 0:
            print(f"Connected to MQTT broker (rc={rc})")
            
            # Suscribirse a topics del tag actual
            topics = [
                ("uwb/tag/logs", 0),           # Datos ranging CSV
                ("uwb/tag/+/status", 0),       # Estados JSON con posición
                ("uwb/indoor/logs", 0),        # Datos indoor adicionales  
                ("uwb/tag/+/raw", 0),          # Datos crudos si existen
            ]
            
            for topic, qos in topics:
                client.subscribe(topic, qos)
                print(f"Subscribed: {topic}")
                
        else:
            print(f"MQTT connection error (rc={rc})")

    def on_disconnect(self, client, userdata, flags, rc, properties=None):
        """MQTT disconnection callback"""
        print(f"Disconnected from broker (rc={rc})")

    def on_message(self, client, userdata, msg):
        """Process MQTT messages thread-safe"""
        try:
            timestamp_system = time.time()
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            with self.file_lock:
                self.stats['total_messages'] += 1
            
            # Procesar según topic
            if topic in ["uwb/tag/logs", "uwb/indoor/logs"]:
                self.process_ranging_data(payload, timestamp_system)
                
            elif topic.startswith("uwb/tag/") and topic.endswith("/status"):
                self.process_position_data(payload, timestamp_system)
                
            # Log topics desconocidos (debug)
            elif self.stats['total_messages'] % 200 == 0:
                print(f"Unknown topic: {topic}")

            # Estadísticas cada 100 mensajes
            if self.stats['total_messages'] % 100 == 0:
                self.print_statistics()
                
        except Exception as e:
            print(f"Error processing message: {e}")

    def process_ranging_data(self, payload, timestamp_system):
        """Process ranging CSV data - already in meters, no conversion needed"""
        try:
            with self.file_lock:
                self.stats['ranging_messages'] += 1
            
            if payload and len(payload.split(',')) >= 7:
                try:
                    parts = payload.split(',')
                    anchor_id = parts[2]
                    raw_distance_m = float(parts[3])       # Already in meters
                    filtered_distance_m = float(parts[4])  # Already in meters
                    signal_power = float(parts[5])
                    anchor_status = int(parts[6])
                    
                    if anchor_id in self.stats['anchor_stats']:
                        with self.file_lock:
                            self.stats['anchor_stats'][anchor_id]['total'] += 1
                            
                            if anchor_status == 1:
                                self.stats['anchor_stats'][anchor_id]['responses'] += 1
                                self.stats['anchor_stats'][anchor_id]['rssi_sum'] += signal_power
                            
                            # Clasificar señales
                            if signal_power > -90:
                                self.stats['strong_signals'] += 1
                            else:
                                self.stats['weak_signals'] += 1
                                
                except Exception as e:
                    print(f"Error processing ranging statistics: {e}")
                
                # Escribir datos (SIN FILTROS)
                if self.ranging_handle:
                    with self.file_lock:
                        self.ranging_handle.write(payload + '\n')
                        
        except Exception as e:
            print(f"Error ranging data: {e}")

    def process_position_data(self, payload, timestamp_system):
        """Process position JSON data - already in meters, no conversion needed"""
        try:
            with self.file_lock:
                self.stats['position_messages'] += 1
            
            data = json.loads(payload)
            tag_id = data.get('tag_id', 0)
            
            if 'position' in data:
                pos = data['position']
                x = pos.get('x', 0.0)
                y = pos.get('y', 0.0)
                
                # Estadísticas de posición (informativo)
                with self.file_lock:
                    if -10.0 <= x <= 10.0 and -5.0 <= y <= 15.0:  # Rango extendido
                        self.stats['positions_in_bounds'] += 1
                    else:
                        self.stats['positions_out_bounds'] += 1
                    
                    self.stats['last_position'] = [x, y]
                    self.stats['last_timestamp'] = timestamp_system

                # Obtener distancias a anclas (mapeo flexible)
                ad = data.get('anchor_distances', {})
                anchor_distances = {}
                
                for i in range(1, 6):
                    key = str(i)
                    # Direct assignment - no conversion needed
                    distance = ad.get(key, ad.get(str(i*10), 0.0))
                    anchor_distances[key] = distance

                # Timestamp formato legible
                dt_timestamp = datetime.datetime.fromtimestamp(timestamp_system)
                
                # Escribir al archivo de posiciones
                if self.positions_handle:
                    row = [
                        dt_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                        tag_id,
                        x,
                        y,
                        anchor_distances['1'],
                        anchor_distances['2'],
                        anchor_distances['3'],
                        anchor_distances['4'],
                        anchor_distances['5']
                    ]
                    
                    with self.file_lock:
                        self.positions_handle.write(','.join(str(v) for v in row) + '\n')
                        
        except Exception as e:
            print(f"Error position data: {e}")

    def print_statistics(self):
        """Print comprehensive real-time statistics"""
        uptime = time.time() - self.stats['start_time']
        
        print(f"\nUWB COLLECTOR STATISTICS ({uptime:.0f}s)")
        print("=" * 50)
        print(f"Total messages: {self.stats['total_messages']}")
        print(f"Ranging: {self.stats['ranging_messages']} ({self.stats['ranging_messages']/max(1,uptime):.1f}/s)")
        print(f"Positions: {self.stats['position_messages']} ({self.stats['position_messages']/max(1,uptime):.1f}/s)")
        
        # Calidad de datos
        if self.stats['position_messages'] > 0:
            in_bounds_pct = self.stats['positions_in_bounds'] / self.stats['position_messages'] * 100
            print(f"In valid area: {in_bounds_pct:.1f}%")
        
        if self.stats['weak_signals'] + self.stats['strong_signals'] > 0:
            strong_pct = self.stats['strong_signals'] / (self.stats['weak_signals'] + self.stats['strong_signals']) * 100
            print(f"Strong signals: {strong_pct:.1f}%")
        
        # Anclas individuales
        print(f"\nPer anchor:")
        for anchor_id, anchor_stats in self.stats['anchor_stats'].items():
            if anchor_stats['total'] > 0:
                response_rate = anchor_stats['responses'] / anchor_stats['total'] * 100
                avg_rssi = anchor_stats['rssi_sum'] / anchor_stats['responses'] if anchor_stats['responses'] > 0 else 0
                print(f"  A{anchor_id}: {response_rate:.0f}% resp, {avg_rssi:.0f}dBm")
        print("=" * 50)

    def run(self):
        """Execute main collector"""
        try:
            # Detectar broker
            broker_ip, network_name = self.detect_mqtt_broker()
            if not broker_ip:
                print("No MQTT broker available")
                print("Solutions:")
                print("   - Enable iPhone hotspot 'iPhone de Nicolas'")  
                print("   - Connect to home WiFi 'MOVISTAR_PLUS_40B0'")
                print("   - Run local broker: mosquitto -v -p 1883")
                return False
                
            self.mqtt_server = broker_ip
            print(f"Using broker: {broker_ip} ({network_name})")
            
            # Conectar
            self.client.connect(self.mqtt_server, self.mqtt_port, MQTT_KEEPALIVE)
            
            # Handler para Ctrl+C
            def signal_handler(sig, frame):
                print(f"\nStopping collector...")
                self.cleanup()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            
            print("Collector started. Ctrl+C to stop.")
            print("Capturing UWB data - all measurements in meters")
            
            # Loop principal
            last_stats = time.time()
            self.client.loop_start()
            
            while True:
                time.sleep(MQTT_LOOP_TIMEOUT)
                
                # Stats cada 30 segundos
                if time.time() - last_stats > 30:
                    self.print_statistics()
                    last_stats = time.time()
                    
            return True
            
        except Exception as e:
            print(f"Error in collector: {e}")
            return False
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        print("\nCleaning up resources...")
        
        if self.client.is_connected():
            self.client.loop_stop()
            self.client.disconnect()
            
        if self.ranging_handle:
            self.ranging_handle.close()
            print(f"Ranging closed: {os.path.basename(self.ranging_file)}")
            
        if self.positions_handle:
            self.positions_handle.close()
            print(f"Positions closed: {os.path.basename(self.positions_file)}")
            
        self.print_statistics()
        print("Collector stopped correctly")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TFG UWB - Ultimate Collector for Anchors 1-5")
    parser.add_argument("--mqtt-server", help="MQTT broker IP (auto-detection if not specified)")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--output-dir", default="uwb_data", help="Output directory")
    
    args = parser.parse_args()
    
    collector = UWBDataCollector(
        mqtt_server=args.mqtt_server,
        mqtt_port=args.mqtt_port,
        output_dir=args.output_dir
    )
    
    success = collector.run()
    sys.exit(0 if success else 1)