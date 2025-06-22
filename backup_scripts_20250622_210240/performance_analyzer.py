#!/usr/bin/env python3
"""
Analizador Avanzado de Rendimiento Deportivo - TFG Fútbol Sala
==============================================================

Sistema completo de análisis de rendimiento para fútbol sala usando datos UWB.
Genera insights tácticos, métricas de rendimiento y comparaciones avanzadas.

Características:
- Análisis de zonas tácticas detalladas
- Métricas de sprint y resistencia
- Detección de patrones de movimiento
- Heatmaps de zona por tiempo
- Análisis de intensidad por período
- Comparación entre sesiones
- Exportación de reportes profesionales

Autor: TFG Sistema UWB Fútbol Sala
Versión: 1.0
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from datetime import datetime, timedelta
import os
import json
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde
import argparse
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class FutsalPerformanceAnalyzer:
    """Analizador profesional de rendimiento para fútbol sala"""
    
    def __init__(self):
        # Configuración de cancha de fútbol sala (40x20m)
        self.court = {
            'length': 40.0,
            'width': 20.0,
            'goal_area_length': 6.0,
            'center_circle_radius': 3.0,
            'penalty_spot_distance': 6.0
        }
        
        # Definición de zonas tácticas avanzadas
        self.tactical_zones = {
            'area_defensiva_propia': {
                'bounds': [0, 6, 0, 20],
                'description': 'Área defensiva propia (0-6m)',
                'tactical_importance': 'CRITICA'
            },
            'zona_defensiva': {
                'bounds': [0, 13.33, 0, 20],
                'description': 'Tercio defensivo (0-13.33m)',
                'tactical_importance': 'ALTA'
            },
            'zona_media_defensiva': {
                'bounds': [13.33, 20, 0, 20],
                'description': 'Zona media defensiva (13.33-20m)',
                'tactical_importance': 'MEDIA'
            },
            'circulo_central': {
                'bounds': [17, 23, 7, 13],
                'description': 'Círculo central',
                'tactical_importance': 'MEDIA'
            },
            'zona_media_ofensiva': {
                'bounds': [20, 26.67, 0, 20],
                'description': 'Zona media ofensiva (20-26.67m)',
                'tactical_importance': 'MEDIA'
            },
            'zona_ofensiva': {
                'bounds': [26.67, 40, 0, 20],
                'description': 'Tercio ofensivo (26.67-40m)',
                'tactical_importance': 'ALTA'
            },
            'area_ofensiva_rival': {
                'bounds': [34, 40, 0, 20],
                'description': 'Área ofensiva rival (34-40m)',
                'tactical_importance': 'CRITICA'
            },
            'banda_izquierda': {
                'bounds': [0, 40, 0, 6.67],
                'description': 'Banda izquierda',
                'tactical_importance': 'MEDIA'
            },
            'zona_central': {
                'bounds': [0, 40, 6.67, 13.33],
                'description': 'Zona central',
                'tactical_importance': 'ALTA'
            },
            'banda_derecha': {
                'bounds': [0, 40, 13.33, 20],
                'description': 'Banda derecha',
                'tactical_importance': 'MEDIA'
            }
        }
        
        # Umbrales de rendimiento (basados en estudios de fútbol sala)
        self.performance_thresholds = {
            'walking_speed': 1.5,      # m/s
            'jogging_speed': 3.0,      # m/s
            'running_speed': 5.0,      # m/s
            'sprinting_speed': 7.0,    # m/s
            'max_realistic_speed': 12.0, # m/s
            'high_intensity_threshold': 4.0, # m/s
            'sprint_duration_min': 2.0,     # segundos mínimos para considerar sprint
            'recovery_time_threshold': 10.0  # segundos de recuperación entre sprints
        }
        
        # Configuración de visualización
        plt.style.use('seaborn-v0_8-darkgrid')
        self.colors = {
            'walking': '#2E8B57',     # Verde mar
            'jogging': '#4169E1',     # Azul real
            'running': '#FF8C00',     # Naranja
            'sprinting': '#DC143C',   # Rojo carmesí
            'zone_low': '#90EE90',    # Verde claro
            'zone_medium': '#FFD700', # Dorado
            'zone_high': '#FF6347',   # Tomate
            'zone_critical': '#8B0000' # Rojo oscuro
        }

    def load_data(self, csv_file):
        """Cargar y validar datos de movimiento"""
        try:
            print(f"📊 Cargando datos: {os.path.basename(csv_file)}")
            
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Validar datos
            required_cols = ['timestamp', 'x', 'y']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Columnas faltantes: {missing_cols}")
            
            # Filtrar datos válidos dentro de la cancha + margen
            df = df[(df['x'] >= -5) & (df['x'] <= 45) & 
                   (df['y'] >= -5) & (df['y'] <= 25)]
            
            print(f"✅ Datos cargados: {len(df)} registros válidos")
            duration = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds()
            print(f"⏱️  Duración: {duration:.1f} segundos")
            
            return df
            
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return None

    def calculate_performance_metrics(self, df):
        """Calcular métricas completas de rendimiento"""
        print("🔬 Calculando métricas de rendimiento...")
        
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
        
        # Asignar zonas tácticas
        df['tactical_zone'] = df.apply(self._get_tactical_zone, axis=1)
        
        # Calcular intensidad normalizada (0-100)
        max_vel = df['velocity'].quantile(0.95)  # 95th percentile para evitar outliers
        df['intensity'] = np.clip((df['velocity'] / max_vel) * 100, 0, 100)
        
        return df

    def _get_tactical_zone(self, row):
        """Determinar zona táctica de una posición"""
        x, y = row['x'], row['y']
        
        for zone_name, zone_data in self.tactical_zones.items():
            x_min, x_max, y_min, y_max = zone_data['bounds']
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return zone_name
        
        return 'fuera_cancha'

    def analyze_sprint_episodes(self, df):
        """Analizar episodios de sprint detalladamente"""
        print("⚡ Analizando episodios de sprint...")
        
        # Identificar períodos de alta intensidad
        high_intensity = df['velocity'] >= self.performance_thresholds['high_intensity_threshold']
        
        # Encontrar inicios y finales de sprint
        sprint_starts = []
        sprint_ends = []
        
        in_sprint = False
        sprint_start_idx = None
        
        for i, is_high in enumerate(high_intensity):
            if is_high and not in_sprint:
                # Inicio de sprint
                in_sprint = True
                sprint_start_idx = i
            elif not is_high and in_sprint:
                # Final de sprint
                in_sprint = False
                sprint_duration = (df['timestamp'].iloc[i] - df['timestamp'].iloc[sprint_start_idx]).total_seconds()
                
                if sprint_duration >= self.performance_thresholds['sprint_duration_min']:
                    sprint_starts.append(sprint_start_idx)
                    sprint_ends.append(i)
        
        # Analizar cada episodio de sprint
        sprint_episodes = []
        for start_idx, end_idx in zip(sprint_starts, sprint_ends):
            episode = df.iloc[start_idx:end_idx+1]
            
            duration = (episode['timestamp'].iloc[-1] - episode['timestamp'].iloc[0]).total_seconds()
            max_speed = episode['velocity'].max()
            avg_speed = episode['velocity'].mean()
            distance = episode['distance'].sum()
            start_zone = episode['tactical_zone'].iloc[0]
            end_zone = episode['tactical_zone'].iloc[-1]
            
            sprint_episodes.append({
                'start_time': episode['timestamp'].iloc[0],
                'end_time': episode['timestamp'].iloc[-1],
                'duration': duration,
                'max_speed': max_speed,
                'avg_speed': avg_speed,
                'distance': distance,
                'start_zone': start_zone,
                'end_zone': end_zone,
                'start_x': episode['x'].iloc[0],
                'start_y': episode['y'].iloc[0],
                'end_x': episode['x'].iloc[-1],
                'end_y': episode['y'].iloc[-1]
            })
        
        print(f"📈 Detectados {len(sprint_episodes)} episodios de sprint")
        return sprint_episodes

    def analyze_zone_activity(self, df):
        """Análisis detallado de actividad por zonas"""
        print("🗺️  Analizando actividad por zonas tácticas...")
        
        zone_stats = defaultdict(lambda: {
            'time_spent': 0,
            'distance_covered': 0,
            'avg_intensity': 0,
            'max_speed': 0,
            'entries': 0,
            'tactical_importance': 'BAJA'
        })
        
        # Analizar cada zona
        for zone_name, zone_data in self.tactical_zones.items():
            zone_mask = df['tactical_zone'] == zone_name
            zone_df = df[zone_mask]
            
            if len(zone_df) > 0:
                time_spent = len(zone_df) * df['dt'].mean()  # Aproximación
                distance_covered = zone_df['distance'].sum()
                avg_intensity = zone_df['intensity'].mean()
                max_speed = zone_df['velocity'].max()
                
                # Contar entradas a la zona
                entries = 0
                prev_in_zone = False
                for in_zone in zone_mask:
                    if in_zone and not prev_in_zone:
                        entries += 1
                    prev_in_zone = in_zone
                
                zone_stats[zone_name] = {
                    'time_spent': time_spent,
                    'distance_covered': distance_covered,
                    'avg_intensity': avg_intensity,
                    'max_speed': max_speed,
                    'entries': entries,
                    'tactical_importance': zone_data['tactical_importance'],
                    'description': zone_data['description']
                }
        
        return dict(zone_stats)

    def generate_performance_report(self, df, sprint_episodes, zone_stats, output_file=None, 
                                   tactical_metrics=None, futsal_metrics=None):
        """Generar reporte completo de rendimiento"""
        print("📝 Generando reporte de rendimiento...")
        
        # Calcular estadísticas generales
        total_time = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
        total_distance = df['distance'].sum()
        avg_speed = df['velocity'].mean()
        max_speed = df['velocity'].max()
        avg_intensity = df['intensity'].mean()
        
        # Estadísticas por tipo de movimiento
        movement_stats = df.groupby('movement_type').agg({
            'distance': 'sum',
            'velocity': 'mean',
            'intensity': 'mean'
        }).round(2)
        
        # Tiempo en cada zona de velocidad
        movement_time = df.groupby('movement_type').size() * df['dt'].mean()
        movement_percentage = (movement_time / total_time * 100).round(1)
        
        # Crear reporte
        report = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    REPORTE DE RENDIMIENTO DEPORTIVO                   ║
║                        Sistema UWB Fútbol Sala                        ║
╠══════════════════════════════════════════════════════════════════════╣
║  📊 RESUMEN GENERAL                                                  ║
╚══════════════════════════════════════════════════════════════════════╝

⏱️  Duración total: {total_time:.1f} segundos ({total_time/60:.1f} minutos)
📏 Distancia total: {total_distance:.1f} metros
🏃 Velocidad promedio: {avg_speed:.2f} m/s
⚡ Velocidad máxima: {max_speed:.2f} m/s
🎯 Intensidad promedio: {avg_intensity:.1f}%

╔══════════════════════════════════════════════════════════════════════╗
║  🏃 ANÁLISIS POR TIPO DE MOVIMIENTO                                  ║
╚══════════════════════════════════════════════════════════════════════╝

"""
        for movement_type, stats in movement_stats.iterrows():
            time_pct = movement_percentage.get(movement_type, 0)
            distance = stats['distance']
            speed = stats['velocity']
            intensity = stats['intensity']
            
            report += f"🔸 {movement_type.upper():12} | "
            report += f"Tiempo: {time_pct:5.1f}% | "
            report += f"Distancia: {distance:6.1f}m | "
            report += f"Vel. media: {speed:5.2f} m/s | "
            report += f"Intensidad: {intensity:5.1f}%\n"

        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚡ ANÁLISIS DE SPRINTS                                              ║
