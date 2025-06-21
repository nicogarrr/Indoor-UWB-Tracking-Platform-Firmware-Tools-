#!/usr/bin/env python3
"""
Sistema de Procesamiento de Datos UWB para TFG Fútbol Sala
===========================================================

Procesador avanzado de datos CSV capturados desde el sistema UWB.
Incluye filtrado de outliers, suavizado, interpolación y visualización.

Características:
- Filtrado automático de outliers usando IQR
- Eliminación de distancias fuera de rango físico
- Filtrado de velocidades imposibles
- Interpolación a frecuencia constante (25 Hz)
- Suavizado con filtro Savitzky-Golay
- Visualizaciones automáticas de trayectoria y métricas
- Estadísticas resumidas por sesión

Autor: Sistema UWB TFG Fútbol Sala
Versión: 1.0
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import interpolate
from scipy.signal import savgol_filter
import os
import glob
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuración de visualización
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

class UWBDataProcessor:
    def __init__(self, data_dir="data"):
        """
        Inicializa el procesador de datos UWB
        
        Args:
            data_dir (str): Directorio donde se encuentran los archivos CSV
        """
        self.data_dir = data_dir
        self.field_bounds = {
            'x_min': -2, 'x_max': 42,
            'y_min': -2, 'y_max': 22
        }
        
        # Parámetros de filtrado
        self.max_distance = 60.0  # metros
        self.min_distance = 0.1   # metros
        self.max_velocity = 12.0  # m/s (velocidad máxima realista para fútbol sala)
        self.teleport_threshold = 15.0  # m/s (detección de saltos de teleportación)
        
        # Configuración de interpolación
        self.target_frequency = 25  # Hz
        
    def find_csv_files(self, pattern="uwb_data_*.csv"):
        """Encuentra archivos CSV con el patrón especificado"""
        if not os.path.exists(self.data_dir):
            print(f"⚠️  Directorio {self.data_dir} no encontrado")
            return []
        
        pattern_path = os.path.join(self.data_dir, pattern)
        files = glob.glob(pattern_path)
        
        if not files:
            print(f"⚠️  No se encontraron archivos con patrón {pattern}")
        else:
            print(f"📁 Encontrados {len(files)} archivos CSV:")
            for f in files:
                print(f"   - {os.path.basename(f)}")
        
        return files
    
    def load_csv_data(self, csv_file):
        """
        Carga datos desde archivo CSV con manejo robusto de errores
        
        Args:
            csv_file (str): Ruta al archivo CSV
            
        Returns:
            pd.DataFrame: Datos cargados y preprocesados
        """
        try:
            print(f"\n📊 Procesando: {os.path.basename(csv_file)}")
            
            # Cargar datos
            df = pd.read_csv(csv_file)
            print(f"   Datos cargados: {len(df)} registros")
            
            if df.empty:
                print("   ⚠️  Archivo vacío")
                return None
                
            # Verificar columnas requeridas
            required_cols = ['timestamp', 'tag_id', 'x', 'y']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"   ❌ Columnas faltantes: {missing_cols}")
                return None
            
            # Convertir timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Filtro básico de coordenadas
            initial_count = len(df)
            df = df.dropna(subset=['x', 'y'])
            df = df[(df['x'].between(-10, 50)) & (df['y'].between(-10, 30))]
            
            filtered_count = len(df)
            if initial_count > filtered_count:
                print(f"   🔧 Filtrado básico: {initial_count - filtered_count} registros eliminados")
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error cargando {csv_file}: {str(e)}")
            return None
    
    def calculate_distances_to_anchors(self, df):
        """Calcula distancias a todas las anclas UWB"""
        anchor_positions = {
            10: (-1, -1),   # Esquina Suroeste
            20: (-1, 21),   # Esquina Noroeste  
            30: (41, -1),   # Esquina Sureste
            40: (41, 21),   # Esquina Noreste
            50: (20, -1)    # Centro campo Sur
        }
        
        for anchor_id, (ax, ay) in anchor_positions.items():
            df[f'dist_anchor_{anchor_id}'] = np.sqrt(
                (df['x'] - ax)**2 + (df['y'] - ay)**2
            )
        
        return df
    
    def filter_outliers_by_anchor(self, df):
        """
        Filtrado de outliers usando IQR por cada ancla individualmente
        """
        print("   🔍 Aplicando filtrado de outliers por ancla...")
        
        anchor_cols = [col for col in df.columns if col.startswith('dist_anchor_')]
        original_len = len(df)
        
        for col in anchor_cols:
            if col in df.columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # También aplicar límites físicos
                lower_bound = max(lower_bound, self.min_distance)
                upper_bound = min(upper_bound, self.max_distance)
                
                df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
        
        filtered_len = len(df)
        print(f"      Outliers eliminados: {original_len - filtered_len} registros")
        
        return df
    
    def filter_impossible_velocities(self, df):
        """
        Filtra posiciones que implican velocidades imposibles
        """
        print("   🚀 Filtrado de velocidades imposibles...")
        
        if len(df) < 2:
            return df
        
        # Calcular desplazamientos y tiempos
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        
        # Calcular velocidades
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        
        # Filtrar velocidades imposibles
        original_len = len(df)
        valid_velocity = (df['velocity'] <= self.max_velocity) | df['velocity'].isna()
        valid_teleport = (df['velocity'] <= self.teleport_threshold) | df['velocity'].isna()
        
        df = df[valid_velocity & valid_teleport]
        
        # Limpiar columnas temporales
        df = df.drop(['dx', 'dy', 'dt', 'distance', 'velocity'], axis=1)
        
        filtered_len = len(df)
        print(f"      Velocidades imposibles eliminadas: {original_len - filtered_len} registros")
        
        return df
    
    def interpolate_to_constant_frequency(self, df):
        """
        Interpola los datos a una frecuencia constante
        """
        print(f"   📈 Interpolando a {self.target_frequency} Hz...")
        
        if len(df) < 2:
            return df
        
        # Crear timeline a frecuencia constante
        start_time = df['timestamp'].min()
        end_time = df['timestamp'].max()
        duration = (end_time - start_time).total_seconds()
        
        if duration <= 0:
            return df
        
        # Generar timestamps uniformes
        num_points = int(duration * self.target_frequency) + 1
        uniform_times = pd.date_range(start=start_time, end=end_time, periods=num_points)
        
        # Convertir a segundos para interpolación
        df['seconds'] = (df['timestamp'] - start_time).dt.total_seconds()
        uniform_seconds = (uniform_times - start_time).total_seconds()
        
        # Interpolar posiciones
        try:
            f_x = interpolate.interp1d(df['seconds'], df['x'], kind='linear', 
                                     bounds_error=False, fill_value='extrapolate')
            f_y = interpolate.interp1d(df['seconds'], df['y'], kind='linear',
                                     bounds_error=False, fill_value='extrapolate')
            
            # Crear DataFrame interpolado
            interpolated_df = pd.DataFrame({
                'timestamp': uniform_times,
                'tag_id': df['tag_id'].iloc[0],
                'x': f_x(uniform_seconds),
                'y': f_y(uniform_seconds)
            })
            
            print(f"      Interpolación: {len(df)} → {len(interpolated_df)} puntos")
            return interpolated_df
            
        except Exception as e:
            print(f"      ⚠️  Error en interpolación: {e}")
            return df
    
    def apply_smoothing(self, df, window_length=5):
        """
        Aplica suavizado Savitzky-Golay a las coordenadas
        """
        print("   🎯 Aplicando suavizado Savitzky-Golay...")
        
        if len(df) < window_length:
            print(f"      ⚠️  Datos insuficientes para suavizado (mín. {window_length})")
            return df
        
        try:
            df['x_smooth'] = savgol_filter(df['x'], window_length, 3)
            df['y_smooth'] = savgol_filter(df['y'], window_length, 3)
            
            # Reemplazar coordenadas originales con suavizadas
            df['x'] = df['x_smooth']
            df['y'] = df['y_smooth']
            df = df.drop(['x_smooth', 'y_smooth'], axis=1)
            
            print("      ✅ Suavizado aplicado correctamente")
            
        except Exception as e:
            print(f"      ⚠️  Error en suavizado: {e}")
        
        return df
    
    def calculate_movement_metrics(self, df):
        """
        Calcula métricas de movimiento avanzadas
        """
        if len(df) < 2:
            return df
        
        # Calcular velocidades y aceleraciones
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        df['acceleration'] = df['velocity'].diff() / df['dt']
        
        # Dirección del movimiento
        df['direction'] = np.arctan2(df['dy'], df['dx']) * 180 / np.pi
        
        return df

    def process_single_file(self, csv_file, output_dir="processed_data"):
        """
        Procesa un archivo CSV individual con pipeline completo
        
        Args:
            csv_file (str): Ruta al archivo CSV
            output_dir (str): Directorio de salida para datos procesados
            
        Returns:
            pd.DataFrame: Datos procesados
        """
        # Cargar datos
        df = self.load_csv_data(csv_file)
        if df is None or df.empty:
            return None
        
        # Pipeline de procesamiento
        df = self.calculate_distances_to_anchors(df)
        df = self.filter_outliers_by_anchor(df)
        df = self.filter_impossible_velocities(df)
        df = self.interpolate_to_constant_frequency(df)
        df = self.apply_smoothing(df)
        df = self.calculate_movement_metrics(df)
        
        # Guardar datos procesados
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_processed.csv")
        df.to_csv(output_file, index=False)
        print(f"   💾 Datos procesados guardados: {os.path.basename(output_file)}")
        
        return df


def main():
    """Función principal para ejecutar el procesador"""
    print("🚀 Sistema de Procesamiento de Datos UWB - TFG Fútbol Sala")
    print("=" * 65)
    
    # Crear procesador
    processor = UWBDataProcessor(data_dir="data")
    
    # Buscar archivos CSV
    csv_files = processor.find_csv_files()
    
    if not csv_files:
        print(f"\n⚠️  No se encontraron archivos para procesar")
        print("   Verifica que exista el directorio 'data/' con archivos 'uwb_data_*.csv'")
        return
    
    # Procesar archivo más reciente como ejemplo
    latest_file = max(csv_files, key=os.path.getmtime)
    print(f"\n🔄 Procesando archivo más reciente: {os.path.basename(latest_file)}")
    
    # Procesar datos
    df = processor.load_csv_data(latest_file)
    if df is not None:
        df = processor.calculate_distances_to_anchors(df)
        df = processor.filter_outliers_by_anchor(df)
        df = processor.filter_impossible_velocities(df)
        df = processor.interpolate_to_constant_frequency(df)
        df = processor.apply_smoothing(df)
        df = processor.calculate_movement_metrics(df)
        
        print(f"\n✅ Procesamiento completado: {len(df)} puntos finales")
        
        # Guardar resultados
        os.makedirs("processed_data", exist_ok=True)
        output_file = "processed_data/latest_processed.csv"
        df.to_csv(output_file, index=False)
        print(f"💾 Datos guardados en: {output_file}")


if __name__ == "__main__":
    main() 