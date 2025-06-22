#!/usr/bin/env python3
"""
Script de Integración Automática TFG - WordPress
==============================================

Automatiza la subida de datos UWB desde el TFG al sitio WordPress del equipo.
Monitoriza la carpeta de datos procesados y los sube automáticamente.

Características:
- Monitoreo de archivos en tiempo real
- Subida automática a WordPress via API REST
- Procesamiento de datos con análisis previo
- Notificaciones de estado
- Logs detallados

Autor: TFG Sistema UWB
"""

import os
import json
import time
import requests
import pandas as pd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import base64
import hashlib
import argparse
from pathlib import Path
import logging

class WordPressUploaderTFG:
    """Subidor automático de datos UWB a WordPress"""
    
    def __init__(self, config_file="wordpress_config.json"):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.session = requests.Session()
        
        # Configurar autenticación
        self.setup_auth()
        
    def load_config(self, config_file):
        """Cargar configuración desde archivo JSON"""
        default_config = {
            "wordpress": {
                "url": "https://tu-equipo-futsal.com",
                "username": "admin_tfg",
                "password": "tu_password_seguro",
                "api_endpoint": "/wp-json/wp/v2"
            },
            "monitoring": {
                "watch_directory": "./processed_data",
                "file_extensions": [".csv"],
                "upload_delay": 30
            },
            "processing": {
                "min_file_size": 1024,
                "max_file_size": 10485760,
                "required_columns": ["timestamp", "x", "y", "tag_id"]
            },
            "team": {
                "team_name": "Equipo TFG Fútbol Sala UWB",
                "default_player_id": "jugador_tfg",
                "season": "2025",
                "project_name": "Sistema UWB para Análisis Deportivo"
            }
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        else:
            # Crear archivo de configuración por defecto
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"📝 Archivo de configuración creado: {config_file}")
            print("⚠️  Por favor, edita el archivo con tu configuración de WordPress")
        
        return default_config
    
    def setup_logging(self):
        """Configurar sistema de logs"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('wordpress_uploader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_auth(self):
        """Configurar autenticación con WordPress"""
        wp_config = self.config['wordpress']
        
        # Crear token de autenticación básica
        credentials = f"{wp_config['username']}:{wp_config['password']}"
        token = base64.b64encode(credentials.encode()).decode()
        
        self.session.headers.update({
            'Authorization': f'Basic {token}',
            'Content-Type': 'application/json'
        })
        
        self.logger.info(f"🔐 Configurada autenticación para {wp_config['url']}")
    
    def test_wordpress_connection(self):
        """Probar conexión con WordPress"""
        try:
            wp_config = self.config['wordpress']
            url = f"{wp_config['url']}{wp_config['api_endpoint']}/users/me"
            
            response = self.session.get(url)
            
            if response.status_code == 200:
                user_data = response.json()
                self.logger.info(f"✅ Conectado a WordPress como: {user_data.get('name', 'Usuario')}")
                return True
            else:
                self.logger.error(f"❌ Error de autenticación: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error conectando a WordPress: {e}")
            return False
    
    def process_uwb_file(self, file_path):
        """Procesar archivo UWB y extraer métricas"""
        try:
            df = pd.read_csv(file_path)
            
            # Validar columnas requeridas
            required_cols = self.config['processing']['required_columns']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️  Faltan columnas: {missing_cols}")
                return None
            
            # Calcular métricas básicas
            total_time = (pd.to_datetime(df['timestamp']).iloc[-1] - 
                         pd.to_datetime(df['timestamp']).iloc[0]).total_seconds()
            
            # Calcular distancia total
            df['distance'] = ((df['x'].diff()**2 + df['y'].diff()**2)**0.5).fillna(0)
            total_distance = df['distance'].sum()
            
            # Calcular velocidades
            df['dt'] = pd.to_datetime(df['timestamp']).diff().dt.total_seconds()
            df['velocity'] = df['distance'] / df['dt']
            avg_speed = df['velocity'].mean()
            max_speed = df['velocity'].max()
            
            # Detectar sprints (velocidad > 4 m/s)
            sprints = len(df[df['velocity'] > 4.0])
            
            # Análisis de zonas
            df['zone'] = df.apply(self.get_tactical_zone, axis=1)
            zone_stats = df['zone'].value_counts().to_dict()
            
            metrics = {
                'file_info': {
                    'filename': os.path.basename(file_path),
                    'file_size': os.path.getsize(file_path),
                    'records': len(df),
                    'duration': total_time
                },
                'performance': {
                    'total_distance': round(total_distance, 2),
                    'avg_speed': round(avg_speed, 2),
                    'max_speed': round(max_speed, 2),
                    'sprints_detected': sprints,
                    'intensity_avg': round((avg_speed / max_speed * 100) if max_speed > 0 else 0, 1)
                },
                'tactical': {
                    'zones_visited': len(zone_stats),
                    'zone_distribution': zone_stats,
                    'x_range': [float(df['x'].min()), float(df['x'].max())],
                    'y_range': [float(df['y'].min()), float(df['y'].max())]
                },
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"📊 Métricas calculadas para {os.path.basename(file_path)}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando archivo {file_path}: {e}")
            return None
    
    def get_tactical_zone(self, row):
        """Determinar zona táctica de una posición"""
        x, y = row['x'], row['y']
        
        if x <= 13.33:
            return 'zona_defensiva'
        elif x >= 26.67:
            return 'zona_ofensiva'
        elif 17 <= x <= 23 and 7 <= y <= 13:
            return 'circulo_central'
        else:
            return 'zona_media'
    
    def upload_to_wordpress(self, file_path, metrics):
        """Subir datos y métricas a WordPress"""
        try:
            wp_config = self.config['wordpress']
            team_config = self.config['team']
            
            # Crear entrada de blog automática
            post_data = {
                'title': f"📊 Análisis UWB - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                'content': self.generate_post_content(metrics),
                'status': 'publish',
                'categories': [1],  # Categoria por defecto
                'meta': {
                    'tfg_uwb_data': json.dumps(metrics),
                    'tfg_session_id': f"session_{int(time.time())}",
                    'tfg_player_id': team_config['default_player_id']
                }
            }
            
            # Enviar a WordPress
            url = f"{wp_config['url']}{wp_config['api_endpoint']}/posts"
            response = self.session.post(url, json=post_data)
            
            if response.status_code == 201:
                post_id = response.json()['id']
                self.logger.info(f"✅ Datos subidos a WordPress. Post ID: {post_id}")
                
                # Subir también el archivo CSV
                self.upload_csv_file(file_path, post_id)
                return True
            else:
                self.logger.error(f"❌ Error subiendo a WordPress: {response.status_code}")
                self.logger.error(response.text)
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error en upload_to_wordpress: {e}")
            return False
    
    def generate_post_content(self, metrics):
        """Generar contenido HTML para el post"""
        file_info = metrics['file_info']
        performance = metrics['performance']
        tactical = metrics['tactical']
        
        content = f"""
        <h2>🏟️ Análisis de Rendimiento - Sistema UWB</h2>
        
        <div class="uwb-analysis-summary">
            <h3>📈 Resumen de la Sesión</h3>
            <ul>
                <li><strong>Duración:</strong> {file_info['duration']:.1f} segundos</li>
                <li><strong>Registros:</strong> {file_info['records']:,} puntos de datos</li>
                <li><strong>Distancia total:</strong> {performance['total_distance']} metros</li>
                <li><strong>Velocidad promedio:</strong> {performance['avg_speed']} m/s</li>
                <li><strong>Velocidad máxima:</strong> {performance['max_speed']} m/s</li>
                <li><strong>Sprints detectados:</strong> {performance['sprints_detected']}</li>
            </ul>
        </div>
        
        <div class="uwb-tactical-analysis">
            <h3>⚔️ Análisis Táctico</h3>
            <p><strong>Zonas visitadas:</strong> {tactical['zones_visited']}</p>
            <p><strong>Distribución por zonas:</strong></p>
            <ul>
        """
        
        for zone, count in tactical['zone_distribution'].items():
            percentage = (count / file_info['records'] * 100)
            content += f"<li>{zone.replace('_', ' ').title()}: {percentage:.1f}% ({count} registros)</li>"
        
        content += f"""
            </ul>
        </div>
        
        <!-- Widget UWB embebido -->
        [uwb_analytics player_id="{self.config['team']['default_player_id']}" type="dashboard"]
        
        <div class="uwb-technical-details">
            <h4>🔧 Detalles Técnicos</h4>
            <p><small>
                Archivo: {file_info['filename']} | 
                Tamaño: {file_info['file_size']:,} bytes | 
                Procesado: {metrics['timestamp']}
            </small></p>
        </div>
        
        <style>
        .uwb-analysis-summary, .uwb-tactical-analysis {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #007cba;
        }}
        .uwb-technical-details {{
            background: #e9ecef;
            padding: 10px;
            border-radius: 4px;
            margin-top: 20px;
        }}
        </style>
        """
        
        return content
    
    def upload_csv_file(self, file_path, post_id):
        """Subir archivo CSV como adjunto"""
        try:
            wp_config = self.config['wordpress']
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, 'text/csv')
                }
                
                url = f"{wp_config['url']}{wp_config['api_endpoint']}/media"
                
                # Temporal: remover Content-Type para upload de archivos
                headers = dict(self.session.headers)
                if 'Content-Type' in headers:
                    del headers['Content-Type']
                
                response = requests.post(
                    url,
                    files=files,
                    headers=headers,
                    data={'post': post_id}
                )
                
                if response.status_code == 201:
                    media_data = response.json()
                    self.logger.info(f"📎 Archivo CSV subido: {media_data['source_url']}")
                else:
                    self.logger.warning(f"⚠️  Error subiendo CSV: {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error subiendo archivo CSV: {e}")

class UWBFileHandler(FileSystemEventHandler):
    """Handler para monitorizar archivos UWB"""
    
    def __init__(self, uploader):
        self.uploader = uploader
        self.processed_files = set()
        
    def on_created(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)
    
    def process_file(self, file_path):
        """Procesar archivo detectado"""
        # Verificar extensión
        if not any(file_path.endswith(ext) for ext in self.uploader.config['monitoring']['file_extensions']):
            return
        
        # Evitar procesar el mismo archivo múltiples veces
        file_hash = self.get_file_hash(file_path)
        if file_hash in self.processed_files:
            return
        
        # Esperar un poco para asegurar que el archivo se ha escrito completamente
        delay = self.uploader.config['monitoring']['upload_delay']
        self.uploader.logger.info(f"⏳ Archivo detectado: {file_path}. Esperando {delay}s...")
        time.sleep(delay)
        
        # Verificar tamaño de archivo
        file_size = os.path.getsize(file_path)
        min_size = self.uploader.config['processing']['min_file_size']
        max_size = self.uploader.config['processing']['max_file_size']
        
        if file_size < min_size:
            self.uploader.logger.warning(f"⚠️  Archivo muy pequeño: {file_size} bytes")
            return
        
        if file_size > max_size:
            self.uploader.logger.warning(f"⚠️  Archivo muy grande: {file_size} bytes")
            return
        
        # Procesar y subir
        self.uploader.logger.info(f"🔄 Procesando: {os.path.basename(file_path)}")
        
        metrics = self.uploader.process_uwb_file(file_path)
        if metrics:
            success = self.uploader.upload_to_wordpress(file_path, metrics)
            if success:
                self.processed_files.add(file_hash)
                self.uploader.logger.info(f"✅ Completado: {os.path.basename(file_path)}")
            else:
                self.uploader.logger.error(f"❌ Falló: {os.path.basename(file_path)}")
        else:
            self.uploader.logger.error(f"❌ Error procesando: {os.path.basename(file_path)}")
    
    def get_file_hash(self, file_path):
        """Calcular hash del archivo para evitar duplicados"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Integración automática TFG-WordPress')
    parser.add_argument('--config', default='wordpress_config.json',
                       help='Archivo de configuración')
    parser.add_argument('--test-connection', action='store_true',
                       help='Solo probar conexión con WordPress')
    parser.add_argument('--upload-file', type=str,
                       help='Subir un archivo específico')
    parser.add_argument('--watch', action='store_true',
                       help='Monitorizar directorio continuamente')
    
    args = parser.parse_args()
    
    print("🚀 TFG UWB → WordPress Integration")
    print("=" * 50)
    
    # Crear uploader
    uploader = WordPressUploaderTFG(args.config)
    
    # Probar conexión
    if args.test_connection:
        uploader.test_wordpress_connection()
        return
    
    # Subir archivo específico
    if args.upload_file:
        if os.path.exists(args.upload_file):
            metrics = uploader.process_uwb_file(args.upload_file)
            if metrics:
                uploader.upload_to_wordpress(args.upload_file, metrics)
            else:
                print("❌ Error procesando archivo")
        else:
            print(f"❌ Archivo no encontrado: {args.upload_file}")
        return
    
    # Monitorización continua
    if args.watch:
        if not uploader.test_wordpress_connection():
            print("❌ No se puede conectar a WordPress. Verifica la configuración.")
            return
        
        watch_dir = uploader.config['monitoring']['watch_directory']
        
        if not os.path.exists(watch_dir):
            print(f"❌ Directorio no existe: {watch_dir}")
            return
        
        print(f"👁️  Monitorizando: {watch_dir}")
        print("📡 Presiona Ctrl+C para detener")
        
        event_handler = UWBFileHandler(uploader)
        observer = Observer()
        observer.schedule(event_handler, watch_dir, recursive=False)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n👋 Monitorización detenida")
        
        observer.join()
    else:
        # Mostrar ayuda si no se especifica acción
        parser.print_help()

if __name__ == "__main__":
    main() 