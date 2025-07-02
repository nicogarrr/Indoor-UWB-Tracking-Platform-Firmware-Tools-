#!/usr/bin/env python3
"""
Analizador Completo de Datos UWB - TFG
Evaluación de mejoras de frecuencia tras optimización del tag
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
from scipy.spatial.distance import cdist
import argparse
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class UWBDataAnalyzer:
    def __init__(self, ranging_file, positions_file):
        self.ranging_file = ranging_file
        self.positions_file = positions_file
        self.ranging_data = None
        self.positions_data = None
        self.analysis_results = {}
        
        # Configuración del sistema
        self.anchor_positions = {
            1: (-6.0, 0.0),
            2: (-1.6, 10.36), 
            3: (2.1, 10.36),
            4: (6.35, 0.0),
            5: (0.0, -1.8)
        }
        
    def load_data(self):
        """Cargar datos CSV"""
        print("📂 Cargando datos CSV...")
        try:
            self.ranging_data = pd.read_csv(self.ranging_file)
            self.positions_data = pd.read_csv(self.positions_file)
            print(f"✅ Ranging: {len(self.ranging_data)} mediciones")
            print(f"✅ Positions: {len(self.positions_data)} posiciones")
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return False
        return True
    
    def analyze_ranging_data(self):
        """Análisis detallado de datos de ranging"""
        print("\n🔍 ANÁLISIS DE DATOS DE RANGING")
        print("=" * 50)
        
        df = self.ranging_data
        results = {}
        
        # 1. Información básica
        duration_ms = df['Timestamp_ms'].max() - df['Timestamp_ms'].min()
        duration_s = duration_ms / 1000
        results['duration_seconds'] = duration_s
        results['total_measurements'] = len(df)
        results['avg_frequency'] = len(df) / duration_s
        
        print(f"📊 Duración total: {duration_s:.1f} segundos")
        print(f"📊 Total mediciones: {len(df)}")
        print(f"📊 Frecuencia promedio: {results['avg_frequency']:.1f} Hz")
        
        # 2. Análisis por ancla
        print("\n🎯 ANÁLISIS POR ANCLA:")
        anchor_stats = {}
        for anchor_id in sorted(df['Anchor_ID'].unique()):
            anchor_data = df[df['Anchor_ID'] == anchor_id]
            count = len(anchor_data)
            expected_count = duration_s * 3  # Esperamos ~3 Hz por ancla
            coverage = (count / expected_count) * 100
            
            # Detectar gaps temporales
            timestamps = sorted(anchor_data['Timestamp_ms'].values)
            gaps = []
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i-1]
                if gap > 500:  # Gap > 500ms es problemático
                    gaps.append(gap)
            
            # RSSI estadísticas
            rssi_values = anchor_data['Signal_Power_dBm']
            rssi_numeric = pd.to_numeric(rssi_values, errors='coerce')
            
            anchor_stats[anchor_id] = {
                'measurements': count,
                'coverage_percent': coverage,
                'gaps_count': len(gaps),
                'max_gap_ms': max(gaps) if gaps else 0,
                'avg_rssi': rssi_numeric.mean(),
                'rssi_std': rssi_numeric.std(),
                'invalid_rssi': rssi_values.isna().sum() + (rssi_values == 'inf').sum()
            }
            
            print(f"  Ancla {anchor_id}: {count:4d} mediciones ({coverage:5.1f}% cobertura) "
                  f"| RSSI: {rssi_numeric.mean():.1f}±{rssi_numeric.std():.1f}dBm "
                  f"| Gaps: {len(gaps)} (max: {max(gaps) if gaps else 0}ms)")
        
        results['anchor_stats'] = anchor_stats
        
        # 3. Detectar problemas críticos
        print("\n⚠️  PROBLEMAS DETECTADOS:")
        problems = []
        
        # Gaps temporales globales
        all_timestamps = sorted(df['Timestamp_ms'].unique())
        global_gaps = []
        for i in range(1, len(all_timestamps)):
            gap = all_timestamps[i] - all_timestamps[i-1]
            if gap > 200:  # Gap > 200ms
                global_gaps.append(gap)
        
        if global_gaps:
            problems.append(f"🔴 {len(global_gaps)} gaps temporales globales (max: {max(global_gaps)}ms)")
        
        # Valores RSSI inválidos
        invalid_rssi = df['Signal_Power_dBm'].isna().sum() + (df['Signal_Power_dBm'] == 'inf').sum()
        if invalid_rssi > 0:
            problems.append(f"🔴 {invalid_rssi} valores RSSI inválidos")
        
        # Cobertura baja de anclas
        for anchor_id, stats in anchor_stats.items():
            if stats['coverage_percent'] < 70:
                problems.append(f"🔴 Ancla {anchor_id}: cobertura baja ({stats['coverage_percent']:.1f}%)")
        
        if not problems:
            print("  ✅ No se detectaron problemas críticos")
        else:
            for problem in problems:
                print(f"  {problem}")
        
        results['problems'] = problems
        self.analysis_results['ranging'] = results
        
    def analyze_positions_data(self):
        """Análisis detallado de datos de posiciones"""
        print("\n🎯 ANÁLISIS DE DATOS DE POSICIONES")
        print("=" * 50)
        
        df = self.positions_data
        results = {}
        
        # 1. Información básica
        results['total_positions'] = len(df)
        
        # Convertir timestamps a datetime si es necesario
        if 'timestamp' in df.columns:
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                duration = (df['timestamp'].max() - df['timestamp'].min()).total_seconds()
                results['duration_seconds'] = duration
                results['avg_frequency'] = len(df) / duration
            except:
                duration = len(df) * 0.1  # Estimación
                results['duration_seconds'] = duration
                results['avg_frequency'] = len(df) / duration
        
        print(f"📊 Total posiciones: {len(df)}")
        print(f"📊 Duración estimada: {results['duration_seconds']:.1f} segundos")
        print(f"📊 Frecuencia promedio: {results['avg_frequency']:.1f} Hz")
        
        # 2. Análisis de coordenadas
        x_coords = df['x'].values
        y_coords = df['y'].values
        
        # Detectar saltos bruscos
        x_diffs = np.abs(np.diff(x_coords))
        y_diffs = np.abs(np.diff(y_coords))
        
        large_jumps_x = np.sum(x_diffs > 2.0)  # Saltos > 2m
        large_jumps_y = np.sum(y_diffs > 2.0)
        
        print(f"\n📍 COORDENADAS:")
        print(f"  Rango X: {x_coords.min():.2f} a {x_coords.max():.2f}m")
        print(f"  Rango Y: {y_coords.min():.2f} a {y_coords.max():.2f}m") 
        print(f"  Saltos bruscos: {large_jumps_x} en X, {large_jumps_y} en Y")
        
        # 3. Análisis de distancias a anclas
        print(f"\n🔗 DISTANCIAS A ANCLAS:")
        anchor_cols = ['anchor_1_dist', 'anchor_2_dist', 'anchor_3_dist', 'anchor_4_dist', 'anchor_5_dist']
        missing_data = {}
        
        for i, col in enumerate(anchor_cols, 1):
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                missing_percent = (zero_count / len(df)) * 100
                missing_data[i] = missing_percent
                print(f"  Ancla {i}: {zero_count} valores perdidos ({missing_percent:.1f}%)")
        
        # 4. Detectar problemas en posiciones
        print("\n⚠️  PROBLEMAS DETECTADOS:")
        pos_problems = []
        
        if large_jumps_x > 0 or large_jumps_y > 0:
            pos_problems.append(f"🔴 Saltos bruscos en trayectoria: {large_jumps_x + large_jumps_y} detectados")
        
        for anchor_id, missing_pct in missing_data.items():
            if missing_pct > 30:
                pos_problems.append(f"🔴 Ancla {anchor_id}: {missing_pct:.1f}% datos perdidos")
        
        if results['avg_frequency'] < 0.5:
            pos_problems.append(f"🔴 Frecuencia muy baja para replay fluido ({results['avg_frequency']:.1f} Hz)")
        
        if not pos_problems:
            print("  ✅ No se detectaron problemas críticos")
        else:
            for problem in pos_problems:
                print(f"  {problem}")
        
        results['problems'] = pos_problems
        results['missing_data'] = missing_data
        results['coordinate_stats'] = {
            'x_range': (x_coords.min(), x_coords.max()),
            'y_range': (y_coords.min(), y_coords.max()),
            'large_jumps': large_jumps_x + large_jumps_y
        }
        
        self.analysis_results['positions'] = results
        
    def create_processed_data(self, target_frequency=10.0):
        """Crear datos procesados para replay fluido"""
        print(f"\n🔧 PROCESANDO DATOS PARA REPLAY FLUIDO ({target_frequency} Hz)")
        print("=" * 60)
        
        df = self.positions_data.copy()
        
        # 1. Limpiar timestamps
        if 'timestamp' in df.columns:
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
            except:
                print("⚠️  Usando índices como timestamps")
                df['timestamp'] = pd.date_range(start='2025-01-01', periods=len(df), freq='100ms')
        
        # 2. Interpolar coordenadas faltantes
        valid_coords = (df['x'].notna()) & (df['y'].notna())
        if valid_coords.sum() < len(df):
            print(f"🔧 Interpolando {len(df) - valid_coords.sum()} coordenadas faltantes...")
            df.loc[~valid_coords, 'x'] = np.interp(
                df.index[~valid_coords], 
                df.index[valid_coords], 
                df.loc[valid_coords, 'x']
            )
            df.loc[~valid_coords, 'y'] = np.interp(
                df.index[~valid_coords], 
                df.index[valid_coords], 
                df.loc[valid_coords, 'y']
            )
        
        # 3. Suavizar trayectoria con filtro Savitzky-Golay
        if len(df) > 10:
            window_length = min(11, len(df) if len(df) % 2 == 1 else len(df) - 1)
            if window_length >= 3:
                print("🔧 Aplicando suavizado de trayectoria...")
                df['x_smooth'] = savgol_filter(df['x'], window_length, 2)
                df['y_smooth'] = savgol_filter(df['y'], window_length, 2)
            else:
                df['x_smooth'] = df['x']
                df['y_smooth'] = df['y']
        else:
            df['x_smooth'] = df['x']
            df['y_smooth'] = df['y']
        
        # 4. Detectar y corregir outliers
        print("🔧 Detectando y corrigiendo outliers...")
        
        # Velocidades instantáneas
        dt = 1.0 / target_frequency
        velocities = np.sqrt(np.diff(df['x_smooth'])**2 + np.diff(df['y_smooth'])**2) / dt
        velocity_threshold = np.percentile(velocities[velocities > 0], 95) * 2  # 2x percentil 95
        
        outlier_count = 0
        for i in range(1, len(df) - 1):
            if i < len(velocities) and velocities[i-1] > velocity_threshold:
                # Interpolar posición outlier
                df.loc[i, 'x_smooth'] = (df.loc[i-1, 'x_smooth'] + df.loc[i+1, 'x_smooth']) / 2
                df.loc[i, 'y_smooth'] = (df.loc[i-1, 'y_smooth'] + df.loc[i+1, 'y_smooth']) / 2
                outlier_count += 1
        
        if outlier_count > 0:
            print(f"🔧 Corregidos {outlier_count} outliers de velocidad")
        
        # 5. Crear timestamps uniformente espaciados
        start_time = df['timestamp'].min()
        end_time = df['timestamp'].max()
        duration = (end_time - start_time).total_seconds()
        
        n_points = int(duration * target_frequency)
        uniform_timestamps = pd.date_range(start=start_time, end=end_time, periods=n_points)
        
        # 6. Interpolar a frecuencia constante
        print(f"🔧 Interpolando a {target_frequency} Hz ({n_points} puntos)...")
        
        # Convertir timestamps a números para interpolación
        time_numeric = (df['timestamp'] - start_time).dt.total_seconds()
        uniform_time_numeric = (uniform_timestamps - start_time).total_seconds()
        
        # Interpolar coordenadas
        interp_x = interp1d(time_numeric, df['x_smooth'], kind='cubic', 
                           bounds_error=False, fill_value='extrapolate')
        interp_y = interp1d(time_numeric, df['y_smooth'], kind='cubic',
                           bounds_error=False, fill_value='extrapolate')
        
        # Crear DataFrame procesado
        processed_df = pd.DataFrame({
            'timestamp': uniform_timestamps,
            'tag_id': df['tag_id'].iloc[0],
            'x': interp_x(uniform_time_numeric),
            'y': interp_y(uniform_time_numeric)
        })
        
        # 7. Calcular distancias teóricas a anclas
        print("🔧 Calculando distancias teóricas a anclas...")
        for anchor_id, (ax, ay) in self.anchor_positions.items():
            distances = np.sqrt((processed_df['x'] - ax)**2 + (processed_df['y'] - ay)**2)
            processed_df[f'anchor_{anchor_id}_dist'] = distances
        
        # 8. Calcular métricas de calidad
        total_distance = np.sum(np.sqrt(np.diff(processed_df['x'])**2 + np.diff(processed_df['y'])**2))
        avg_speed = total_distance / duration
        max_speed = np.max(np.sqrt(np.diff(processed_df['x'])**2 + np.diff(processed_df['y'])**2) / dt)
        
        print(f"\n📈 MÉTRICAS DEL PROCESADO:")
        print(f"  ✅ Frecuencia objetivo: {target_frequency} Hz")
        print(f"  ✅ Puntos generados: {len(processed_df)}")
        print(f"  ✅ Distancia total: {total_distance:.1f}m")
        print(f"  ✅ Velocidad promedio: {avg_speed:.2f} m/s")
        print(f"  ✅ Velocidad máxima: {max_speed:.2f} m/s")
        
        return processed_df
    
    def save_processed_data(self, processed_df, output_suffix="_processed"):
        """Guardar datos procesados"""
        base_name = os.path.splitext(self.positions_file)[0]
        output_file = f"{base_name}{output_suffix}.csv"
        
        processed_df.to_csv(output_file, index=False)
        print(f"\n💾 Datos procesados guardados: {output_file}")
        return output_file
    
    def create_visualizations(self):
        """Crear visualizaciones de análisis"""
        print("\n📊 GENERANDO VISUALIZACIONES...")
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Análisis de Datos UWB', fontsize=16, fontweight='bold')
        
        # 1. Trayectoria original vs procesada
        ax1 = axes[0, 0]
        df_pos = self.positions_data
        ax1.scatter(df_pos['x'], df_pos['y'], alpha=0.6, s=20, label='Original', color='red')
        ax1.set_title('Trayectoria Original')
        ax1.set_xlabel('X (m)')
        ax1.set_ylabel('Y (m)')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Añadir posiciones de anclas
        for anchor_id, (ax, ay) in self.anchor_positions.items():
            ax1.plot(ax, ay, 'ks', markersize=10, label=f'A{anchor_id}' if anchor_id == 1 else "")
            ax1.annotate(f'A{anchor_id}', (ax, ay), xytext=(5, 5), textcoords='offset points')
        
        # 2. Análisis de RSSI por ancla
        ax2 = axes[0, 1]
        df_ranging = self.ranging_data
        
        # Convertir RSSI a numérico
        df_ranging_clean = df_ranging.copy()
        df_ranging_clean['Signal_Power_dBm'] = pd.to_numeric(
            df_ranging_clean['Signal_Power_dBm'], errors='coerce'
        )
        
        for anchor_id in sorted(df_ranging_clean['Anchor_ID'].unique()):
            anchor_data = df_ranging_clean[df_ranging_clean['Anchor_ID'] == anchor_id]
            rssi_values = anchor_data['Signal_Power_dBm'].dropna()
            if len(rssi_values) > 0:
                ax2.hist(rssi_values, alpha=0.6, bins=20, label=f'Ancla {anchor_id}')
        
        ax2.set_title('Distribución RSSI por Ancla')
        ax2.set_xlabel('RSSI (dBm)')
        ax2.set_ylabel('Frecuencia')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Timeline de mediciones por ancla
        ax3 = axes[1, 0]
        colors = ['red', 'blue', 'green', 'orange', 'purple']
        
        for i, anchor_id in enumerate(sorted(df_ranging['Anchor_ID'].unique())):
            anchor_data = df_ranging[df_ranging['Anchor_ID'] == anchor_id]
            times = anchor_data['Timestamp_ms'] / 1000  # Convertir a segundos
            y_values = [anchor_id] * len(times)
            ax3.scatter(times, y_values, alpha=0.6, s=10, 
                       color=colors[i % len(colors)], label=f'Ancla {anchor_id}')
        
        ax3.set_title('Timeline de Mediciones por Ancla')
        ax3.set_xlabel('Tiempo (s)')
        ax3.set_ylabel('Ancla ID')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. Distancias a anclas vs tiempo
        ax4 = axes[1, 1]
        anchor_cols = ['anchor_1_dist', 'anchor_2_dist', 'anchor_3_dist', 'anchor_4_dist', 'anchor_5_dist']
        
        for i, col in enumerate(anchor_cols):
            if col in df_pos.columns:
                # Filtrar valores válidos (no cero)
                valid_data = df_pos[df_pos[col] > 0]
                if len(valid_data) > 0:
                    ax4.plot(valid_data.index, valid_data[col], 
                            alpha=0.7, label=f'Ancla {i+1}', color=colors[i % len(colors)])
        
        ax4.set_title('Distancias a Anclas vs Tiempo')
        ax4.set_xlabel('Índice temporal')
        ax4.set_ylabel('Distancia (m)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Guardar visualización
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_file = f"uwb_analysis_{timestamp}.png"
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        print(f"📊 Visualizaciones guardadas: {plot_file}")
        
        plt.show()
    
    def generate_report(self):
        """Generar reporte completo"""
        print("\n📄 REPORTE DE ANÁLISIS UWB")
        print("=" * 60)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""
# Reporte de Análisis UWB
**Generado:** {timestamp}
**Archivos analizados:**
- Ranging: {self.ranging_file}
- Posiciones: {self.positions_file}

## Resumen Ejecutivo
"""
        
        # Añadir resumen de problemas
        ranging_problems = len(self.analysis_results.get('ranging', {}).get('problems', []))
        position_problems = len(self.analysis_results.get('positions', {}).get('problems', []))
        
        if ranging_problems == 0 and position_problems == 0:
            report += "✅ **ESTADO: EXCELENTE** - No se detectaron problemas críticos\n"
        elif ranging_problems + position_problems <= 3:
            report += "⚠️  **ESTADO: BUENO** - Problemas menores detectados\n"
        else:
            report += "🔴 **ESTADO: REQUIERE ATENCIÓN** - Múltiples problemas detectados\n"
        
        # Añadir recomendaciones
        report += f"""
## Recomendaciones para Replay Fluido

1. **Post-procesado obligatorio:** {ranging_problems + position_problems > 0}
2. **Interpolación temporal:** Necesaria para frecuencia constante
3. **Suavizado de trayectoria:** Recomendado para eliminar ruido
4. **Frecuencia objetivo:** 10-15 Hz para replay fluido
5. **Filtrado de outliers:** Eliminar saltos de velocidad > 5 m/s

## Próximos Pasos
- Ejecutar post-procesado con parámetros optimizados
- Validar datos procesados con visualizaciones
- Ajustar frecuencia según requisitos de aplicación
"""
        
        # Guardar reporte
        report_file = f"uwb_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 Reporte guardado: {report_file}")
        
        return report_file

