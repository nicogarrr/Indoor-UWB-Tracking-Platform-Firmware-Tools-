#!/usr/bin/env python3
"""
TFG - Sistema GPS Indoor para Fútbol Sala
Sistema de Replay de Movimientos
Autor: TFG UWB System
Versión: 1.0

Reproduce los movimientos del tag usando datos CSV procesados:
- Replay en tiempo real con velocidad ajustable
- Visualización interactiva de la trayectoria
- Análisis de zonas y eventos deportivos
- Exportación a video/GIF
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, Circle
import argparse
import os
import glob
import time
from datetime import datetime, timedelta
import json

class MovementReplay:
    def __init__(self, data_dir="./processed_data", session_id=None):
        self.data_dir = data_dir
        self.session_id = session_id
        
        # Configuración de cancha
        self.court_length = 40.0  # metros
        self.court_width = 20.0   # metros
        
        # Configuración de zonas de fútbol sala
        self.zones = [
            {'name': 'Area_Porteria_1', 'x': 2.0, 'y': 4.0, 'radius': 3.0, 'color': 'red'},
            {'name': 'Area_Porteria_2', 'x': 38.0, 'y': 4.0, 'radius': 3.0, 'color': 'red'},
            {'name': 'Centro_Campo', 'x': 20.0, 'y': 10.0, 'radius': 3.0, 'color': 'blue'},
            {'name': 'Medio_Campo_1', 'x': 10.0, 'y': 10.0, 'radius': 5.0, 'color': 'green'},
            {'name': 'Medio_Campo_2', 'x': 30.0, 'y': 10.0, 'radius': 5.0, 'color': 'green'},
            {'name': 'Banda_Lateral', 'x': 20.0, 'y': 2.0, 'radius': 8.0, 'color': 'orange'}
        ]
        
        # Posiciones de anclas optimizadas
        self.anchor_positions = {
            10: (-1, -1),     # Esquina SW (fuera cancha)
            20: (-1, 21),     # Esquina NW (fuera cancha)
            30: (41, -1),     # Esquina SE (fuera cancha)
            40: (41, 21),     # Esquina NE (fuera cancha)
            50: (20, 25)      # Lateral Norte (fuera cancha)
        }
        
        # Estado del replay
        self.position_data = None
        self.zones_data = None
        self.current_frame = 0
        self.playing = False
        self.speed_multiplier = 1.0
        
        print(f"🎬 TFG UWB Movement Replay")
        print(f"📂 Directorio de datos: {data_dir}")
        if session_id:
            print(f"📅 Sesión: {session_id}")
        print("=" * 50)
    
    def find_latest_session(self):
        """Encontrar la sesión más reciente automáticamente"""
        session_dirs = glob.glob(os.path.join(self.data_dir, "session_*"))
        if not session_dirs:
            raise FileNotFoundError("No se encontraron sesiones procesadas")
        
        # Extraer timestamp del directorio más reciente
        latest_dir = max(session_dirs)
        session_id = os.path.basename(latest_dir).replace("session_", "")
        
        return session_id
    
    def load_session_data(self, session_id=None):
        """Cargar datos de una sesión procesada"""
        if session_id is None:
            session_id = self.find_latest_session()
            print(f"📅 Usando sesión más reciente: {session_id}")
        
        self.session_id = session_id
        session_dir = os.path.join(self.data_dir, f"session_{session_id}")
        
        # Cargar datos de posición (preferir interpolados si existen)
        position_files = [
            "position_interpolated_cleaned.csv",
            "position_cleaned.csv"
        ]
        
        position_data = None
        for filename in position_files:
            filepath = os.path.join(session_dir, filename)
            if os.path.exists(filepath):
                position_data = pd.read_csv(filepath)
                print(f"✅ Cargados datos de posición: {filename} ({len(position_data)} puntos)")
                break
        
        if position_data is None or position_data.empty:
            raise FileNotFoundError("No se encontraron datos de posición procesados")
        
        # Cargar datos de zonas si existen
        zones_file = os.path.join(session_dir, "zones_cleaned.csv")
        zones_data = None
        if os.path.exists(zones_file):
            zones_data = pd.read_csv(zones_file)
            print(f"✅ Cargados datos de zonas: {len(zones_data)} eventos")
        else:
            print("⚠️  No se encontraron datos de zonas")
            zones_data = pd.DataFrame()
        
        # Ordenar por timestamp
        position_data = position_data.sort_values('timestamp_system').reset_index(drop=True)
        if not zones_data.empty:
            zones_data = zones_data.sort_values('timestamp_system').reset_index(drop=True)
        
        # Convertir timestamps a tiempo relativo
        start_time = position_data['timestamp_system'].min()
        position_data['time_relative'] = position_data['timestamp_system'] - start_time
        if not zones_data.empty:
            zones_data['time_relative'] = zones_data['timestamp_system'] - start_time
        
        self.position_data = position_data
        self.zones_data = zones_data
        
        # Estadísticas del dataset
        duration = position_data['time_relative'].max()
        avg_speed = position_data['speed_ms'].mean() if 'speed_ms' in position_data.columns else 0
        max_speed = position_data['speed_ms'].max() if 'speed_ms' in position_data.columns else 0
        
        print(f"📊 Dataset cargado:")
        print(f"   ⏱️  Duración: {duration:.1f}s")
        print(f"   🏃 Velocidad promedio: {avg_speed:.2f} m/s")
        print(f"   🚀 Velocidad máxima: {max_speed:.2f} m/s")
        
        return position_data, zones_data
    
    def setup_plot(self):
        """Configurar la visualización matplotlib"""
        plt.style.use('dark_background')
        
        self.fig, self.ax = plt.subplots(figsize=(16, 9))
        self.ax.set_facecolor('#0a0a0a')
        
        # Dibujar cancha de fútbol sala
        court = Rectangle((0, 0), self.court_length, self.court_width, 
                         fill=False, edgecolor='white', linewidth=3)
        self.ax.add_patch(court)
        
        # Línea central
        self.ax.axvline(x=self.court_length/2, color='white', linewidth=2, alpha=0.7)
        
        # Círculo central
        central_circle = Circle((self.court_length/2, self.court_width/2), 3, 
                               fill=False, edgecolor='white', linewidth=2, alpha=0.7)
        self.ax.add_patch(central_circle)
        
        # Áreas de portería
        goal_area_1 = Rectangle((0, self.court_width/2 - 3), 6, 6,
                               fill=False, edgecolor='white', linewidth=2, alpha=0.7)
        goal_area_2 = Rectangle((self.court_length - 6, self.court_width/2 - 3), 6, 6,
                               fill=False, edgecolor='white', linewidth=2, alpha=0.7)
        self.ax.add_patch(goal_area_1)
        self.ax.add_patch(goal_area_2)
        
        # Dibujar zonas de análisis
        for zone in self.zones:
            zone_circle = Circle((zone['x'], zone['y']), zone['radius'],
                               fill=False, edgecolor=zone['color'], 
                               linewidth=1, alpha=0.3, linestyle='--')
            self.ax.add_patch(zone_circle)
            self.ax.text(zone['x'], zone['y'], zone['name'], 
                        ha='center', va='center', fontsize=8, 
                        color=zone['color'], alpha=0.7)
        
        # Dibujar anclas
        for anchor_id, (x, y) in self.anchor_positions.items():
            self.ax.scatter(x, y, c='yellow', s=100, marker='s', 
                           edgecolor='black', linewidth=1, alpha=0.8, zorder=10)
            self.ax.text(x, y-1.5, f'A{anchor_id}', ha='center', va='top', 
                        fontsize=10, color='yellow', weight='bold')
        
        # Configurar límites y aspecto
        margin = 3
        self.ax.set_xlim(-margin, self.court_length + margin)
        self.ax.set_ylim(-margin, self.court_width + margin)
        self.ax.set_aspect('equal')
        
        # Etiquetas y título
        self.ax.set_xlabel('X (metros)', color='white', fontsize=12)
        self.ax.set_ylabel('Y (metros)', color='white', fontsize=12)
        self.ax.set_title(f'TFG UWB - Replay de Movimiento - Sesión {self.session_id}', 
                         color='white', fontsize=14, weight='bold')
        
        # Grid
        self.ax.grid(True, alpha=0.2, color='white')
        
        # Elementos dinámicos del plot
        self.trail_line, = self.ax.plot([], [], 'cyan', alpha=0.6, linewidth=2, label='Trayectoria')
        self.current_pos = self.ax.scatter([], [], c='red', s=200, marker='o', 
                                          edgecolor='white', linewidth=2, zorder=20, 
                                          label='Posición actual')
        
        # Panel de información
        info_text = (f"Sesión: {self.session_id}\n"
                    f"Puntos: {len(self.position_data)}\n"
                    f"Duración: {self.position_data['time_relative'].max():.1f}s")
        
        self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes,
                    verticalalignment='top', bbox=dict(boxstyle='round', 
                    facecolor='black', alpha=0.8), color='white', fontsize=10)
        
        # Panel de controles
        controls_text = ("Controles:\n"
                        "SPACE: Play/Pause\n"
                        "← →: Frame anterior/siguiente\n"
                        "↑ ↓: Velocidad +/-\n"
                        "R: Reiniciar\n"
                        "Q: Salir")
        
        self.ax.text(0.98, 0.98, controls_text, transform=self.ax.transAxes,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='black', alpha=0.8), 
                    color='white', fontsize=9)
        
        # Panel de estado dinámico
        self.status_text = self.ax.text(0.02, 0.02, '', transform=self.ax.transAxes,
                                       verticalalignment='bottom',
                                       bbox=dict(boxstyle='round', facecolor='navy', alpha=0.8),
                                       color='white', fontsize=11, weight='bold')
        
        self.ax.legend(loc='upper left', bbox_to_anchor=(0.02, 0.75), 
                      framealpha=0.8, facecolor='black')
        
        # Configurar eventos de teclado
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        plt.tight_layout()
    
    def update_frame(self, frame_idx=None):
        """Actualizar la visualización para un frame específico"""
        if frame_idx is None:
            frame_idx = self.current_frame
        
        if frame_idx >= len(self.position_data):
            return
        
        # Datos del frame actual
        current_data = self.position_data.iloc[frame_idx]
        current_time = current_data['time_relative']
        
        # Usar posición suavizada si está disponible
        if 'position_x_m_smooth' in self.position_data.columns:
            x, y = current_data['position_x_m_smooth'], current_data['position_y_m_smooth']
        else:
            x, y = current_data['position_x_m'], current_data['position_y_m']
        
        # Actualizar posición actual
        self.current_pos.set_offsets([[x, y]])
        
        # Actualizar trayectoria (últimos N puntos)
        trail_length = min(100, frame_idx + 1)
        trail_start = max(0, frame_idx - trail_length + 1)
        
        if 'position_x_m_smooth' in self.position_data.columns:
            trail_x = self.position_data['position_x_m_smooth'].iloc[trail_start:frame_idx+1]
            trail_y = self.position_data['position_y_m_smooth'].iloc[trail_start:frame_idx+1]
        else:
            trail_x = self.position_data['position_x_m'].iloc[trail_start:frame_idx+1]
            trail_y = self.position_data['position_y_m'].iloc[trail_start:frame_idx+1]
        
        self.trail_line.set_data(trail_x, trail_y)
        
        # Actualizar panel de estado
        speed_text = f"{current_data.get('speed_ms', 0):.2f} m/s" if 'speed_ms' in current_data else "N/A"
        
        # Verificar zona actual
        current_zone = "Fuera de zonas"
        for zone in self.zones:
            dist = np.sqrt((x - zone['x'])**2 + (y - zone['y'])**2)
            if dist <= zone['radius']:
                current_zone = zone['name']
                break
        
        status_info = (f"Frame: {frame_idx + 1}/{len(self.position_data)}\n"
                      f"Tiempo: {current_time:.2f}s\n"
                      f"Posición: ({x:.1f}, {y:.1f})\n"
                      f"Velocidad: {speed_text}\n"
                      f"Zona: {current_zone}\n"
                      f"Velocidad replay: {self.speed_multiplier:.1f}x")
        
        self.status_text.set_text(status_info)
        
        # Actualizar título con progreso
        progress = (frame_idx + 1) / len(self.position_data) * 100
        title = f'TFG UWB - Replay de Movimiento - Sesión {self.session_id} ({progress:.1f}%)'
        self.ax.set_title(title, color='white', fontsize=14, weight='bold')
        
        self.fig.canvas.draw()
    
    def on_key_press(self, event):
        """Manejar eventos de teclado"""
        if event.key == ' ':  # Space: Play/Pause
            self.playing = not self.playing
            print(f"{'▶️ Reproduciendo' if self.playing else '⏸️ Pausado'}")
            
        elif event.key == 'left':  # Flecha izquierda: Frame anterior
            self.current_frame = max(0, self.current_frame - 1)
            self.update_frame()
            
        elif event.key == 'right':  # Flecha derecha: Frame siguiente
            self.current_frame = min(len(self.position_data) - 1, self.current_frame + 1)
            self.update_frame()
            
        elif event.key == 'up':  # Flecha arriba: Aumentar velocidad
            self.speed_multiplier = min(10.0, self.speed_multiplier * 1.5)
            print(f"🔄 Velocidad: {self.speed_multiplier:.1f}x")
            
        elif event.key == 'down':  # Flecha abajo: Disminuir velocidad
            self.speed_multiplier = max(0.1, self.speed_multiplier / 1.5)
            print(f"🔄 Velocidad: {self.speed_multiplier:.1f}x")
            
        elif event.key == 'r':  # R: Reiniciar
            self.current_frame = 0
            self.update_frame()
            print("🔄 Reiniciado")
            
        elif event.key == 'q':  # Q: Salir
            plt.close()
            print("👋 Saliendo del replay")
    
    def run_interactive_replay(self):
        """Ejecutar replay interactivo en tiempo real"""
        if self.position_data is None:
            raise ValueError("No hay datos cargados. Ejecutar load_session_data() primero.")
        
        self.setup_plot()
        self.update_frame(0)
        
        print("\n🎮 Controles del replay:")
        print("   SPACE: Play/Pause")
        print("   ← →: Frame anterior/siguiente")
        print("   ↑ ↓: Aumentar/disminuir velocidad")
        print("   R: Reiniciar")
        print("   Q: Salir")
        print("\n▶️ Presiona SPACE para comenzar")
        
        # Loop principal
        try:
            plt.show(block=False)
            
            while plt.get_fignums():  # Mientras la ventana esté abierta
                if self.playing and self.current_frame < len(self.position_data) - 1:
                    self.current_frame += 1
                    self.update_frame()
                    
                    # Calcular delay basado en datos reales y velocidad de replay
                    if self.current_frame < len(self.position_data) - 1:
                        current_time = self.position_data.iloc[self.current_frame]['time_relative']
                        next_time = self.position_data.iloc[self.current_frame + 1]['time_relative']
                        real_interval = next_time - current_time
                        sleep_time = real_interval / self.speed_multiplier
                        time.sleep(max(0.01, sleep_time))  # Mínimo 10ms
                    
                elif self.playing and self.current_frame >= len(self.position_data) - 1:
                    # Fin del replay
                    self.playing = False
                    print("🏁 Fin del replay")
                
                plt.pause(0.001)  # Permitir procesamiento de eventos
                
        except KeyboardInterrupt:
            print("\n⏹️ Replay interrumpido por el usuario")
        finally:
            plt.close()
    
    def generate_movement_report(self, output_file=None):
        """Generar reporte detallado del movimiento"""
        if self.position_data is None:
            raise ValueError("No hay datos cargados")
        
        if output_file is None:
            output_file = f"movement_report_{self.session_id}.txt"
        
        with open(output_file, 'w') as f:
            f.write(f"TFG UWB - Reporte de Movimiento\n")
            f.write(f"Sesión: {self.session_id}\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            # Estadísticas generales
            duration = self.position_data['time_relative'].max()
            distance_traveled = 0
            
            # Calcular distancia total recorrida
            for i in range(1, len(self.position_data)):
                x1, y1 = self.position_data.iloc[i-1][['position_x_m', 'position_y_m']]
                x2, y2 = self.position_data.iloc[i][['position_x_m', 'position_y_m']]
                distance_traveled += np.sqrt((x2-x1)**2 + (y2-y1)**2)
            
            avg_speed = self.position_data['speed_ms'].mean() if 'speed_ms' in self.position_data.columns else 0
            max_speed = self.position_data['speed_ms'].max() if 'speed_ms' in self.position_data.columns else 0
            
            f.write("ESTADÍSTICAS GENERALES:\n")
            f.write(f"  Duración: {duration:.2f} segundos\n")
            f.write(f"  Distancia recorrida: {distance_traveled:.2f} metros\n")
            f.write(f"  Velocidad promedio: {avg_speed:.2f} m/s\n")
            f.write(f"  Velocidad máxima: {max_speed:.2f} m/s\n")
            f.write(f"  Puntos de datos: {len(self.position_data)}\n")
            f.write(f"  Frecuencia promedio: {len(self.position_data)/duration:.1f} Hz\n\n")
            
            # Análisis de zonas
            if not self.zones_data.empty:
                f.write("EVENTOS DE ZONAS:\n")
                for _, event in self.zones_data.iterrows():
                    f.write(f"  {event['time_relative']:.2f}s - {event['zone_name']}: {event['action']}\n")
                f.write("\n")
        
        print(f"📄 Reporte generado: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TFG UWB - Replay de Movimientos")
    parser.add_argument("--data-dir", default="./processed_data",
                        help="Directorio con datos procesados")
    parser.add_argument("--session-id", default=None,
                        help="ID de sesión específica")
    parser.add_argument("--report-only", action="store_true",
                        help="Solo generar reporte, no mostrar replay")
    
    args = parser.parse_args()
    
    try:
        # Crear reproductor
        replay = MovementReplay(data_dir=args.data_dir, session_id=args.session_id)
        
        # Cargar datos
        replay.load_session_data(args.session_id)
        
        # Generar reporte
        replay.generate_movement_report()
        
        if not args.report_only:
            # Mostrar replay interactivo
            replay.run_interactive_replay()
        
    except Exception as e:
        print(f"❌ Error en el replay: {e}")
        raise 