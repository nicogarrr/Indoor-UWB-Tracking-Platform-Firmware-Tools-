#!/usr/bin/env python3
"""
Sistema Integrado de Análisis UWB para TFG Fútbol Sala
======================================================

Herramienta consolidada que combina:
- Procesamiento avanzado de datos CSV (ex csv_processor.py)
- Análisis completo de rendimiento (ex performance_analyzer.py)  
- Generación de mapas de calor (ex heatmap_generator.py)

Autor: TFG Sistema UWB Fútbol Sala
Versión: 2.0 - Consolidada
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from scipy import interpolate
from scipy.signal import savgol_filter, find_peaks
from scipy.stats import gaussian_kde
from scipy.ndimage import gaussian_filter
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Wedge, Circle
import os
import glob
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class UWBAnalyzer:
    """Sistema integrado de análisis UWB para fútbol sala"""
    
    def __init__(self, data_dir="data", output_dir="outputs"):
        self.data_dir = data_dir
        self.output_dir = output_dir
        
        # Crear estructura organizada de directorios
        os.makedirs(os.path.join(output_dir, "heatmaps"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "reports"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "comparisons"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "dashboards"), exist_ok=True)
        
        # Configuración de cancha
        self.court = {
            'length': 40.0, 'width': 20.0,
            'goal_area_length': 6.0, 'center_circle_radius': 3.0
        }
        
        # Parámetros de procesamiento
        self.filter_params = {
            'max_distance': 60.0, 'min_distance': 0.1,
            'max_velocity': 12.0, 'teleport_threshold': 15.0,
            'target_frequency': 25
        }
        
        # Umbrales de rendimiento
        self.performance_thresholds = {
            'walking_speed': 1.5, 'jogging_speed': 3.0,
            'running_speed': 5.0, 'sprinting_speed': 7.0,
            'high_intensity_threshold': 4.0
        }
        
        # Zonas tácticas
        self.tactical_zones = {
            'area_defensiva_propia': {'bounds': [0, 6, 0, 20], 'importance': 'CRITICA'},
            'zona_defensiva': {'bounds': [0, 13.33, 0, 20], 'importance': 'ALTA'},
            'zona_media': {'bounds': [13.33, 26.67, 0, 20], 'importance': 'MEDIA'},
            'zona_ofensiva': {'bounds': [26.67, 40, 0, 20], 'importance': 'ALTA'},
            'area_ofensiva_rival': {'bounds': [34, 40, 0, 20], 'importance': 'CRITICA'}
        }
        
        # Configuración de visualización
        plt.style.use('seaborn-v0_8-darkgrid')
        self.setup_colors()
    
    def setup_colors(self):
        """Configurar esquemas de colores"""
        self.colors = {
            'walking': '#2E8B57', 'jogging': '#4169E1',
            'running': '#FF8C00', 'sprinting': '#DC143C',
            'zone_low': '#90EE90', 'zone_medium': '#FFD700',
            'zone_high': '#FF6347', 'zone_critical': '#8B0000'
        }
        
        # Esquemas para mapas de calor
        self.heat_colors = ['#000033', '#003399', '#0066CC', '#3399FF',
                           '#66CCFF', '#CCFF99', '#FFFF66', '#FFCC33',
                           '#FF9900', '#FF6600', '#FF3300', '#CC0000']
    
    # ================================
    # MÓDULO 1: PROCESAMIENTO DE DATOS
    # ================================
    
    def load_and_process_data(self, csv_file):
        """Cargar y procesar datos CSV completo"""
        # Mostrar información de ubicación
        full_path = os.path.abspath(csv_file)
        folder_name = os.path.dirname(csv_file)
        file_name = os.path.basename(csv_file)
        
        print(f"📊 PROCESANDO DATOS:")
        print(f"   📁 Directorio: {folder_name}/")
        print(f"   📄 Archivo: {file_name}")
        print(f"   🗂️  Ruta completa: {full_path}")
        print(f"   📍 Trabajando desde: {os.getcwd()}")
        
        # Cargar datos
        df = self._load_csv_data(csv_file)
        if df is None:
            return None
        
        # Aplicar filtros de procesamiento
        df = self._apply_comprehensive_filtering(df)
        
        # Calcular métricas de movimiento
        df = self._calculate_movement_metrics(df)
        
        # Asignar zonas tácticas
        df = self._assign_tactical_zones(df)
        
        print(f"✅ Procesamiento completado: {len(df)} registros válidos")
        return df
    
    def _load_csv_data(self, csv_file):
        """Cargar datos CSV con validación"""
        try:
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Validar columnas requeridas
            required_cols = ['timestamp', 'x', 'y']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Columnas faltantes: {missing_cols}")
            
            # Filtro básico de coordenadas
            initial_count = len(df)
            df = df.dropna(subset=['x', 'y'])
            df = df[(df['x'].between(-10, 50)) & (df['y'].between(-10, 30))]
            
            print(f"   Datos válidos: {len(df)}/{initial_count}")
            return df
            
        except Exception as e:
            print(f"❌ Error cargando {csv_file}: {e}")
            return None
    
    def _apply_comprehensive_filtering(self, df):
        """Aplicar filtros completos de calidad de datos"""
        print("   🔧 Aplicando filtros avanzados...")
        
        # 1. Filtrar outliers de velocidad
        df = self._filter_velocity_outliers(df)
        
        # 2. Interpolación a frecuencia constante
        df = self._interpolate_to_constant_frequency(df)
        
        # 3. Suavizado con filtro Savitzky-Golay
        df = self._apply_smoothing(df)
        
        return df
    
    def _filter_velocity_outliers(self, df):
        """Filtrar velocidades imposibles"""
        if len(df) < 2:
            return df
        
        # Calcular velocidades
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        
        # Filtrar velocidades imposibles
        original_len = len(df)
        valid_velocity = (df['velocity'] <= self.filter_params['max_velocity']) | df['velocity'].isna()
        valid_teleport = (df['velocity'] <= self.filter_params['teleport_threshold']) | df['velocity'].isna()
        
        df = df[valid_velocity & valid_teleport]
        
        print(f"      Outliers de velocidad eliminados: {original_len - len(df)}")
        
        # Limpiar columnas temporales
        df = df.drop(['dx', 'dy', 'dt', 'distance', 'velocity'], axis=1, errors='ignore')
        return df
    
    def _interpolate_to_constant_frequency(self, df):
        """Interpolar a frecuencia constante"""
        if len(df) < 10:
            return df
        
        print("   🔄 Interpolando a 25 Hz...")
        
        # Crear timeline regular
        start_time = df['timestamp'].iloc[0]
        end_time = df['timestamp'].iloc[-1]
        freq = f"{1000//self.filter_params['target_frequency']}ms"
        regular_timeline = pd.date_range(start=start_time, end=end_time, freq=freq)
        
        # Interpolar posiciones
        f_x = interpolate.interp1d(df['timestamp'].astype(np.int64), df['x'], 
                                  kind='linear', bounds_error=False, fill_value=df['x'].iloc[0])
        f_y = interpolate.interp1d(df['timestamp'].astype(np.int64), df['y'], 
                                  kind='linear', bounds_error=False, fill_value=df['y'].iloc[0])
        
        # Crear DataFrame interpolado
        interpolated_df = pd.DataFrame({
            'timestamp': regular_timeline,
            'x': f_x(regular_timeline.astype(np.int64)),
            'y': f_y(regular_timeline.astype(np.int64))
        })
        
        # Mantener otras columnas si existen
        for col in df.columns:
            if col not in ['timestamp', 'x', 'y'] and col in df.columns:
                interpolated_df[col] = df[col].iloc[0]  # Usar primer valor
        
        print(f"      Interpolación: {len(df)} → {len(interpolated_df)} puntos")
        return interpolated_df
    
    def _apply_smoothing(self, df, window_length=5):
        """Aplicar suavizado Savitzky-Golay"""
        if len(df) < window_length * 2:
            return df
        
        print("   🌊 Aplicando suavizado...")
        
        try:
            df['x'] = savgol_filter(df['x'], window_length, 3)
            df['y'] = savgol_filter(df['y'], window_length, 3)
        except Exception as e:
            print(f"      Warning: Error en suavizado: {e}")
        
        return df
    
    def _calculate_movement_metrics(self, df):
        """Calcular métricas completas de movimiento"""
        print("   📈 Calculando métricas de movimiento...")
        
        # Calcular velocidades y aceleraciones
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        df['acceleration'] = df['velocity'].diff() / df['dt']
        
        # Clasificar tipos de movimiento
        conditions = [
            df['velocity'] <= self.performance_thresholds['walking_speed'],
            (df['velocity'] > self.performance_thresholds['walking_speed']) & 
            (df['velocity'] <= self.performance_thresholds['jogging_speed']),
            (df['velocity'] > self.performance_thresholds['jogging_speed']) & 
            (df['velocity'] <= self.performance_thresholds['running_speed']),
            df['velocity'] > self.performance_thresholds['running_speed']
        ]
        
        choices = ['walking', 'jogging', 'running', 'sprinting']
        df['movement_type'] = np.select(conditions, choices, default='walking')
        
        # Calcular intensidad normalizada (0-100)
        max_vel = df['velocity'].quantile(0.95)
        df['intensity'] = np.clip((df['velocity'] / max_vel) * 100, 0, 100)
        
        return df
    
    def _assign_tactical_zones(self, df):
        """Asignar zonas tácticas a cada posición"""
        def get_zone(row):
            x, y = row['x'], row['y']
            for zone_name, zone_data in self.tactical_zones.items():
                x_min, x_max, y_min, y_max = zone_data['bounds']
                if x_min <= x <= x_max and y_min <= y <= y_max:
                    return zone_name
            return 'fuera_zona'
        
        df['tactical_zone'] = df.apply(get_zone, axis=1)
        return df
    
    # =======================================
    # MÓDULO 2: ANÁLISIS DE RENDIMIENTO
    # =======================================
    
    def analyze_performance(self, df):
        """Análisis completo de rendimiento deportivo"""
        print("\n🏃 ANÁLISIS DE RENDIMIENTO DEPORTIVO")
        print("=" * 50)
        
        # Métricas básicas
        basic_metrics = self._calculate_basic_metrics(df)
        
        # Análisis de sprints
        sprint_episodes = self._analyze_sprint_episodes(df)
        
        # Análisis de zonas
        zone_stats = self._analyze_zone_activity(df)
        
        # Métricas específicas de fútbol sala
        futsal_metrics = self._calculate_futsal_metrics(df)
        
        # Generar reporte
        self._generate_performance_report(df, basic_metrics, sprint_episodes, 
                                        zone_stats, futsal_metrics)
        
        return {
            'basic_metrics': basic_metrics,
            'sprint_episodes': sprint_episodes,
            'zone_stats': zone_stats,
            'futsal_metrics': futsal_metrics
        }
    
    def _calculate_basic_metrics(self, df):
        """Calcular métricas básicas de rendimiento"""
        total_time = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds()
        total_distance = df['distance'].sum()
        avg_speed = df['velocity'].mean()
        max_speed = df['velocity'].max()
        
        # Tiempo en cada tipo de movimiento
        movement_times = {}
        for movement_type in ['walking', 'jogging', 'running', 'sprinting']:
            movement_times[movement_type] = len(df[df['movement_type'] == movement_type]) * df['dt'].mean()
        
        return {
            'total_time': total_time,
            'total_distance': total_distance,
            'avg_speed': avg_speed,
            'max_speed': max_speed,
            'movement_times': movement_times
        }
    
    def _analyze_sprint_episodes(self, df):
        """Analizar episodios de sprint"""
        sprint_threshold = self.performance_thresholds['sprinting_speed']
        sprint_mask = df['velocity'] > sprint_threshold
        
        # Encontrar episodios de sprint
        sprint_episodes = []
        in_sprint = False
        sprint_start = None
        
        for i, is_sprint in enumerate(sprint_mask):
            if is_sprint and not in_sprint:
                # Inicio de sprint
                in_sprint = True
                sprint_start = i
            elif not is_sprint and in_sprint:
                # Fin de sprint
                in_sprint = False
                sprint_end = i
                
                # Validar duración mínima (2 segundos)
                duration = (df.iloc[sprint_end]['timestamp'] - 
                           df.iloc[sprint_start]['timestamp']).total_seconds()
                
                if duration >= 2.0:
                    sprint_data = df.iloc[sprint_start:sprint_end]
                    episode = {
                        'start_time': sprint_data.iloc[0]['timestamp'],
                        'end_time': sprint_data.iloc[-1]['timestamp'],
                        'duration': duration,
                        'distance': sprint_data['distance'].sum(),
                        'avg_speed': sprint_data['velocity'].mean(),
                        'max_speed': sprint_data['velocity'].max(),
                        'start_pos': (sprint_data.iloc[0]['x'], sprint_data.iloc[0]['y']),
                        'end_pos': (sprint_data.iloc[-1]['x'], sprint_data.iloc[-1]['y'])
                    }
                    sprint_episodes.append(episode)
        
        return sprint_episodes
    
    def _analyze_zone_activity(self, df):
        """Analizar actividad por zonas tácticas"""
        zone_stats = {}
        
        for zone_name in self.tactical_zones.keys():
            zone_data = df[df['tactical_zone'] == zone_name]
            
            if len(zone_data) > 0:
                zone_stats[zone_name] = {
                    'time_spent': len(zone_data) * df['dt'].mean(),
                    'distance_covered': zone_data['distance'].sum(),
                    'avg_speed': zone_data['velocity'].mean(),
                    'max_speed': zone_data['velocity'].max(),
                    'sprint_count': len(zone_data[zone_data['movement_type'] == 'sprinting'])
                }
            else:
                zone_stats[zone_name] = {
                    'time_spent': 0, 'distance_covered': 0,
                    'avg_speed': 0, 'max_speed': 0, 'sprint_count': 0
                }
        
        return zone_stats
    
    def _calculate_futsal_metrics(self, df):
        """Métricas específicas de fútbol sala"""
        # Cambios de dirección (aceleración > umbral)
        direction_changes = len(df[abs(df['acceleration']) > 2.0])
        
        # Tiempo en área ofensiva vs defensiva
        offensive_time = len(df[df['x'] > 20]) * df['dt'].mean()
        defensive_time = len(df[df['x'] <= 20]) * df['dt'].mean()
        
        # Distancia promedio al centro de la cancha
        center_x, center_y = 20, 10
        df['distance_to_center'] = np.sqrt((df['x'] - center_x)**2 + (df['y'] - center_y)**2)
        avg_distance_to_center = df['distance_to_center'].mean()
        
        return {
            'direction_changes': direction_changes,
            'offensive_time_pct': (offensive_time / (offensive_time + defensive_time)) * 100,
            'avg_distance_to_center': avg_distance_to_center
        }
    
    def _generate_performance_report(self, df, basic_metrics, sprint_episodes, 
                                   zone_stats, futsal_metrics):
        """Generar reporte completo de rendimiento"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_dir, f"reports/performance_report_{timestamp}.txt")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("🏟️ REPORTE DE ANÁLISIS DE RENDIMIENTO - FÚTBOL SALA\n")
            f.write("=" * 60 + "\n\n")
            
            # Métricas básicas
            f.write("📊 MÉTRICAS BÁSICAS:\n")
            f.write(f"⏱️  Duración total: {basic_metrics['total_time']:.1f} segundos\n")
            f.write(f"📏 Distancia total: {basic_metrics['total_distance']:.1f} metros\n")
            f.write(f"🏃 Velocidad promedio: {basic_metrics['avg_speed']:.2f} m/s\n")
            f.write(f"⚡ Velocidad máxima: {basic_metrics['max_speed']:.2f} m/s\n\n")
            
            # Análisis de sprints
            f.write("💨 ANÁLISIS DE SPRINTS:\n")
            f.write(f"🔥 Total de sprints: {len(sprint_episodes)}\n")
            if sprint_episodes:
                avg_sprint_duration = sum(ep['duration'] for ep in sprint_episodes) / len(sprint_episodes)
                f.write(f"⏱️  Duración promedio: {avg_sprint_duration:.1f} segundos\n")
                max_sprint_speed = max(ep['max_speed'] for ep in sprint_episodes)
                f.write(f"🚀 Velocidad máxima en sprint: {max_sprint_speed:.2f} m/s\n")
            f.write("\n")
            
            # Análisis por zonas
            f.write("🎯 ANÁLISIS POR ZONAS TÁCTICAS:\n")
            for zone_name, stats in zone_stats.items():
                f.write(f"📍 {zone_name}:\n")
                f.write(f"   ⏱️  Tiempo: {stats['time_spent']:.1f}s\n")
                f.write(f"   📏 Distancia: {stats['distance_covered']:.1f}m\n")
                f.write(f"   🏃 Vel. promedio: {stats['avg_speed']:.2f} m/s\n")
            f.write("\n")
            
            # Métricas específicas fútbol sala
            f.write("⚽ MÉTRICAS ESPECÍFICAS FÚTBOL SALA:\n")
            f.write(f"🔄 Cambios de dirección: {futsal_metrics['direction_changes']}\n")
            f.write(f"⚔️  Tiempo ofensivo: {futsal_metrics['offensive_time_pct']:.1f}%\n")
            f.write(f"📍 Distancia promedio al centro: {futsal_metrics['avg_distance_to_center']:.1f}m\n")
        
        print(f"📋 Reporte guardado: {report_file}")
    
    # =====================================
    # MÓDULO 3: MAPAS DE CALOR
    # =====================================
    
    def generate_heatmap(self, df, style='professional', method='gaussian'):
        """Generar mapa de calor de densidad de movimiento"""
        print("\n🔥 GENERANDO MAPA DE CALOR")
        print("=" * 40)
        
        # Calcular densidad
        density_grid = self._calculate_density_grid(df, method)
        
        # Crear visualización
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Dibujar fondo de cancha
        self._draw_futsal_court_background(ax)
        
        # Crear mapa de calor
        if density_grid is not None:
            extent = (0, self.court['length'], 0, self.court['width'])
            
            if style == 'professional':
                cmap = LinearSegmentedColormap.from_list('custom', self.heat_colors)
            else:
                cmap = 'hot'
            
            heatmap = ax.imshow(density_grid, extent=extent, origin='lower', 
                               cmap=cmap, alpha=0.7, interpolation='bilinear')
        
        # Configurar visualización
        ax.set_xlim(-2, 42)
        ax.set_ylim(-2, 22)
        ax.set_aspect('equal')
        ax.set_title('MAPA DE CALOR - DENSIDAD DE MOVIMIENTO\nFútbol Sala UWB System', 
                    fontsize=16, fontweight='bold', pad=20)
        
        # Agregar colorbar
        cbar = plt.colorbar(heatmap, ax=ax, shrink=0.8)
        cbar.set_label('Densidad de Actividad', fontsize=12)
        
        # Agregar estadísticas
        total_time = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds()
        total_distance = df['distance'].sum()
        
        stats_text = (f"⏱️ Duración: {total_time:.1f}s\n"
                     f"📏 Distancia: {total_distance:.1f}m\n"
                     f"📊 Puntos: {len(df)}")
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
               verticalalignment='top', bbox=dict(boxstyle='round', 
               facecolor='white', alpha=0.8), fontsize=10)
        
        # Guardar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        heatmap_file = os.path.join(self.output_dir, "heatmaps", 
                                   f"heatmap_{style}_{len(df)}pts_{total_time:.0f}s_{timestamp}.png")
        plt.savefig(heatmap_file, dpi=300, bbox_inches='tight')
        print(f"🔥 Mapa de calor guardado: {heatmap_file}")
        
        plt.show()
        return fig, ax
    
    def _calculate_density_grid(self, df, method='gaussian'):
        """Calcular grid de densidad"""
        resolution = 100
        x_grid = np.linspace(0, self.court['length'], resolution)
        y_grid = np.linspace(0, self.court['width'], resolution//2)
        
        if method == 'gaussian':
            # Crear histograma 2D
            hist, x_edges, y_edges = np.histogram2d(
                df['x'], df['y'], 
                bins=[resolution, resolution//2],
                range=[[0, self.court['length']], [0, self.court['width']]]
            )
            
            # Aplicar suavizado gaussiano
            density = gaussian_filter(hist, sigma=2.0)
            return density.T
        
        elif method == 'kde':
            if len(df) > 5000:
                df_sample = df.sample(n=5000, random_state=42)
            else:
                df_sample = df
            
            kde = gaussian_kde([df_sample['x'], df_sample['y']])
            X, Y = np.meshgrid(x_grid, y_grid)
            positions = np.vstack([X.ravel(), Y.ravel()])
            density = kde(positions).reshape(X.shape)
            return density
    
    def _draw_futsal_court_background(self, ax):
        """Dibujar cancha de fútbol sala como fondo"""
        # Fondo de la cancha
        court = Rectangle((0, 0), 40, 20, linewidth=3,
                         edgecolor='white', facecolor='none', alpha=0.9)
        ax.add_patch(court)
        
        # Línea central
        ax.plot([20, 20], [0, 20], 'white', linewidth=2, alpha=0.9)
        
        # Círculo central
        center_circle = Circle((20, 10), 3, linewidth=2,
                             edgecolor='white', facecolor='none', alpha=0.9)
        ax.add_patch(center_circle)
        
        # Áreas de portería
        penalty_left = Wedge((0, 10), 6, -90, 90, linewidth=2,
                           edgecolor='white', facecolor='none', alpha=0.9)
        penalty_right = Wedge((40, 10), 6, 90, 270, linewidth=2,
                            edgecolor='white', facecolor='none', alpha=0.9)
        ax.add_patch(penalty_left)
        ax.add_patch(penalty_right)
        
        # Porterías
        ax.plot([0, 0], [8.5, 11.5], 'white', linewidth=4, alpha=0.9)
        ax.plot([40, 40], [8.5, 11.5], 'white', linewidth=4, alpha=0.9)
        
        # Puntos de penalti
        ax.plot(6, 10, 'wo', markersize=8, alpha=0.9)
        ax.plot(34, 10, 'wo', markersize=8, alpha=0.9)
    
    # ================================
    # INTERFAZ PRINCIPAL
    # ================================
    
    def save_processed_data(self, df, original_file):
        """Guardar datos procesados en CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = os.path.basename(original_file).replace('.csv', '')
        
        # Crear directorio processed_data si no existe
        os.makedirs("processed_data", exist_ok=True)
        
        # Nombre del archivo procesado
        processed_filename = f"{original_name}_processed_{timestamp}.csv"
        processed_path = os.path.join("processed_data", processed_filename)
        
        # Guardar CSV procesado
        df.to_csv(processed_path, index=False)
        
        print(f"💾 DATOS PROCESADOS GUARDADOS:")
        print(f"   📁 Archivo: processed_data/{processed_filename}")
        print(f"   📊 Registros: {len(df)}")
        print(f"   🔧 Filtros aplicados: ✅ Outliers ✅ Interpolación ✅ Suavizado")
        
        return processed_path

    def run_complete_analysis(self, csv_file, save_processed=True):
        """Ejecutar análisis completo de un archivo CSV"""
        print("🏟️ INICIANDO ANÁLISIS COMPLETO UWB")
        print("=" * 60)
        
        # 1. Procesar datos
        df = self.load_and_process_data(csv_file)
        if df is None:
            return None
        
        # 2. Guardar datos procesados (NUEVA FUNCIONALIDAD)
        processed_file = None
        if save_processed:
            processed_file = self.save_processed_data(df, csv_file)
        
        # 3. Análisis de rendimiento
        analysis_results = self.analyze_performance(df)
        
        # 4. Generar mapa de calor
        self.generate_heatmap(df)
        
        print(f"\n✅ ANÁLISIS COMPLETADO")
        print(f"📁 Resultados guardados en: {self.output_dir}")
        if processed_file:
            print(f"💾 Datos procesados guardados en: {processed_file}")
        
        return {
            'processed_data': df,
            'processed_file': processed_file,
            'analysis_results': analysis_results
        }

def select_directory_and_file():
    """Selección interactiva de directorio y archivo"""
    import glob
    
    print("\n📁 SELECCIONAR DIRECTORIO DE DATOS:")
    print("=" * 50)
    print("1. 📊 processed_data/ - Datos ya procesados")
    print("2. 📥 data/ - Datos originales")
    print("3. 🔍 Buscar en ambos directorios")
    print("0. ❌ Cancelar")
    
    while True:
        try:
            dir_choice = input("\n👆 Selecciona directorio (0-3): ").strip()
            
            if dir_choice == '0':
                print("❌ Operación cancelada")
                return None
            elif dir_choice == '1':
                data_files = glob.glob("processed_data/*.csv")
                dir_name = "📊 processed_data"
                search_path = "processed_data/"
                break
            elif dir_choice == '2':
                data_files = glob.glob("data/*.csv")
                dir_name = "📥 data"
                search_path = "data/"
                break
            elif dir_choice == '3':
                data_files = glob.glob("processed_data/*.csv") + glob.glob("data/*.csv")
                dir_name = "🔍 ambos directorios"
                search_path = "processed_data/ y data/"
                break
            else:
                print("❌ Opción inválida. Selecciona 0, 1, 2 o 3")
                continue
        except KeyboardInterrupt:
            print("\n❌ Operación cancelada")
            return None
    
    if not data_files:
        print(f"❌ No se encontraron archivos CSV en {search_path}")
        return None
    
    print(f"\n📁 ARCHIVOS EN {dir_name.upper()}:")
    print("=" * 60)
    
    for i, file_path in enumerate(data_files, 1):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024  # KB
        folder_icon = "📊" if file_path.startswith("processed_data") else "📥"
        folder_name = "processed_data" if file_path.startswith("processed_data") else "data"
        print(f"{i:2d}. {folder_icon} {folder_name}/{file_name:<35} ({file_size:6.1f} KB)")
    
    print(f"\n👆 Selecciona un archivo (1-{len(data_files)}) o 0 para cancelar:")
    
    while True:
        try:
            choice = input("Opción: ").strip()
            
            if choice == '0':
                print("❌ Operación cancelada")
                return None
            
            file_idx = int(choice) - 1
            
            if 0 <= file_idx < len(data_files):
                selected = data_files[file_idx]
                folder_name = "processed_data" if selected.startswith("processed_data") else "data"
                print(f"✅ Archivo seleccionado: {folder_name}/{os.path.basename(selected)}")
                return selected
            else:
                print(f"❌ Número inválido. Ingresa un número entre 1 y {len(data_files)}")
        except ValueError:
            print("❌ Por favor ingresa un número válido")
        except KeyboardInterrupt:
            print("\n❌ Operación cancelada")
            return None

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='🏟️ Analizador UWB Integrado para Fútbol Sala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python uwb_analyzer.py                              # Selección interactiva + guarda CSV procesado
  python uwb_analyzer.py data/mi_archivo.csv          # Archivo específico + guarda CSV procesado
  python uwb_analyzer.py --output results/            # Directorio de salida personalizado
  python uwb_analyzer.py --no-save-processed          # Solo análisis, sin guardar CSV procesado
        """
    )
    
    parser.add_argument('csv_file', nargs='?', 
                       help='Archivo CSV con datos UWB')
    parser.add_argument('--output', '-o', default='outputs',
                       help='Directorio de salida (default: outputs)')
    parser.add_argument('--data-dir', default='data',
                       help='Directorio de datos de entrada (default: data)')
    parser.add_argument('--no-save-processed', action='store_true',
                       help='No guardar archivo CSV con datos procesados')
    
    args = parser.parse_args()
    
    # Seleccionar archivo
    if args.csv_file:
        if not os.path.exists(args.csv_file):
            print(f"❌ Archivo no encontrado: {args.csv_file}")
            return
        selected_file = args.csv_file
    else:
        selected_file = select_directory_and_file()
        if selected_file is None:
            return
    
    try:
        # Crear analizador
        analyzer = UWBAnalyzer(data_dir=args.data_dir, output_dir=args.output)
        
        # Ejecutar análisis completo
        save_processed = not args.no_save_processed
        results = analyzer.run_complete_analysis(selected_file, save_processed=save_processed)
        
        if results:
            print("\n🎉 ¡Análisis completado exitosamente!")
            print(f"🔍 Revisa los resultados en: {args.output}/")
        
    except KeyboardInterrupt:
        print("\n👋 Análisis cancelado por el usuario")
    except Exception as e:
        print(f"❌ Error durante el análisis: {e}")

if __name__ == "__main__":
    main() 