def analyze_uwb_data(ranging_file, positions_file):
    """Análisis completo de datos UWB recogidos tras optimización"""
    
    print("🔷 ANÁLISIS COMPLETO DATOS UWB - POST OPTIMIZACIÓN")
    print("=" * 60)
    
    # === ANÁLISIS DATOS DE RANGING ===
    print("\n📡 ANÁLISIS DATOS DE RANGING")
    print("-" * 40)
    
    ranging_df = pd.read_csv(ranging_file)
    print(f"Total mediciones ranging: {len(ranging_df):,}")
    
    # Duración y frecuencia de ranging
    time_start_ms = ranging_df['Timestamp_ms'].min()
    time_end_ms = ranging_df['Timestamp_ms'].max()
    duration_s = (time_end_ms - time_start_ms) / 1000
    ranging_freq = len(ranging_df) / duration_s
    
    print(f"Rango temporal: {time_start_ms:,}ms - {time_end_ms:,}ms")
    print(f"Duración total: {duration_s:.1f} segundos ({duration_s/60:.1f} minutos)")
    print(f"Frecuencia ranging promedio: {ranging_freq:.1f} Hz")
    
    # Distribución por ancla
    print(f"\n📊 DISTRIBUCIÓN POR ANCLA:")
    anchor_counts = ranging_df['Anchor_ID'].value_counts().sort_index()
    for anchor, count in anchor_counts.items():
        freq_per_anchor = count / duration_s
        print(f"  Ancla {anchor}: {count:3d} mediciones ({freq_per_anchor:.1f} Hz)")
    
    # Análisis de gaps temporales
    print(f"\n⏱️  ANÁLISIS GAPS TEMPORALES:")
    ranging_sorted = ranging_df.sort_values('Timestamp_ms')
    time_diffs = ranging_sorted['Timestamp_ms'].diff().dropna()
    
    # Diferentes tipos de gaps
    normal_intervals = time_diffs[time_diffs <= 200]
    medium_gaps = time_diffs[(time_diffs > 200) & (time_diffs <= 1000)]
    large_gaps = time_diffs[time_diffs > 1000]
    
    print(f"  Intervalos normales (<200ms): {len(normal_intervals):,}")
    print(f"  Gaps medianos (200-1000ms): {len(medium_gaps)}")
    print(f"  Gaps grandes (>1000ms): {len(large_gaps)}")
    
    if len(normal_intervals) > 0:
        print(f"  Intervalo promedio normal: {normal_intervals.mean():.1f}ms")
        print(f"  Intervalo mediano normal: {normal_intervals.median():.1f}ms")
    
    if len(medium_gaps) > 0:
        print(f"  Gap mediano máximo: {medium_gaps.max():.0f}ms")
    
    if len(large_gaps) > 0:
        print(f"  Gap grande máximo: {large_gaps.max():.0f}ms")
    
    # Análisis de calidad de señal
    print(f"\n📶 ANÁLISIS CALIDAD DE SEÑAL:")
    strong_signals = ranging_df[ranging_df['Signal_Power_dBm'] > -85]
    weak_signals = ranging_df[ranging_df['Signal_Power_dBm'] <= -85]
    
    print(f"  Señales fuertes (>-85dBm): {len(strong_signals):,} ({len(strong_signals)/len(ranging_df)*100:.1f}%)")
    print(f"  Señales débiles (≤-85dBm): {len(weak_signals):,} ({len(weak_signals)/len(ranging_df)*100:.1f}%)")
    print(f"  RSSI promedio: {ranging_df['Signal_Power_dBm'].mean():.1f} dBm")
    print(f"  RSSI rango: {ranging_df['Signal_Power_dBm'].min():.1f} a {ranging_df['Signal_Power_dBm'].max():.1f} dBm")
    
    # === ANÁLISIS DATOS DE POSICIONES ===
    print(f"\n🎯 ANÁLISIS DATOS DE POSICIONES")
    print("-" * 40)
    
    pos_df = pd.read_csv(positions_file)
    print(f"Total posiciones calculadas: {len(pos_df):,}")
    
    # Duración y frecuencia de posiciones
    pos_df['timestamp'] = pd.to_datetime(pos_df['timestamp'])
    pos_start = pos_df['timestamp'].iloc[0]
    pos_end = pos_df['timestamp'].iloc[-1]
    pos_duration = (pos_end - pos_start).total_seconds()
    pos_freq = len(pos_df) / pos_duration if pos_duration > 0 else 0
    
    print(f"Duración posiciones: {pos_duration:.1f} segundos")
    print(f"Frecuencia posiciones: {pos_freq:.1f} Hz")
    
    # Análisis de pérdida de datos por ancla
    print(f"\n❌ PÉRDIDA DE DATOS POR ANCLA:")
    total_positions = len(pos_df)
    for i in range(1, 6):
        col = f'anchor_{i}_dist'
        zeros = (pos_df[col] == 0).sum()
        percent = (zeros / total_positions) * 100
        print(f"  Ancla {i}: {zeros}/{total_positions} perdidos ({percent:.1f}%)")
    
    # Análisis de cobertura espacial
    print(f"\n🗺️  COBERTURA ESPACIAL:")
    x_min, x_max = pos_df['x'].min(), pos_df['x'].max()
    y_min, y_max = pos_df['y'].min(), pos_df['y'].max()
    
    print(f"  Rango X: {x_min:.2f} a {x_max:.2f} metros ({x_max-x_min:.2f}m)")
    print(f"  Rango Y: {y_min:.2f} a {y_max:.2f} metros ({y_max-y_min:.2f}m)")
    
    # === COMPARACIÓN CON DATOS ANTERIORES ===
    print(f"\n📈 COMPARACIÓN CON CAPTURA ANTERIOR")
    print("-" * 40)
    
    # Datos de la captura anterior (uwb_positions_20250702_125828.csv)
    prev_freq = 1.4  # Hz frecuencia anterior
    prev_positions = 78  # posiciones anteriores
    prev_duration = 55.6  # segundos anteriores
    
    freq_improvement = pos_freq / prev_freq
    positions_improvement = len(pos_df) / prev_positions
    
    print(f"  Frecuencia anterior: {prev_freq:.1f} Hz")
    print(f"  Frecuencia actual: {pos_freq:.1f} Hz")
    print(f"  Mejora frecuencia: {freq_improvement:.1f}x ({(freq_improvement-1)*100:+.1f}%)")
    print(f"  ")
    print(f"  Posiciones anterior: {prev_positions}")
    print(f"  Posiciones actual: {len(pos_df)}")
    print(f"  Mejora posiciones: {positions_improvement:.1f}x ({(positions_improvement-1)*100:+.1f}%)")
    
    # === EVALUACIÓN GENERAL ===
    print(f"\n✅ EVALUACIÓN GENERAL")
    print("-" * 40)
    
    # Criterios de evaluación
    if pos_freq >= 4.0:
        freq_status = "EXCELENTE"
    elif pos_freq >= 2.5:
        freq_status = "BUENA"
    elif pos_freq >= 1.5:
        freq_status = "ACEPTABLE"
    else:
        freq_status = "INSUFICIENTE"
    
    # Pérdida de datos promedio
    total_missing = sum((pos_df[f'anchor_{i}_dist'] == 0).sum() for i in range(1, 6))
    total_expected = len(pos_df) * 5
    missing_rate = (total_missing / total_expected) * 100
    
    if missing_rate <= 5:
        quality_status = "EXCELENTE"
    elif missing_rate <= 15:
        quality_status = "BUENA"
    elif missing_rate <= 30:
        quality_status = "ACEPTABLE"
    else:
        quality_status = "PROBLEMÁTICA"
    
    print(f"  Frecuencia de posiciones: {pos_freq:.1f} Hz - {freq_status}")
    print(f"  Pérdida de datos: {missing_rate:.1f}% - {quality_status}")
    print(f"  Duración captura: {pos_duration:.1f}s - {'ACEPTABLE' if pos_duration >= 30 else 'CORTA'}")
    
    if pos_freq >= 3.0 and missing_rate <= 15:
        overall = "✅ OPTIMIZACIÓN EXITOSA"
    elif pos_freq >= 2.0 and missing_rate <= 25:
        overall = "⚠️  OPTIMIZACIÓN PARCIAL"
    else:
        overall = "❌ OPTIMIZACIÓN INSUFICIENTE"
    
    print(f"  ")
    print(f"  RESULTADO GENERAL: {overall}")
    
    # Retornar datos para análisis adicional
    return {
        'ranging_freq': ranging_freq,
        'position_freq': pos_freq,
        'position_count': len(pos_df),
        'duration': pos_duration,
        'missing_rate': missing_rate,
        'improvement_factor': freq_improvement
    }

