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
    def __init__(self, mqtt_server="172.20.10.3", mqtt_port=1883, output_dir="./data"):
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.output_dir = output_dir
        
        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Archivos CSV
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ranging_file = os.path.join(output_dir, f"ranging_data_{timestamp}.csv")
        self.position_file = os.path.join(output_dir, f"position_data_{timestamp}.csv")
        self.zones_file = os.path.join(output_dir, f"zones_data_{timestamp}.csv")
        self.metrics_file = os.path.join(output_dir, f"metrics_data_{timestamp}.csv")
        
        # Contadores y estadísticas
        self.ranging_count = 0
        self.position_count = 0
        self.zones_count = 0
        self.metrics_count = 0
        self.start_time = time.time()
        
        # Lock para escritura thread-safe
        self.file_lock = Lock()
        
        # Cliente MQTT
        self.client = mqtt.Client(client_id="uwb_data_collector")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Inicializar archivos CSV con headers
        self.init_csv_files()
        
        print(f"🎯 TFG UWB Data Collector iniciado")
        print(f"📂 Directorio de salida: {output_dir}")
        print(f"🔗 MQTT Broker: {mqtt_server}:{mqtt_port}")
        print(f"📁 Archivos:")
        print(f"   • Ranging: {self.ranging_file}")
        print(f"   • Posición: {self.position_file}")
        print(f"   • Zonas: {self.zones_file}")
        print(f"   • Métricas: {self.metrics_file}")
        print("=" * 60)
    
    def init_csv_files(self):
        """Inicializar archivos CSV con headers apropiados"""
        
        # Archivo de ranging (datos brutos UWB)
        with open(self.ranging_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_system', 'timestamp_device', 'tag_id', 'anchor_id',
                'distance_raw_cm', 'distance_filtered_cm', 'rssi_dbm', 
                'anchor_responded', 'session_id'
            ])
        
        # Archivo de posición (trilateración y filtros Kalman)
        with open(self.position_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_system', 'timestamp_device', 'tag_id', 
                'position_x_m', 'position_y_m', 'velocity_x_ms', 'velocity_y_ms',
                'speed_ms', 'prediction_x_m', 'prediction_y_m',
                'responding_anchors', 'update_rate_hz', 'session_id'
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
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback de conexión MQTT"""
        if rc == 0:
            print(f"✅ Conectado al broker MQTT (rc={rc})")
            
            # Suscribirse a todos los topics relevantes
            topics = [
                "uwb/tag/logs",           # Datos de ranging brutos
                "uwb/tag/+/status",       # Estado de tags
                "uwb/futsal/zones",       # Eventos de zonas
                "uwb/futsal/performance", # Eventos de rendimiento
                "uwb/futsal/metrics",     # Métricas del sistema
                "uwb/anchor/+/metrics",   # Métricas de anclas
            ]
            
            for topic in topics:
                client.subscribe(topic)
                print(f"📡 Suscrito a: {topic}")
                
        else:
            print(f"❌ Error de conexión MQTT (rc={rc})")
    
    def on_disconnect(self, client, userdata, rc):
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
            if topic == "uwb/tag/logs":
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
                
                with self.file_lock:
                    with open(self.position_file, 'a', newline='') as f:
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
                self.position_count += 1
                
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
        print(f"   📏 Datos ranging: {self.ranging_count}")
        print(f"   📍 Datos posición: {self.position_count}")
        print(f"   🏟️  Eventos zonas: {self.zones_count}")
        print(f"   📈 Métricas: {self.metrics_count}")
        if uptime > 0:
            print(f"   📊 Tasa ranging: {self.ranging_count/uptime:.1f} msgs/s")
    
    def run(self):
        """Ejecutar el recolector"""
        try:
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
    parser.add_argument("--output-dir", default="./data",
                        help="Directorio de salida para archivos CSV")
    
    args = parser.parse_args()
    
    collector = MQTTToCSVCollector(
        mqtt_server=args.mqtt_server,
        mqtt_port=args.mqtt_port,
        output_dir=args.output_dir
    )
    
    collector.run() 