╚══════════════════════════════════════════════════════════════════════╝

📈 Total de sprints: {len(sprint_episodes)}
"""
        
        if sprint_episodes:
            avg_sprint_duration = np.mean([ep['duration'] for ep in sprint_episodes])
            max_sprint_speed = max([ep['max_speed'] for ep in sprint_episodes])
            total_sprint_distance = sum([ep['distance'] for ep in sprint_episodes])
            
            report += f"⏱️  Duración promedio de sprint: {avg_sprint_duration:.1f} segundos\n"
            report += f"⚡ Velocidad máxima en sprint: {max_sprint_speed:.2f} m/s\n"
            report += f"📏 Distancia total en sprints: {total_sprint_distance:.1f} metros\n"
            
            # Top 3 sprints más intensos
            sorted_sprints = sorted(sprint_episodes, key=lambda x: x['max_speed'], reverse=True)[:3]
            report += f"\n🏆 TOP 3 SPRINTS MÁS INTENSOS:\n"
            for i, sprint in enumerate(sorted_sprints, 1):
                report += f"   {i}. {sprint['max_speed']:.2f} m/s durante {sprint['duration']:.1f}s "
                report += f"({sprint['start_zone']} → {sprint['end_zone']})\n"

        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  🗺️  ANÁLISIS POR ZONAS TÁCTICAS                                    ║
╚══════════════════════════════════════════════════════════════════════╝

"""
        
        # Ordenar zonas por importancia táctica y tiempo
        sorted_zones = sorted(zone_stats.items(), 
                            key=lambda x: (x[1]['tactical_importance'], x[1]['time_spent']), 
                            reverse=True)
        
        for zone_name, stats in sorted_zones:
            if stats['time_spent'] > 0:
                time_pct = (stats['time_spent'] / total_time * 100)
                report += f"🏟️  {stats['description']:<30} | "
                report += f"Tiempo: {time_pct:5.1f}% | "
                report += f"Dist: {stats['distance_covered']:6.1f}m | "
                report += f"Entradas: {stats['entries']:3d} | "
                report += f"Importancia: {stats['tactical_importance']}\n"

        # Agregar métricas tácticas si están disponibles
        if tactical_metrics:
            report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚔️  ANÁLISIS TÁCTICO AVANZADO                                       ║