def main():
    parser = argparse.ArgumentParser(description='Análisis y post-procesado de datos UWB')
    parser.add_argument('ranging_file', help='Archivo CSV de datos de ranging')
    parser.add_argument('positions_file', help='Archivo CSV de datos de posiciones')
    parser.add_argument('--frequency', type=float, default=10.0, 
                       help='Frecuencia objetivo para replay (Hz, default: 10.0)')
    parser.add_argument('--no-plots', action='store_true', 
                       help='No generar visualizaciones')
    parser.add_argument('--output-suffix', default='_processed',
                       help='Sufijo para archivo de salida')
    
    args = parser.parse_args()
    
    # Crear analizador
    analyzer = UWBDataAnalyzer(args.ranging_file, args.positions_file)
    
    # Cargar datos
    if not analyzer.load_data():
        return 1
    
    # Realizar análisis
    analyzer.analyze_ranging_data()
    analyzer.analyze_positions_data()
    
    # Procesar datos
    processed_data = analyzer.create_processed_data(args.frequency)
    
    # Guardar datos procesados
    output_file = analyzer.save_processed_data(processed_data, args.output_suffix)
    
    # Generar visualizaciones
    if not args.no_plots:
        analyzer.create_visualizations()
    
    # Generar reporte
    analyzer.generate_report()
    
    print(f"\n🎉 ANÁLISIS COMPLETADO")
    print(f"📁 Archivo procesado: {output_file}")
    print(f"🚀 Listo para replay fluido con movement_replay.py")
    
    return 0

if __name__ == "__main__":
    exit(main()) 