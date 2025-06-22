#!/usr/bin/env python3
"""
Sistema Integrado de Comparación de Sesiones UWB - TFG Fútbol Sala
==================================================================

Herramienta consolidada que combina:
- Comparación de múltiples sesiones (ex session_comparator.py)
- Generación de datos de prueba (ex futsal_movement_generator.py)

Autor: TFG Sistema UWB Fútbol Sala
Versión: 2.0 - Consolidada
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
import math
import random
from datetime import datetime, timedelta
import argparse

class UWBComparator:
    def __init__(self, output_dir="outputs/comparisons"):
        self.sessions = {}
        self.metrics = {}
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def load_session(self, csv_file, session_name=None):
        """Cargar una sesión de entrenamiento"""
        if session_name is None:
            session_name = os.path.basename(csv_file).replace('.csv', '')
        
        try:
            # Mostrar información de procesamiento
            folder_name = os.path.dirname(csv_file)
            file_name = os.path.basename(csv_file)
            print(f"     📁 {folder_name}/{file_name}")
            
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            print(f"     📊 {len(df)} registros cargados")
            
            # Calcular métricas básicas
            metrics = self._calculate_metrics(df)
            
            self.sessions[session_name] = {
                'data': df,
                'metrics': metrics,
                'file': csv_file,
                'folder': folder_name
            }
            
            duration = metrics['total_time']
            distance = metrics['total_distance']
            print(f"     ✅ Duración: {duration:.1f}s, Distancia: {distance:.1f}m")
            
        except Exception as e:
            print(f"     ❌ Error: {e}")
    
    def _calculate_metrics(self, df):
        """Calcular métricas de sesión"""
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        
        total_time = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds()
        total_distance = df['distance'].sum()
        avg_speed = df['velocity'].mean()
        max_speed = df['velocity'].max()
        
        return {
            'total_time': total_time,
            'total_distance': total_distance,
            'avg_speed': avg_speed,
            'max_speed': max_speed
        }
    
    def compare_sessions(self):
        """Comparar todas las sesiones cargadas"""
        if len(self.sessions) < 2:
            print("❌ Se necesitan al menos 2 sesiones")
            return None
        
        print("\n🔍 COMPARACIÓN DE SESIONES")
        print("=" * 50)
        
        metrics_df = pd.DataFrame()
        for session_name, session_data in self.sessions.items():
            metrics_series = pd.Series(session_data['metrics'])
            metrics_df[session_name] = metrics_series
        
        print("\n📊 TABLA COMPARATIVA:")
        
        # Configurar pandas para mostrar todas las columnas
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
        
        print(metrics_df.round(2).to_string())
        
        # Restaurar configuración por defecto
        pd.reset_option('display.max_columns')
        pd.reset_option('display.width') 
        pd.reset_option('display.max_colwidth')
        
        # Mostrar resumen de métricas
        print(f"\n📈 RESUMEN:")
        print(f"   📏 Distancia promedio: {metrics_df.loc['total_distance'].mean():.1f}m")
        print(f"   🏃 Velocidad promedio: {metrics_df.loc['avg_speed'].mean():.2f} m/s")
        print(f"   ⚡ Velocidad máxima: {metrics_df.loc['max_speed'].max():.2f} m/s")
        
        return metrics_df
    
    def generate_test_session(self, scenario="professional", duration=120):
        """Generar sesión de prueba"""
        print(f"🔧 Generando sesión: {scenario}")
        
        total_frames = duration * 25  # 25 FPS
        movements = []
        timestamps = []
        start_time = datetime.now()
        
        x, y = 20, 10  # Centro cancha
        
        for frame in range(total_frames):
            t = frame / 25
            
            if scenario == "professional":
                target_x = 20 + 15 * math.sin(t * 0.2)
                target_y = 10 + 6 * math.cos(t * 0.3)
                speed = 0.2
            else:  # amateur
                target_x = 20 + 10 * math.sin(t * 0.1)
                target_y = 10 + 4 * math.cos(t * 0.15)
                speed = 0.1
            
            dx = (target_x - x) * speed
            dy = (target_y - y) * speed
            
            x += dx + random.uniform(-0.3, 0.3)
            y += dy + random.uniform(-0.2, 0.2)
            
            x = max(2, min(38, x))
            y = max(2, min(18, y))
            
            timestamp = start_time + timedelta(seconds=frame / 25)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        # Crear DataFrame con ruido
        df = pd.DataFrame({
            'timestamp': timestamps,
            'tag_id': ['J07'] * len(timestamps),
            'x': [pos[0] + np.random.normal(0, 0.15) for pos in movements],
            'y': [pos[1] + np.random.normal(0, 0.15) for pos in movements]
        })
        
        # Guardar
        output_file = f"test_{scenario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = os.path.join("data", output_file)
        os.makedirs("data", exist_ok=True)
        
        df.to_csv(output_path, index=False)
        print(f"💾 Guardado: {output_path}")
        
        return output_path

def select_comparison_files():
    """Selección interactiva de archivos para comparación"""
    print("🏟️ COMPARADOR UWB PARA FÚTBOL SALA")
    print("=" * 60)
    
    print("\n📁 SELECCIONAR DIRECTORIO PARA COMPARACIÓN:")
    print("=" * 50)
    print("1. 📊 processed_data/ - Datos ya procesados")
    print("2. 📥 data/ - Datos originales")
    print("3. 🔍 Buscar en ambos directorios")
    print("4. 🎯 Selección manual archivo por archivo")
    print("0. ❌ Cancelar")
    
    while True:
        try:
            dir_choice = input("\n👆 Selecciona opción (0-4): ").strip()
            
            if dir_choice == '0':
                print("❌ Operación cancelada")
                return None
            elif dir_choice == '1':
                csv_files = glob.glob("processed_data/*.csv")
                search_path = "📊 processed_data/"
                break
            elif dir_choice == '2':
                csv_files = glob.glob("data/*.csv")
                search_path = "📥 data/"
                break
            elif dir_choice == '3':
                csv_files = glob.glob("processed_data/*.csv") + glob.glob("data/*.csv")
                search_path = "🔍 ambos directorios"
                break
            elif dir_choice == '4':
                return select_manual_files()
            else:
                print("❌ Opción inválida. Selecciona 0, 1, 2, 3 o 4")
                continue
        except KeyboardInterrupt:
            print("\n❌ Operación cancelada")
            return None
    
    if len(csv_files) < 2:
        print(f"⚠️  Solo se encontraron {len(csv_files)} archivos en {search_path}")
        print("🔧 Se necesitan al menos 2 archivos para comparar")
        return None
    
    print(f"\n📁 ARCHIVOS ENCONTRADOS EN {search_path.upper()}:")
    print("=" * 70)
    
    files_to_load = csv_files[:5]  # Máximo 5 archivos
    for i, csv_file in enumerate(files_to_load, 1):
        file_name = os.path.basename(csv_file)
        file_size = os.path.getsize(csv_file) / 1024
        folder_icon = "📊" if csv_file.startswith("processed_data") else "📥"
        folder_name = "processed_data" if csv_file.startswith("processed_data") else "data"
        print(f"   {i}. {folder_icon} {folder_name}/{file_name} ({file_size:.1f} KB)")
    
    return files_to_load

def select_manual_files():
    """Selección manual de archivos específicos"""
    all_files = glob.glob("processed_data/*.csv") + glob.glob("data/*.csv")
    
    if not all_files:
        print("❌ No se encontraron archivos CSV")
        return None
    
    print(f"\n📁 TODOS LOS ARCHIVOS DISPONIBLES:")
    print("=" * 70)
    
    for i, file_path in enumerate(all_files, 1):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024
        folder_icon = "📊" if file_path.startswith("processed_data") else "📥"
        folder_name = "processed_data" if file_path.startswith("processed_data") else "data"
        print(f"{i:2d}. {folder_icon} {folder_name}/{file_name} ({file_size:.1f} KB)")
    
    selected_files = []
    print(f"\n👆 Selecciona archivos para comparar (mínimo 2):")
    print("   Ingresa los números separados por comas (ej: 1,3,5) o 0 para cancelar:")
    
    while True:
        try:
            choice = input("Opción: ").strip()
            
            if choice == '0':
                print("❌ Operación cancelada")
                return None
            
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            
            if all(0 <= idx < len(all_files) for idx in indices) and len(indices) >= 2:
                selected_files = [all_files[idx] for idx in indices]
                break
            else:
                print("❌ Selección inválida. Necesitas al menos 2 archivos válidos")
                
        except (ValueError, IndexError):
            print("❌ Formato inválido. Usa números separados por comas (ej: 1,3,5)")
        except KeyboardInterrupt:
            print("\n❌ Operación cancelada")
            return None
    
    print(f"\n✅ Archivos seleccionados para comparación:")
    for file_path in selected_files:
        folder_name = "processed_data" if file_path.startswith("processed_data") else "data"
        print(f"   📄 {folder_name}/{os.path.basename(file_path)}")
    
    return selected_files

def main():
    # Seleccionar archivos
    selected_files = select_comparison_files()
    
    if selected_files is None:
        return
    
    print(f"\n📍 DIRECTORIO DE TRABAJO: {os.getcwd()}")
    
    comparator = UWBComparator()
    
    # Cargar sesiones seleccionadas
    print(f"\n📋 CARGANDO {len(selected_files)} SESIONES:")
    for csv_file in selected_files:
        print(f"   🔄 Procesando: {os.path.basename(csv_file)}")
        comparator.load_session(csv_file)
    
    if len(comparator.sessions) >= 2:
        comparator.compare_sessions()
        print(f"\n✅ COMPARACIÓN COMPLETADA")
        print(f"📁 Resultados disponibles para {len(comparator.sessions)} sesiones")
    else:
        print("❌ No se pudieron cargar suficientes sesiones para comparar")

if __name__ == "__main__":
    main()