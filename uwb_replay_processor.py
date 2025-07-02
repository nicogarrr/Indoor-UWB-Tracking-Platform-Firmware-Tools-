#!/usr/bin/env python3
"""
🔧 UWB Replay Processor
-----------------------
Limpia y normaliza ficheros CSV producidos por `mqtt_to_csv_collector.py` / `log_receiver_opt.py`.

Funcionalidades principales
1. Elimina duplicados exactos (timestamp + resto de columnas).
2. Filtra filas con distancias nulas o menores que un umbral (default 50 cm).
3. Opcionalmente remuestrea a intervalos fijos (default 500 ms) interpolando posiciones.
4. Guarda un CSV limpio en `processed_data/` (o la ruta indicada).

Uso rápido
----------
Procesar un único archivo:
    python uwb_replay_processor.py --input uwb_replay_csv/uwb_replay_20250627_131955.csv

Procesar todos los CSV de una carpeta:
    python uwb_replay_processor.py --input uwb_replay_csv --resample --freq 400ms
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
from datetime import datetime, timedelta

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def discover_csvs(path: Path) -> List[Path]:
    """Devuelve lista de ficheros CSV dentro de un path (archivo o carpeta)."""
    if path.is_file() and path.suffix.lower() == ".csv":
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.csv"))
    raise FileNotFoundError(f"Ruta no válida: {path}")


def clean_dataframe(df: pd.DataFrame, dist_threshold: float = 50.0) -> pd.DataFrame:
    """Limpia duplicados y distancias inválidas."""
    initial_rows = len(df)
    # 1. Eliminar duplicados exactos
    df = df.drop_duplicates()

    # 2. Filtrar distancias <= threshold
    dist_cols = [c for c in df.columns if c.endswith("_dist")]
    mask_valid = df[dist_cols].gt(dist_threshold).all(axis=1)
    df = df[mask_valid]

    removed = initial_rows - len(df)
    return df, removed


def resample_dataframe(df: pd.DataFrame, freq: str = "500ms") -> pd.DataFrame:
    """Ajusta el DataFrame a una frecuencia fija usando primer valor + interpolación lineal."""
    df = df.copy()
    df.index = pd.to_datetime(df["timestamp"])
    df = df.sort_index()

    # Re-muestreo, manteniendo la primera observación del intervalo y
    # luego interpolando valores numéricos faltantes.
    df_res = df.resample(freq).first()
    df_res[df_res.select_dtypes(float).columns] = df_res.select_dtypes(float).interpolate()
    df_res["tag_id"] = df_res["tag_id"].ffill()

    # Restaurar índice numérico
    df_res = df_res.reset_index()
    return df_res


# --------------------------------------------------
# CLI
# --------------------------------------------------

class UWBReplayProcessor:
    def __init__(self, target_frequency=15.0):
        self.target_frequency = target_frequency
        self.anchor_positions = {
            1: (-6.0, 0.0),
            2: (-1.6, 10.36), 
            3: (2.1, 10.36),
            4: (6.35, 0.0),
            5: (0.0, -1.8)
        }
        
    def load_and_clean_positions(self, positions_file):
        """Cargar y limpiar datos de posiciones"""
        print(f"📂 Cargando: {positions_file}")
        
        df = pd.read_csv(positions_file)
        original_count = len(df)
        print(f"✅ {original_count} posiciones originales cargadas")
        
        # 1. Limpiar timestamps duplicados
        if 'timestamp' in df.columns:
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                # Eliminar duplicados manteniendo el primero
                df = df.drop_duplicates(subset=['timestamp'], keep='first')
                removed_dups = original_count - len(df)
                if removed_dups > 0:
                    print(f"🔧 Eliminados {removed_dups} timestamps duplicados")
            except:
                print("⚠️  Creando timestamps sintéticos")
                df['timestamp'] = pd.date_range(start='2025-01-01 12:00:00', 
                                              periods=len(df), freq='700ms')
        
        # 2. Limpiar coordenadas inválidas
        before_clean = len(df)
        df = df.dropna(subset=['x', 'y'])
        df = df[(df['x'].abs() < 100) & (df['y'].abs() < 100)]  # Remover outliers extremos
        after_clean = len(df)
        
        if before_clean != after_clean:
            print(f"🔧 Eliminadas {before_clean - after_clean} coordenadas inválidas")
        
        # 3. Ordenar por timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"✅ {len(df)} posiciones válidas tras limpieza")
        
        return df
    
    def interpolate_missing_distances(self, df):
        """Interpolar distancias a anclas faltantes"""
        print("🔧 Interpolando distancias a anclas faltantes...")
        
        anchor_cols = ['anchor_1_dist', 'anchor_2_dist', 'anchor_3_dist', 
                      'anchor_4_dist', 'anchor_5_dist']
        
        interpolated_count = 0
        
        for col in anchor_cols:
            if col in df.columns:
                # Identificar valores faltantes (0 o NaN)
                missing_mask = (df[col] == 0) | df[col].isna()
                valid_mask = ~missing_mask
                
                if valid_mask.sum() > 2:  # Necesitamos al menos 2 puntos para interpolar
                    # Usar índices como x para interpolación
                    valid_indices = df.index[valid_mask]
                    valid_values = df.loc[valid_mask, col]
                    
                    # Crear función de interpolación
                    if len(valid_values) > 1:
                        interp_func = interp1d(valid_indices, valid_values, 
                                             kind='linear', fill_value='extrapolate',
                                             bounds_error=False)
                        
                        # Interpolar valores faltantes
                        missing_indices = df.index[missing_mask]
                        df.loc[missing_mask, col] = interp_func(missing_indices)
                        interpolated_count += missing_mask.sum()
        
        if interpolated_count > 0:
            print(f"✅ Interpoladas {interpolated_count} distancias faltantes")
        
        return df
    
    def smooth_trajectory(self, df):
        """Suavizar trayectoria eliminando ruido y saltos"""
        print("🔧 Suavizando trayectoria...")
        
        x_coords = df['x'].values
        y_coords = df['y'].values
        
        # 1. Detectar y corregir outliers extremos usando velocidad
        dt = 1.0 / self.target_frequency
        velocities = np.sqrt(np.diff(x_coords)**2 + np.diff(y_coords)**2) / dt
        
        # Velocidad máxima realista para humanos: 8 m/s (sprint)
        max_realistic_velocity = 8.0
        outlier_indices = []
        
        for i in range(1, len(velocities)):
            if velocities[i-1] > max_realistic_velocity:
                outlier_indices.append(i)
        
        # Corregir outliers por interpolación
        outlier_count = 0
        for idx in outlier_indices:
            if 0 < idx < len(df) - 1:
                df.loc[idx, 'x'] = (df.loc[idx-1, 'x'] + df.loc[idx+1, 'x']) / 2
                df.loc[idx, 'y'] = (df.loc[idx-1, 'y'] + df.loc[idx+1, 'y']) / 2
                outlier_count += 1
        
        if outlier_count > 0:
            print(f"✅ Corregidos {outlier_count} outliers de velocidad")
        
        # 2. Aplicar filtro Savitzky-Golay para suavizado
        if len(df) > 10:
            window_length = min(11, len(df) if len(df) % 2 == 1 else len(df) - 1)
            if window_length >= 5:
                df['x_smooth'] = savgol_filter(df['x'], window_length, 3)
                df['y_smooth'] = savgol_filter(df['y'], window_length, 3)
                print(f"✅ Aplicado suavizado Savitzky-Golay (ventana: {window_length})")
            else:
                df['x_smooth'] = df['x']
                df['y_smooth'] = df['y']
        else:
            df['x_smooth'] = df['x']
            df['y_smooth'] = df['y']
        
        return df
    
    def create_uniform_timeline(self, df):
        """Crear timeline uniforme a frecuencia constante"""
        print(f"🔧 Creando timeline uniforme a {self.target_frequency} Hz...")
        
        # Calcular duración total
        start_time = df['timestamp'].min()
        end_time = df['timestamp'].max()
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Crear puntos de tiempo uniformemente espaciados
        n_points = int(duration_seconds * self.target_frequency) + 1
        uniform_timestamps = pd.date_range(start=start_time, end=end_time, periods=n_points)
        
        print(f"✅ {n_points} puntos generados ({duration_seconds:.1f}s a {self.target_frequency} Hz)")
        
        # Convertir a tiempo numérico para interpolación
        time_numeric = (df['timestamp'] - start_time).dt.total_seconds()
        uniform_time_numeric = (uniform_timestamps - start_time).total_seconds()
        
        # Interpolar coordenadas
        interp_x = interp1d(time_numeric, df['x_smooth'], kind='cubic', 
                           bounds_error=False, fill_value='extrapolate')
        interp_y = interp1d(time_numeric, df['y_smooth'], kind='cubic',
                           bounds_error=False, fill_value='extrapolate')
        
        # Crear DataFrame uniforme
        uniform_df = pd.DataFrame({
            'timestamp': uniform_timestamps,
            'tag_id': df['tag_id'].iloc[0] if 'tag_id' in df.columns else 1,
            'x': interp_x(uniform_time_numeric),
            'y': interp_y(uniform_time_numeric)
        })
        
        # Interpolar distancias a anclas
        anchor_cols = ['anchor_1_dist', 'anchor_2_dist', 'anchor_3_dist', 
                      'anchor_4_dist', 'anchor_5_dist']
        
        for col in anchor_cols:
            if col in df.columns:
                valid_data = df[df[col] > 0]
                if len(valid_data) > 1:
                    valid_time = (valid_data['timestamp'] - start_time).dt.total_seconds()
                    interp_dist = interp1d(valid_time, valid_data[col], 
                                         kind='linear', bounds_error=False, 
                                         fill_value='extrapolate')
                    uniform_df[col] = interp_dist(uniform_time_numeric)
                else:
                    # Calcular distancias teóricas si no hay datos
                    anchor_id = int(col.split('_')[1])
                    if anchor_id in self.anchor_positions:
                        ax, ay = self.anchor_positions[anchor_id]
                        uniform_df[col] = np.sqrt((uniform_df['x'] - ax)**2 + 
                                                (uniform_df['y'] - ay)**2)
        
        # Calcular distancias teóricas para anclas sin datos
        for anchor_id, (ax, ay) in self.anchor_positions.items():
            col = f'anchor_{anchor_id}_dist'
            if col not in uniform_df.columns:
                uniform_df[col] = np.sqrt((uniform_df['x'] - ax)**2 + 
                                        (uniform_df['y'] - ay)**2)
        
        return uniform_df
    
    def calculate_quality_metrics(self, original_df, processed_df):
        """Calcular métricas de calidad del procesado"""
        print("\n📊 MÉTRICAS DE CALIDAD:")
        
        # Métricas temporales
        original_duration = (original_df['timestamp'].max() - 
                           original_df['timestamp'].min()).total_seconds()
        processed_duration = (processed_df['timestamp'].max() - 
                            processed_df['timestamp'].min()).total_seconds()
        
        original_freq = len(original_df) / original_duration
        processed_freq = len(processed_df) / processed_duration
        
        print(f"  📈 Frecuencia: {original_freq:.1f} Hz → {processed_freq:.1f} Hz")
        print(f"  📏 Puntos: {len(original_df)} → {len(processed_df)}")
        
        # Métricas de movimiento
        def calculate_distance(df):
            return np.sum(np.sqrt(np.diff(df['x'])**2 + np.diff(df['y'])**2))
        
        original_distance = calculate_distance(original_df)
        processed_distance = calculate_distance(processed_df)
        
        print(f"  🏃 Distancia total: {original_distance:.1f}m → {processed_distance:.1f}m")
        
        # Métricas de velocidad (para datos procesados)
        dt = 1.0 / self.target_frequency
        velocities = np.sqrt(np.diff(processed_df['x'])**2 + 
                           np.diff(processed_df['y'])**2) / dt
        
        avg_velocity = np.mean(velocities)
        max_velocity = np.max(velocities)
        
        print(f"  🚀 Velocidad promedio: {avg_velocity:.2f} m/s")
        print(f"  ⚡ Velocidad máxima: {max_velocity:.2f} m/s")
        
        # Verificar realismo
        realistic_checks = []
        if avg_velocity < 5.0:
            realistic_checks.append("✅ Velocidad promedio realista")
        else:
            realistic_checks.append("⚠️  Velocidad promedio alta")
            
        if max_velocity < 10.0:
            realistic_checks.append("✅ Velocidad máxima realista")
        else:
            realistic_checks.append("⚠️  Velocidad máxima muy alta")
        
        for check in realistic_checks:
            print(f"  {check}")
    
    def process_file(self, input_file, output_suffix="_processed_smooth"):
        """Procesar archivo completo"""
        print(f"\n🎯 PROCESANDO PARA REPLAY FLUIDO ({self.target_frequency} Hz)")
        print("=" * 60)
        
        # 1. Cargar y limpiar datos
        df = self.load_and_clean_positions(input_file)
        
        # 2. Interpolar distancias faltantes
        df = self.interpolate_missing_distances(df)
        
        # 3. Suavizar trayectoria
        df = self.smooth_trajectory(df)
        
        # 4. Crear timeline uniforme
        processed_df = self.create_uniform_timeline(df)
        
        # 5. Calcular métricas de calidad
        self.calculate_quality_metrics(df, processed_df)
        
        # 6. Guardar archivo procesado
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}{output_suffix}.csv"
        
        processed_df.to_csv(output_file, index=False)
        
        print(f"\n💾 ARCHIVO PROCESADO GUARDADO:")
        print(f"   📁 {output_file}")
        print(f"   📊 {len(processed_df)} puntos a {self.target_frequency} Hz")
        print(f"   🎬 Listo para replay ultra-fluido con movement_replay.py")
        
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Post-procesador UWB para replay fluido')
    parser.add_argument('input_file', help='Archivo CSV de posiciones a procesar')
    parser.add_argument('--frequency', type=float, default=15.0,
                       help='Frecuencia objetivo en Hz (default: 15.0)')
    parser.add_argument('--output-suffix', default='_processed_smooth',
                       help='Sufijo para archivo de salida')
    
    args = parser.parse_args()
    
    # Verificar que el archivo existe
    if not os.path.exists(args.input_file):
        print(f"❌ Error: Archivo no encontrado: {args.input_file}")
        return 1
    
    # Crear procesador y procesar archivo
    processor = UWBReplayProcessor(target_frequency=args.frequency)
    output_file = processor.process_file(args.input_file, args.output_suffix)
    
    print(f"\n🚀 PROCESADO COMPLETADO")
    print(f"📋 Para probar el replay fluido:")
    print(f"   python movement_replay.py \"{output_file}\"")
    
    return 0

if __name__ == "__main__":
    exit(main()) 