╚══════════════════════════════════════════════════════════════════════╝

🔄 Transiciones defensivas: {tactical_metrics.get('defensive_transitions', 0)}
🔄 Transiciones ofensivas: {tactical_metrics.get('offensive_transitions', 0)}
⚡ Eficiencia movimiento: {tactical_metrics.get('movement_efficiency', 0):.2f}
🏃 Tiempo pressing: {tactical_metrics.get('pressing_time', 0):.1f} segundos

"""

        # Agregar métricas específicas de fútbol sala
        if futsal_metrics:
            report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  ⚽ MÉTRICAS ESPECÍFICAS FÚTBOL SALA                                  ║
╚══════════════════════════════════════════════════════════════════════╝

🎵 Cambios de ritmo: {futsal_metrics.get('rhythm_changes', 0)}
🗺️  Cobertura cancha: {futsal_metrics.get('court_coverage_pct', 0):.1f}%
⚡ Acciones explosivas: {futsal_metrics.get('explosive_actions', 0)}
⏱️  Tiempo recuperación promedio: {futsal_metrics.get('avg_recovery_time', 0):.1f}s

"""

        report += f"""
╔══════════════════════════════════════════════════════════════════════╗
║  💡 INSIGHTS Y RECOMENDACIONES                                       ║
╚══════════════════════════════════════════════════════════════════════╝

"""
        
        # Generar insights automáticos
        insights = self._generate_insights(df, sprint_episodes, zone_stats, total_time)
        for insight in insights:
            report += f"💡 {insight}\n"

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📁 Reporte guardado en: {output_file}")
        
        print(report)
        return report

    def _generate_insights(self, df, sprint_episodes, zone_stats, total_time):
        """Generar insights automáticos basados en los datos"""
        insights = []
        
        # Análisis de intensidad
        high_intensity_time = len(df[df['intensity'] >= 70]) * df['dt'].mean()
        high_intensity_pct = (high_intensity_time / total_time * 100)
        
        if high_intensity_pct > 25:
            insights.append("Alta intensidad de juego - excelente condición física mostrada")
        elif high_intensity_pct < 10:
            insights.append("Intensidad baja - considerar aumentar ritmo de entrenamiento")
        
        # Análisis de sprints
        if len(sprint_episodes) > 20:
            insights.append("Muchos sprints detectados - buen trabajo de alta intensidad")
        elif len(sprint_episodes) < 5:
            insights.append("Pocos sprints - incrementar trabajo anaeróbico")
        
        # Análisis de zonas
        offensive_time = sum(stats['time_spent'] for name, stats in zone_stats.items() 
                           if 'ofensiva' in name)
        defensive_time = sum(stats['time_spent'] for name, stats in zone_stats.items() 
                           if 'defensiva' in name)
        
        if offensive_time > defensive_time * 1.5:
            insights.append("Perfil ofensivo - más tiempo en zonas de ataque")
        elif defensive_time > offensive_time * 1.5:
            insights.append("Perfil defensivo - más tiempo en zonas de retroceso")
        else:
            insights.append("Perfil equilibrado - distribución uniforme por zonas")
        
        # Análisis de velocidad máxima
        max_speed = df['velocity'].max()
        if max_speed > 8.0:
            insights.append(f"Excelente velocidad máxima registrada: {max_speed:.1f} m/s")
        elif max_speed < 5.0:
            insights.append("Velocidad máxima baja - trabajar potencia y velocidad")
        
        return insights

    def create_advanced_visualizations(self, df, sprint_episodes, zone_stats, output_dir="plots"):
        """Crear visualizaciones avanzadas de rendimiento"""
        print("📈 Generando visualizaciones avanzadas...")
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Dashboard completo de rendimiento
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('DASHBOARD DE RENDIMIENTO DEPORTIVO - FÚTBOL SALA', 
                    fontsize=16, fontweight='bold')
        
        # Gráfico 1: Distribución de velocidades
        ax1 = axes[0, 0]
        ax1.hist(df['velocity'].dropna(), bins=50, alpha=0.7, color='skyblue', edgecolor='black')
        ax1.axvline(df['velocity'].mean(), color='red', linestyle='--', 
                   label=f'Media: {df["velocity"].mean():.1f} m/s')
        ax1.set_xlabel('Velocidad (m/s)')
        ax1.set_ylabel('Frecuencia')
        ax1.set_title('Distribución de Velocidades')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Gráfico 2: Intensidad a lo largo del tiempo
        ax2 = axes[0, 1]
        time_minutes = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds() / 60
        ax2.plot(time_minutes, df['intensity'], color='orange', alpha=0.7)
        ax2.fill_between(time_minutes, df['intensity'], alpha=0.3, color='orange')
        ax2.set_xlabel('Tiempo (minutos)')
        ax2.set_ylabel('Intensidad (%)')
        ax2.set_title('Intensidad vs Tiempo')
        ax2.grid(True, alpha=0.3)
        
        # Gráfico 3: Tiempo por tipo de movimiento
        ax3 = axes[0, 2]
        movement_counts = df['movement_type'].value_counts()
        colors = [self.colors.get(movement, 'gray') for movement in movement_counts.index]
        ax3.pie(movement_counts.values, labels=movement_counts.index, 
               autopct='%1.1f%%', colors=colors, startangle=90)
        ax3.set_title('Distribución Tipos de Movimiento')
        
        # Gráfico 4: Mapa de calor de posiciones
        ax4 = axes[1, 0]
        self._draw_court_background(ax4)
        # Crear heatmap de densidad
        if len(df) > 100:
            # Submuestrear para performance
            sample_df = df.sample(n=min(1000, len(df)))
            ax4.hexbin(sample_df['x'], sample_df['y'], gridsize=20, 
                      cmap='YlOrRd', alpha=0.7)
        ax4.set_title('Mapa de Calor de Posiciones')
        ax4.set_xlabel('X (metros)')
        ax4.set_ylabel('Y (metros)')
        
        # Gráfico 5: Velocidad por zona
        ax5 = axes[1, 1]
        zone_velocities = []
        zone_names = []
        for zone_name, stats in zone_stats.items():
            if stats['time_spent'] > 0:
                zone_df = df[df['tactical_zone'] == zone_name]
                if len(zone_df) > 0:
                    zone_velocities.append(zone_df['velocity'].values)
                    zone_names.append(zone_name.replace('_', '\n'))
        
        if zone_velocities:
            ax5.boxplot(zone_velocities, labels=zone_names)
            ax5.set_ylabel('Velocidad (m/s)')
            ax5.set_title('Velocidad por Zona Táctica')
            ax5.tick_params(axis='x', rotation=45)
        
        # Gráfico 6: Sprints en el tiempo
        ax6 = axes[1, 2]
        if sprint_episodes:
            sprint_times = [(ep['start_time'] - df['timestamp'].iloc[0]).total_seconds() / 60 
                          for ep in sprint_episodes]
            sprint_speeds = [ep['max_speed'] for ep in sprint_episodes]
            ax6.scatter(sprint_times, sprint_speeds, alpha=0.7, s=60, color='red')
            ax6.set_xlabel('Tiempo (minutos)')
            ax6.set_ylabel('Velocidad Sprint (m/s)')
            ax6.set_title('Episodios de Sprint')
            ax6.grid(True, alpha=0.3)
        
        plt.tight_layout()
        dashboard_file = os.path.join(output_dir, f"performance_dashboard_{timestamp}.png")
        plt.savefig(dashboard_file, dpi=300, bbox_inches='tight')
        print(f"📊 Dashboard guardado: {dashboard_file}")
        
        # 2. Mapa táctico con sprints
        self._create_tactical_sprint_map(df, sprint_episodes, output_dir, timestamp)
        
        plt.show()
        return dashboard_file

    def _draw_court_background(self, ax):
        """Dibujar fondo de cancha de fútbol sala simplificado"""
        # Perímetro
        ax.add_patch(patches.Rectangle((0, 0), 40, 20, fill=False, edgecolor='white', linewidth=2))
        
        # Línea central
        ax.axvline(x=20, color='white', linewidth=1)
        
        # Círculo central
        circle = patches.Circle((20, 10), 3, fill=False, edgecolor='white', linewidth=1)
        ax.add_patch(circle)
        
        # Áreas de portería
        ax.add_patch(patches.Rectangle((0, 4), 6, 12, fill=False, edgecolor='white', linewidth=1))
        ax.add_patch(patches.Rectangle((34, 4), 6, 12, fill=False, edgecolor='white', linewidth=1))
        
        ax.set_xlim(-2, 42)
        ax.set_ylim(-2, 22)
        ax.set_aspect('equal')
        ax.set_facecolor('#2d5016')  # Verde cancha

    def _create_tactical_sprint_map(self, df, sprint_episodes, output_dir, timestamp):
        """Crear mapa táctico con sprints destacados"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Dibujar cancha
        self._draw_court_background(ax)
        
        # Trayectoria general (suavizada)
        if len(df) > 1000:
            step = len(df) // 1000
            plot_df = df.iloc[::step]
        else:
            plot_df = df
            
        ax.plot(plot_df['x'], plot_df['y'], 'lightblue', alpha=0.5, linewidth=1, 
               label='Trayectoria general')
        
        # Destacar sprints
        colors_sprint = ['red', 'orange', 'yellow', 'purple', 'pink']
        for i, episode in enumerate(sprint_episodes[:5]):  # Top 5 sprints
            start_time = episode['start_time']
            end_time = episode['end_time']
            
            sprint_df = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]
            
            color = colors_sprint[i % len(colors_sprint)]
            ax.plot(sprint_df['x'], sprint_df['y'], color=color, linewidth=4, alpha=0.8,
                   label=f'Sprint {i+1}: {episode["max_speed"]:.1f} m/s')
            
            # Marcar inicio y fin
            ax.plot(episode['start_x'], episode['start_y'], 'go', markersize=10)
            ax.plot(episode['end_x'], episode['end_y'], 'ro', markersize=10)
        
        ax.set_title('MAPA TÁCTICO CON EPISODIOS DE SPRINT', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
        
        plt.tight_layout()
        tactical_file = os.path.join(output_dir, f"tactical_sprint_map_{timestamp}.png")
        plt.savefig(tactical_file, dpi=300, bbox_inches='tight')
        print(f"🗺️  Mapa táctico guardado: {tactical_file}")

    def analyze_tactical_efficiency(self, df):
        """Analizar eficiencia táctica específica para fútbol sala"""
        print("⚔️ Analizando eficiencia táctica...")
        
        tactical_metrics = {}
        
        # 1. Análisis de transiciones defensiva-ofensiva
        zone_changes = []
        prev_zone = None
        
        for _, row in df.iterrows():
            current_zone = row['tactical_zone']
            if prev_zone and prev_zone != current_zone:
                if 'defensiva' in prev_zone and 'ofensiva' in current_zone:
                    zone_changes.append('def_to_off')
                elif 'ofensiva' in prev_zone and 'defensiva' in current_zone:
                    zone_changes.append('off_to_def')
            prev_zone = current_zone
        
        tactical_metrics['defensive_transitions'] = zone_changes.count('off_to_def')
        tactical_metrics['offensive_transitions'] = zone_changes.count('def_to_off')
        
        # 2. Tiempo de permanencia en zonas críticas
        critical_zones = ['area_defensiva_propia', 'area_ofensiva_rival']
        for zone in critical_zones:
            zone_time = len(df[df['tactical_zone'] == zone]) * df['dt'].mean()
            tactical_metrics[f'time_in_{zone}'] = zone_time
        
        # 3. Eficiencia de movimiento (distancia vs progreso)
        start_x = df['x'].iloc[0]
        end_x = df['x'].iloc[-1]
        net_progress = abs(end_x - start_x)
        total_distance = df['distance'].sum()
        
        tactical_metrics['movement_efficiency'] = net_progress / total_distance if total_distance > 0 else 0
        
        # 4. Análisis de pressing (tiempo en zona rival con alta velocidad)
        pressing_situations = df[
            (df['tactical_zone'].str.contains('ofensiva', na=False)) & 
            (df['velocity'] > 3.0)
        ]
        tactical_metrics['pressing_time'] = len(pressing_situations) * df['dt'].mean()
        
        return tactical_metrics

    def calculate_futsal_specific_metrics(self, df):
        """Calcular métricas específicas del fútbol sala profesional"""
        print("⚽ Calculando métricas específicas de fútbol sala...")
        
        futsal_metrics = {}
        
        # 1. Análisis de ritmo de juego (cambios de velocidad)
        velocity_changes = abs(df['velocity'].diff())
        futsal_metrics['rhythm_changes'] = len(velocity_changes[velocity_changes > 2.0])
        
        # 2. Cobertura de cancha (% de área cubierta)
        x_range = df['x'].max() - df['x'].min()
        y_range = df['y'].max() - df['y'].min()
        court_coverage = (x_range / 40.0) * (y_range / 20.0) * 100
        futsal_metrics['court_coverage_pct'] = min(100, court_coverage)
        
        # 3. Densidad de actividad por zona
        for zone_name in self.tactical_zones.keys():
            zone_df = df[df['tactical_zone'] == zone_name]
            if len(zone_df) > 0:
                zone_density = len(zone_df) / len(df) * 100
                futsal_metrics[f'density_{zone_name}'] = zone_density
        
        # 4. Análisis de recuperación (tiempo entre esfuerzos intensos)
        high_intensity_moments = df[df['velocity'] > 4.0].index
        if len(high_intensity_moments) > 1:
            recovery_times = np.diff(high_intensity_moments) * df['dt'].mean()
            futsal_metrics['avg_recovery_time'] = np.mean(recovery_times)
            futsal_metrics['min_recovery_time'] = np.min(recovery_times)
        else:
            futsal_metrics['avg_recovery_time'] = 0
            futsal_metrics['min_recovery_time'] = 0
        
        # 5. Índice de explosividad (aceleraciones bruscas)
        accelerations = abs(df['acceleration'].fillna(0))
        explosive_moments = len(accelerations[accelerations > 3.0])  # m/s²
        futsal_metrics['explosive_actions'] = explosive_moments
        
        return futsal_metrics

def select_analysis_file():
    """Selección interactiva de archivo para análisis"""
    import glob
    
    # Buscar archivos procesados primero
    processed_files = glob.glob("processed_data/*.csv")
    data_files = glob.glob("data/*.csv")
    
    all_files = processed_files + data_files
    
    if not all_files:
        print("❌ No se encontraron archivos CSV")
        return None
    
    print("\n📊 SELECCIONAR ARCHIVO PARA ANÁLISIS DE RENDIMIENTO:")
    print("=" * 60)
    
    for i, file_path in enumerate(all_files, 1):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024
        folder = "📊 processed/" if file_path.startswith("processed_data/") else "📁 data/"
        status = "✅ RECOMENDADO" if file_path.startswith("processed_data/") else "⚠️  RAW"
        
        print(f"{i:2d}. {folder}{file_name:<35} | {file_size:6.1f}KB | {status}")
    
    while True:
        try:
            choice = input(f"\n👆 Selecciona archivo (1-{len(all_files)}): ").strip()
            file_idx = int(choice) - 1
            
            if 0 <= file_idx < len(all_files):
                return all_files[file_idx]
            else:
                print(f"⚠️  Número inválido. Usa 1-{len(all_files)}")
                
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Operación cancelada")
            return None

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Analizador Avanzado de Rendimiento para Fútbol Sala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python performance_analyzer.py                           # Selección interactiva
  python performance_analyzer.py processed_data/file.csv  # Archivo específico
  python performance_analyzer.py --output-dir reports/    # Directorio personalizado
        """
    )
    
    parser.add_argument('csv_file', nargs='?',
                       help='Archivo CSV con datos de movimiento')
    parser.add_argument('--output-dir', default='reports',
                       help='Directorio de salida para reportes')
    parser.add_argument('--no-visualizations', action='store_true',
                       help='Solo generar reporte de texto')
    
    args = parser.parse_args()
    
    # Selección de archivo
    if args.csv_file:
        if not os.path.exists(args.csv_file):
            print(f"❌ Error: Archivo no encontrado '{args.csv_file}'")
            return
        selected_file = args.csv_file
    else:
        selected_file = select_analysis_file()
        if selected_file is None:
            return
    
    print("🚀 ANALIZADOR AVANZADO DE RENDIMIENTO DEPORTIVO")
    print("=" * 55)
    
    # Crear analizador
    analyzer = FutsalPerformanceAnalyzer()
    
    # Cargar y procesar datos
    df = analyzer.load_data(selected_file)
    if df is None:
        return
    
    df = analyzer.calculate_performance_metrics(df)
    sprint_episodes = analyzer.analyze_sprint_episodes(df)
    zone_stats = analyzer.analyze_zone_activity(df)
    
    # Nuevos análisis avanzados
    tactical_metrics = analyzer.analyze_tactical_efficiency(df)
    futsal_metrics = analyzer.calculate_futsal_specific_metrics(df)
    
    # Generar reporte
    os.makedirs(args.output_dir, exist_ok=True)
    report_file = os.path.join(args.output_dir, 
                              f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    analyzer.generate_performance_report(df, sprint_episodes, zone_stats, report_file, 
                                        tactical_metrics, futsal_metrics)
    
    # Generar visualizaciones
    if not args.no_visualizations:
        analyzer.create_advanced_visualizations(df, sprint_episodes, zone_stats, args.output_dir)
    
    print(f"\n✅ Análisis completado. Archivos guardados en: {args.output_dir}")

if __name__ == "__main__":
    main() 