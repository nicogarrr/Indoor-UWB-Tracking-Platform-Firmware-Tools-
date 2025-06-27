#!/usr/bin/env python3
"""
TFG - Sistema GPS Indoor para Fútbol Sala
Recolector de datos MQTT a CSV
Autor: TFG UWB System
Versión: 1.0

Captura todos los datos de ranging y posición del sistema UWB via MQTT
y los almacena en archivos CSV para análisis posterior.
"""

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import csv
import json
import time
import datetime
import os
import argparse
import signal
import sys
from threading import Lock

class MQTTToCSVCollector:
    def __init__(self, mqtt_server="172.20.10.3", mqtt_port=1883, output_dir="data"):
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.output_dir = output_dir
        
        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Archivos CSV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # *** ARCHIVO PRINCIPAL COMPATIBLE CON MOVEMENT_REPLAY.PY ***
        self.main_file = os.path.join(output_dir, f"uwb_data_futsal_game_{timestamp}.csv")
        
        # Archivos especializados (opcionales)
        self.ranging_file = os.path.join(output_dir, f"ranging_data_{timestamp}.csv")
        self.zones_file = os.path.join(output_dir, f"zones_data_{timestamp}.csv")
        self.metrics_file = os.path.join(output_dir, f"metrics_data_{timestamp}.csv")
        
        # Contadores y estadísticas
        self.main_count = 0
        self.ranging_count = 0
        self.zones_count = 0
        self.metrics_count = 0
        self.start_time = time.time()
        
        # Lock para escritura thread-safe
        self.file_lock = Lock()
        
        # Cliente MQTT (API v2 para evitar deprecation warning)
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="uwb_data_collector")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Inicializar archivos CSV con headers
        self.init_csv_files()
        
        print(f"🎯 TFG UWB Data Collector iniciado")
        print(f"📂 Directorio de salida: {output_dir}")
        print(f"🔗 MQTT Broker: {mqtt_server}:{mqtt_port}")
        print(f"📁 Archivos:")
        print(f"   ⭐ PRINCIPAL (Replay): {self.main_file}")
        print(f"   • Ranging: {self.ranging_file}")
        print(f"   • Zonas: {self.zones_file}")
        print(f"   • Métricas: {self.metrics_file}")
        print("=" * 60)
    
    def init_csv_files(self):
        """Inicializar archivos CSV con headers apropiados"""
        
        # *** ARCHIVO PRINCIPAL COMPATIBLE CON MOVEMENT_REPLAY.PY ***
        # Formato requerido: timestamp, x, y, tag_id + columnas adicionales UWB
        with open(self.main_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'tag_id', 'x', 'y',
                'anchor_10_dist', 'anchor_20_dist', 'anchor_30_dist', 
                'anchor_40_dist', 'anchor_50_dist'
            ])
        
        # Archivo de ranging (datos brutos UWB)
        with open(self.ranging_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_system', 'timestamp_device', 'tag_id', 'anchor_id',
                'distance_raw_cm', 'distance_filtered_cm', 'rssi_dbm', 
                'anchor_responded', 'session_id'
            ])
        
        # Archivo de zonas (eventos de fútbol sala)
        with open(self.zones_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_system', 'timestamp_device', 'tag_id',
                'zone_name', 'action', 'position_x_m', 'position_y_m',
                'velocity_x_ms', 'velocity_y_ms', 'duration_ms', 'session_id'
            ])
        
        # Archivo de métricas (rendimiento del sistema)
        with open(self.metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_system', 'timestamp_device', 'tag_id',
                'total_cycles', 'successful_triangulations', 'triangulation_success_rate',
                'less_than_3_anchors', 'full_coverage', 'full_coverage_rate',
                'average_latency_ms', 'average_update_rate_hz', 'mqtt_failures',
                'session_id'
            ])
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de conexión MQTT"""
        if rc == 0:
            print(f"✅ Conectado al broker MQTT (rc={rc})")
            
            # Suscribirse a todos los topics relevantes
            topics = [
                "uwb/tag/logs",           # Datos de ranging brutos (tag.ino)
                "uwb/tag/+/status",       # Estado de tags (tag.ino con posición)
                "uwb/indoor/logs",        # Datos indoor (tag_indoor.ino)
                "uwb/futsal/zones",       # Eventos de zonas
                "uwb/futsal/performance", # Eventos de rendimiento
                "uwb/futsal/metrics",     # Métricas del sistema
                "uwb/anchor/+/metrics",   # Métricas de anclas
                "uwb/+/+/status",         # Todos los status de tags
            ]
            
            for topic in topics:
                client.subscribe(topic)
                print(f"📡 Suscrito a: {topic}")
                
        else:
            print(f"❌ Error de conexión MQTT (rc={rc})")
    
    def on_disconnect(self, client, userdata, rc, properties=None):
        """Callback de desconexión MQTT"""
        print(f"🔌 Desconectado del broker MQTT (rc={rc})")
    
    def on_message(self, client, userdata, msg):
        """Procesar mensajes MQTT entrantes"""
        try:
            timestamp_system = time.time()
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Generar session_id basado en hora de inicio
            session_id = datetime.datetime.fromtimestamp(self.start_time).strftime("%Y%m%d_%H%M%S")
            
            # Procesar según el topic
            if topic == "uwb/tag/logs" or topic == "uwb/indoor/logs":
                self.process_ranging_data(payload, timestamp_system, session_id)
            
            elif topic.startswith("uwb/tag/") and topic.endswith("/status"):
                self.process_position_data(payload, timestamp_system, session_id)
            
            elif topic == "uwb/futsal/zones":
                self.process_zones_data(payload, timestamp_system, session_id)
            
            elif topic == "uwb/futsal/performance":
                self.process_performance_data(payload, timestamp_system, session_id)
            
            elif topic == "uwb/futsal/metrics":
                self.process_metrics_data(payload, timestamp_system, session_id)
            
            elif topic.startswith("uwb/anchor/") and topic.endswith("/metrics"):
                self.process_anchor_metrics(payload, timestamp_system, session_id)
                
        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")
            print(f"   Topic: {topic}")
            print(f"   Payload: {payload[:100]}...")
    
    def process_ranging_data(self, payload, timestamp_system, session_id):
        """Procesar datos de ranging CSV del tag"""
        try:
            # Formato: TAG_ID,timestamp_ms,anchor_id,distance_raw,distance_filtered,rssi,responded
            parts = payload.strip().split(',')
            if len(parts) >= 7:
                with self.file_lock:
                    with open(self.ranging_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp_system,      # timestamp_system
                            int(parts[1]),         # timestamp_device (ms desde boot)
                            int(parts[0]),         # tag_id
                            int(parts[2]),         # anchor_id
                            float(parts[3]),       # distance_raw_cm
                            float(parts[4]),       # distance_filtered_cm
                            float(parts[5]),       # rssi_dbm
                            bool(int(parts[6])),   # anchor_responded
                            session_id
                        ])
                self.ranging_count += 1
                
        except Exception as e:
            print(f"❌ Error en ranging data: {e}")
    
    def process_position_data(self, payload, timestamp_system, session_id):
        """Procesar datos de posición JSON del tag"""
        try:
            data = json.loads(payload)
            tag_id = data.get('tag_id', 0)
            timestamp_device = data.get('timestamp_ms', 0)
            
            # Datos de posición desde web interface (/data endpoint)
            if 'position' in data:
                pos = data['position']
                vel = data.get('velocity', {})
                pred = data.get('prediction', {})
                quality = data.get('quality', {})
                
                # *** ESCRIBIR AL ARCHIVO PRINCIPAL (COMPATIBLE MOVEMENT_REPLAY.PY) ***
                # Convertir timestamp a formato datetime
                dt_timestamp = datetime.datetime.fromtimestamp(timestamp_system)
                
                # Obtener distancias a las anclas (simuladas si no están disponibles)
                anchor_distances = data.get('anchor_distances', {})
                
                with self.file_lock:
                    with open(self.main_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            dt_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],  # timestamp
                            tag_id,                                             # tag_id
                            pos.get('x', 0.0),                                 # x
                            pos.get('y', 0.0),                                 # y
                            anchor_distances.get('10', 0.0),                   # anchor_10_dist
                            anchor_distances.get('20', 0.0),                   # anchor_20_dist
                            anchor_distances.get('30', 0.0),                   # anchor_30_dist
                            anchor_distances.get('40', 0.0),                   # anchor_40_dist
                            anchor_distances.get('50', 0.0)                    # anchor_50_dist
                        ])
                self.main_count += 1
                
                # *** TAMBIÉN ESCRIBIR AL ARCHIVO DE RANGING (HISTÓRICO) ***
                with self.file_lock:
                    with open(self.ranging_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp_system,
                            timestamp_device,
                            tag_id,
                            pos.get('x', 0.0),
                            pos.get('y', 0.0),
                            vel.get('x', 0.0),
                            vel.get('y', 0.0),
                            vel.get('speed', 0.0),
                            pred.get('x', 0.0),
                            pred.get('y', 0.0),
                            quality.get('responding_anchors', 0),
                            quality.get('update_rate_hz', 0.0),
                            session_id
                        ])
                self.ranging_count += 1
                
        except Exception as e:
            print(f"❌ Error en position data: {e}")
    
    def process_zones_data(self, payload, timestamp_system, session_id):
        """Procesar eventos de zonas de fútbol sala"""
        try:
            data = json.loads(payload)
            
            with self.file_lock:
                with open(self.zones_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp_system,
                        data.get('timestamp', 0),
                        data.get('tag_id', 0),
                        data.get('zone_name', ''),
                        data.get('action', ''),
                        data.get('position', {}).get('x', 0.0),
                        data.get('position', {}).get('y', 0.0),
                        data.get('velocity', {}).get('x', 0.0),
                        data.get('velocity', {}).get('y', 0.0),
                        data.get('duration_ms', 0),
                        session_id
                    ])
            self.zones_count += 1
            
        except Exception as e:
            print(f"❌ Error en zones data: {e}")
    
    def process_performance_data(self, payload, timestamp_system, session_id):
        """Procesar eventos de rendimiento deportivo"""
        try:
            data = json.loads(payload)
            # Similar a zones pero para sprints, etc.
            self.process_zones_data(payload, timestamp_system, session_id)
            
        except Exception as e:
            print(f"❌ Error en performance data: {e}")
    
    def process_metrics_data(self, payload, timestamp_system, session_id):
        """Procesar métricas del sistema"""
        try:
            data = json.loads(payload)
            metrics = data.get('metrics', {})
            
            with self.file_lock:
                with open(self.metrics_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp_system,
                        data.get('timestamp', 0),
                        data.get('tag_id', 0),
                        metrics.get('total_cycles', 0),
                        metrics.get('successful_triangulations', 0),
                        metrics.get('triangulation_success_rate', 0.0),
                        metrics.get('less_than_3_anchors', 0),
                        metrics.get('full_coverage', 0),
                        metrics.get('full_coverage_rate', 0.0),
                        metrics.get('average_latency_ms', 0.0),
                        metrics.get('average_update_rate_hz', 0.0),
                        metrics.get('mqtt_failures', 0),
                        session_id
                    ])
            self.metrics_count += 1
            
        except Exception as e:
            print(f"❌ Error en metrics data: {e}")
    
    def process_anchor_metrics(self, payload, timestamp_system, session_id):
        """Procesar métricas de anclas (opcional)"""
        try:
            # Podrías expandir esto para métricas específicas de anclas
            pass
        except Exception as e:
            print(f"❌ Error en anchor metrics: {e}")
    
    def print_statistics(self):
        """Imprimir estadísticas de recolección"""
        uptime = time.time() - self.start_time
        print(f"\n📊 Estadísticas de recolección:")
        print(f"   ⏱️  Tiempo activo: {uptime:.1f}s")
        print(f"   ⭐ Datos principales (replay): {self.main_count}")
        print(f"   📏 Datos ranging: {self.ranging_count}")
        print(f"   🏟️  Eventos zonas: {self.zones_count}")
        print(f"   📈 Métricas: {self.metrics_count}")
        if uptime > 0:
            print(f"   📊 Tasa principal: {self.main_count/uptime:.1f} msgs/s")
            print(f"   📊 Tasa ranging: {self.ranging_count/uptime:.1f} msgs/s")
        print(f"   📁 Archivo principal: {os.path.basename(self.main_file)}")
        
        # Información de compatibilidad
        if self.main_count > 0:
            print(f"\n✅ Archivo COMPATIBLE con movement_replay.py")
            print(f"   Para usar: python movement_replay.py \"{self.main_file}\"")
        else:
            print(f"\n⚠️  Sin datos de posición aún...")
    
    def detect_mqtt_broker(self):
        """Detectar broker MQTT disponible en diferentes redes"""
        brokers_to_try = [
            ("172.20.10.2", "iPhone hotspot (IP real)"),
            ("172.20.10.3", "iPhone hotspot (IP anterior)"),
            ("192.168.1.38", "WiFi casa MOVISTAR"),
            ("localhost", "Local"),
            ("127.0.0.1", "Local IP")
        ]
        
        for broker_ip, network_name in brokers_to_try:
            try:
                print(f"🔍 Probando broker {broker_ip} ({network_name})...")
                test_client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="uwb_test_connection")
                test_client.connect(broker_ip, self.mqtt_port, 5)  # 5 sec timeout
                test_client.loop_start()
                time.sleep(1)  # Breve pausa para verificar conexión
                test_client.disconnect()
                test_client.loop_stop()
                
                print(f"✅ Broker encontrado: {broker_ip} ({network_name})")
                return broker_ip
                
            except Exception as e:
                print(f"❌ {broker_ip} no disponible: {str(e)[:50]}")
                continue
        
        return None

    def run(self):
        """Ejecutar el recolector"""
        try:
            # Detectar broker MQTT disponible
            detected_broker = self.detect_mqtt_broker()
            if detected_broker:
                self.mqtt_server = detected_broker
                print(f"🎯 Usando broker MQTT: {self.mqtt_server}:{self.mqtt_port}")
            else:
                print("❌ No se encontró ningún broker MQTT disponible.")
                print("💡 Opciones para solucionar:")
                print("   1. Activar hotspot iPhone 'iPhone de Nicolas'")
                print("   2. Conectar a WiFi casa 'MOVISTAR_PLUS_40B0'")
                print("   3. Iniciar broker local: mosquitto -v -p 1883")
                return
            
            # Conectar al broker MQTT
            self.client.connect(self.mqtt_server, self.mqtt_port, 60)
            
            # Configurar handler para Ctrl+C
            def signal_handler(sig, frame):
                print(f"\n🛑 Deteniendo recolector...")
                self.print_statistics()
                self.client.disconnect()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            
            print("🚀 Recolector iniciado. Presiona Ctrl+C para detener.")
            print("📡 Esperando datos MQTT...")
            
            # Loop principal con estadísticas periódicas
            last_stats = time.time()
            self.client.loop_start()
            
            while True:
                time.sleep(1)
                
                # Mostrar estadísticas cada 30 segundos
                if time.time() - last_stats > 30:
                    self.print_statistics()
                    last_stats = time.time()
                    
        except Exception as e:
            print(f"❌ Error en el recolector: {e}")
        finally:
            self.client.loop_stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TFG UWB - Recolector MQTT a CSV")
    parser.add_argument("--mqtt-server", default="172.20.10.3", 
                        help="Dirección IP del broker MQTT")
    parser.add_argument("--mqtt-port", type=int, default=1883,
                        help="Puerto del broker MQTT")
    parser.add_argument("--output-dir", default="data",
                        help="Directorio de salida para archivos CSV")
    
    args = parser.parse_args()
    
    collector = MQTTToCSVCollector(
        mqtt_server=args.mqtt_server,
        mqtt_port=args.mqtt_port,
        output_dir=args.output_dir
    )
    
    collector.run() 