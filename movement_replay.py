#!/usr/bin/env python3
"""
Sistema Avanzado de Replay UWB para Fútbol Sala
Reproductor interactivo en tiempo real de datos de movimiento
Con filtros avanzados, predicción ML y suavizado de trayectorias
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
import argparse
import sys
from datetime import datetime, timedelta
import time
from scipy.interpolate import CubicSpline, interp1d
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, Matern
import warnings

class KalmanPositionFilter:
    """
    Implementación del Filtro de Kalman para suavizar posiciones 2D.
    Reduce el ruido en las posiciones calculadas para movimientos más naturales.
    """
    def __init__(self, initial_pos=None, process_noise=0.01, measurement_noise=0.1):
        # Dimensiones: estado = 4 (x, y, vx, vy), medición = 2 (x, y)
        self.state = np.zeros(4)  # [x, y, vx, vy]
        if initial_pos is not None:
            self.state[:2] = initial_pos
            
        # Matriz de covarianza (incertidumbre inicial alta)
        self.P = np.eye(4) * 1000
        
        # Ruido del proceso (incertidumbre en la predicción)
        self.Q = np.eye(4) * process_noise
        
        # Ruido de medición (incertidumbre en las mediciones)
        self.R = np.eye(2) * measurement_noise
        
        # Matriz de transición (modelo de movimiento lineal)
        self.F = np.eye(4)
        
        # Matriz de medición (observamos solo x,y)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]])
        
        self.initialized = False
        
    def predict(self, dt):
        """Predice el siguiente estado basado en el modelo de movimiento."""
        # Actualizar matriz de transición con dt
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        # Predicción del estado: x = F·x
        self.state = self.F @ self.state
        
        # Actualizar covarianza: P = F·P·F^T + Q
        self.P = self.F @ self.P @ self.F.T + self.Q
        
    def update(self, measurement):
        """Actualiza el estado con una nueva medición."""
        # Innovación (diferencia entre medición predicha y actual)
        y = measurement - self.H @ self.state
        
        # Covarianza de la innovación
        S = self.H @ self.P @ self.H.T + self.R
        
        # Ganancia de Kalman
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Actualizar estado
        self.state = self.state + K @ y
        
        # Actualizar covarianza
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P
        
    def process(self, position, dt=0.02):
        """Procesa una nueva posición, devolviendo la posición filtrada."""
        # Si la posición es NaN, solo predecir sin actualizar
        if np.isnan(position[0]) or np.isnan(position[1]):
            if self.initialized:
                self.predict(dt)
                return self.state[:2]
            else:
                return position
        
        if not self.initialized:
            # Primera medición válida: inicializar
            self.state[:2] = position
            self.initialized = True
            return position
        
        # Realizar predicción
        self.predict(dt)
        
        # Actualizar con medición
        self.update(position)
        
        # Devolver posición filtrada
        return self.state[:2]

class TrajectoryPredictor:
    """
    Predicción de trayectorias usando Gaussian Process Regression (GPR)
    optimizado para movimientos de fútbol sala.
    """
    def __init__(self, context="futsal"):
        self.context = context
        self.x_model = None
        self.y_model = None
        self.min_samples_required = 5
        self.is_trained = False
        self.min_ts = 0
        self.max_ts = 0
        
        # Kernel optimizado para fútbol sala
        length_scale_bounds = (1e-3, 25.0)
        noise_level_bounds = (1e-8, 1.0)
        
        self.kernel_x = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                       WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
        
        self.kernel_y = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                       WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
    
    def train(self, timestamps, positions):
        """Entrena los modelos GPR usando datos históricos."""
        if len(timestamps) < self.min_samples_required:
            self.is_trained = False
            return False
        
        # Filtrar posiciones válidas
        valid_indices = ~np.isnan(positions[:, 0])
        valid_timestamps = timestamps[valid_indices]
        valid_positions = positions[valid_indices]
        
        if len(valid_timestamps) < self.min_samples_required:
            self.is_trained = False
            return False
        
        # Normalizar timestamps
        self.min_ts = min(valid_timestamps)
        self.max_ts = max(valid_timestamps)
        ts_range = self.max_ts - self.min_ts
        
        if ts_range <= 0:
            self.is_trained = False
            return False
        
        norm_timestamps = (valid_timestamps - self.min_ts) / ts_range
        norm_timestamps = norm_timestamps.reshape(-1, 1)
        
        try:
            self.x_model = GaussianProcessRegressor(
                kernel=self.kernel_x, 
                alpha=1e-5,
                normalize_y=True, 
                n_restarts_optimizer=1
            )
            
            self.y_model = GaussianProcessRegressor(
                kernel=self.kernel_y, 
                alpha=1e-5,
                normalize_y=True, 
                n_restarts_optimizer=1
            )
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.x_model.fit(norm_timestamps, valid_positions[:, 0])
                self.y_model.fit(norm_timestamps, valid_positions[:, 1])
                
            self.is_trained = True
            return True
            
        except Exception as e:
            print(f"⚠️ Error en entrenamiento GPR: {e}")
            self.is_trained = False
            return False
    
    def predict(self, target_timestamps, max_speed=7.0):
        """Predice posiciones para timestamps objetivo."""
        if not self.is_trained or self.x_model is None or self.y_model is None:
            return None
        
        if len(target_timestamps) == 0:
            return []
        
        # Normalizar timestamps objetivo
        ts_range = self.max_ts - self.min_ts
        norm_ts = (np.array(target_timestamps) - self.min_ts) / ts_range
        norm_ts = norm_ts.reshape(-1, 1)
        
        # Predicción con GPR
        pred_x, _ = self.x_model.predict(norm_ts, return_std=True)
        pred_y, _ = self.y_model.predict(norm_ts, return_std=True)
        
        # Aplicar restricciones de velocidad
        predictions = []
        last_pos = None
        last_ts = None
        
        for i in range(len(target_timestamps)):
            pos = [float(pred_x[i]), float(pred_y[i])]
            ts = target_timestamps[i]
            
            # Limitar velocidad entre puntos consecutivos
            if last_pos is not None and last_ts is not None:
                dt = (ts - last_ts) / 1000.0  # segundos
                if dt > 0:
                    dx = pos[0] - last_pos[0]
                    dy = pos[1] - last_pos[1]
                    distance = np.sqrt(dx*dx + dy*dy)
                    current_speed = distance / dt
                    
                    if current_speed > max_speed:
                        scale_factor = max_speed / current_speed
                        pos[0] = last_pos[0] + dx * scale_factor
                        pos[1] = last_pos[1] + dy * scale_factor
            
            predictions.append(pos)
            last_pos = pos
            last_ts = ts
        
        return predictions

class FutsalReplaySystem:
    def __init__(self, csv_file):
        """Inicializar el sistema de replay avanzado"""
        print("🔄 Cargando Sistema Avanzado de Replay UWB...")
        
        # Configuración avanzada
        self.use_kalman_filter = True
        self.use_ml_prediction = True
        self.trail_length = 100
        self.animation_step_ms = 20  # 50 FPS
        self.max_speed = 7.0  # m/s (velocidad sprint fútbol sala)
        self.interpolation_threshold = 100  # ms
        
        # Filtros y predictores
        self.kalman_filter = None
        self.trajectory_predictor = TrajectoryPredictor("futsal")
        
        # Datos procesados - Inicializar como None
        self.original_df = None
        self.df = None
        self.interpolated_data = None
        
        self.load_data(csv_file)
        self.setup_plot()
        self.setup_animation_controls()
        self.setup_interactive_controls()
        
    def load_data(self, csv_file):
        """Cargar y procesar datos CSV con filtros avanzados"""
        try:
            self.original_df = pd.read_csv(csv_file)
            self.original_df['timestamp'] = pd.to_datetime(self.original_df['timestamp'])
            
            # Validar datos
            required_columns = ['timestamp', 'x', 'y', 'tag_id']
            missing_cols = [col for col in required_columns if col not in self.original_df.columns]
            if missing_cols:
                raise ValueError(f"Columnas faltantes: {missing_cols}")
            
            print(f"✅ Datos originales cargados: {len(self.original_df)} registros")
            
            # Aplicar filtros avanzados
            self.apply_advanced_filtering()
            
            if self.df is not None:
                print(f"📊 Duración: {(self.df['timestamp'].iloc[-1] - self.df['timestamp'].iloc[0]).total_seconds():.1f} segundos")
                print(f"🏃 Rango X: {self.df['x'].min():.1f} - {self.df['x'].max():.1f}m")
                print(f"🏃 Rango Y: {self.df['y'].min():.1f} - {self.df['y'].max():.1f}m")
            
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            sys.exit(1)
    
    def apply_advanced_filtering(self):
        """Aplicar filtros avanzados: Kalman + ML + Interpolación"""
        if self.original_df is None:
            print("⚠️ No hay datos originales para procesar")
            return
            
        print("🔬 Aplicando filtros avanzados...")
        
        # Inicializar filtro de Kalman
        if self.use_kalman_filter:
            first_valid_pos = self.find_first_valid_position()
            if first_valid_pos is not None:
                self.kalman_filter = KalmanPositionFilter(
                    initial_pos=first_valid_pos,
                    process_noise=0.01,
                    measurement_noise=0.1
                )
        
        # Aplicar interpolación inteligente
        self.df = self.apply_intelligent_interpolation()
        
        if self.df is not None:
            print(f"✅ Filtros aplicados: {len(self.df)} frames interpolados")
        else:
            print("⚠️ Error: No se pudieron aplicar los filtros")
    
    def find_first_valid_position(self):
        """Encuentra la primera posición válida en los datos"""
        if self.original_df is None:
            return None
            
        for _, row in self.original_df.iterrows():
            if not (np.isnan(row['x']) or np.isnan(row['y'])):
                return [row['x'], row['y']]
        return None
    
    def apply_intelligent_interpolation(self):
        """Aplicar interpolación inteligente con ML y Kalman"""
        if self.original_df is None:
            return None
            
        # Convertir timestamps a millisegundos para trabajar
        timestamps_ms = [(ts - self.original_df['timestamp'].iloc[0]).total_seconds() * 1000 
                         for ts in self.original_df['timestamp']]
        
        # Crear timeline completo con step fijo
        start_ms = 0
        end_ms = timestamps_ms[-1]
        full_timeline = np.arange(start_ms, end_ms, self.animation_step_ms)
        
        # Preparar datos para interpolación
        positions = self.original_df[['x', 'y']].values
        
        # Identificar gaps grandes que requieren predicción ML
        interpolated_positions = []
        last_valid_idx = 0
        
        for target_ms in full_timeline:
            # Encontrar datos válidos más cercanos
            closest_idx = np.argmin(np.abs(np.array(timestamps_ms) - target_ms))
            
            if abs(timestamps_ms[closest_idx] - target_ms) <= self.interpolation_threshold:
                # Usar dato real si está cerca
                pos = positions[closest_idx]
                
                # Aplicar filtro de Kalman si está activado
                if self.use_kalman_filter and self.kalman_filter is not None:
                    dt = self.animation_step_ms / 1000.0
                    pos = self.kalman_filter.process(pos, dt)
                
                interpolated_positions.append(pos)
                last_valid_idx = len(interpolated_positions) - 1
                
            else:
                # Gap grande - usar predicción ML si está disponible
                if (self.use_ml_prediction and 
                    last_valid_idx >= 5 and 
                    len(interpolated_positions) >= 10):
                    
                    # Entrenar con datos recientes
                    recent_positions = np.array(interpolated_positions[-10:])
                    recent_timestamps = full_timeline[len(interpolated_positions)-10:len(interpolated_positions)]
                    
                    if self.trajectory_predictor.train(recent_timestamps, recent_positions):
                        predictions = self.trajectory_predictor.predict([target_ms], self.max_speed)
                        if predictions:
                            pos = predictions[0]
                        else:
                            # Fallback a interpolación lineal
                            pos = self.linear_interpolation_fallback(
                                interpolated_positions, target_ms, full_timeline, len(interpolated_positions)
                            )
                    else:
                        pos = self.linear_interpolation_fallback(
                            interpolated_positions, target_ms, full_timeline, len(interpolated_positions)
                        )
                else:
                    # Interpolación lineal simple
                    pos = self.linear_interpolation_fallback(
                        interpolated_positions, target_ms, full_timeline, len(interpolated_positions)
                    )
                
                interpolated_positions.append(pos)
        
        # Crear DataFrame interpolado
        interpolated_df = pd.DataFrame({
            'timestamp': [self.original_df['timestamp'].iloc[0] + timedelta(milliseconds=ms) 
                         for ms in full_timeline],
            'x': [pos[0] for pos in interpolated_positions],
            'y': [pos[1] for pos in interpolated_positions],
            'tag_id': [self.original_df['tag_id'].iloc[0]] * len(full_timeline)
        })
        
        return interpolated_df
    
    def linear_interpolation_fallback(self, positions_list, target_ms, timeline, current_idx):
        """Fallback de interpolación lineal cuando ML no está disponible"""
        if len(positions_list) == 0:
            return [20.0, 10.0]  # Centro de cancha por defecto
        
        if len(positions_list) == 1:
            return positions_list[0]
        
        # Interpolación lineal simple entre últimos dos puntos válidos
        if len(positions_list) >= 2:
            last_pos = positions_list[-1]
            prev_pos = positions_list[-2]
            
            # Extrapolación conservadora
            dx = last_pos[0] - prev_pos[0]
            dy = last_pos[1] - prev_pos[1]
            
            # Limitar extrapolación para evitar movimientos erráticos
            max_extrapolation = 0.5  # metros
            distance = np.sqrt(dx*dx + dy*dy)
            if distance > max_extrapolation:
                scale = max_extrapolation / distance
                dx *= scale
                dy *= scale
            
            return [last_pos[0] + dx, last_pos[1] + dy]
        
        return positions_list[-1]
    
    def setup_plot(self):
        """Configurar la visualización de la cancha"""
        # Crear figura con tamaño optimizado
        self.fig, self.ax = plt.subplots(figsize=(16, 10))
        
        # Verificar si el manager existe antes de intentar establecer el título
        try:
            if hasattr(self.fig.canvas, 'manager') and self.fig.canvas.manager is not None:
                self.fig.canvas.manager.set_window_title('🏟️ Sistema de Replay UWB - Fútbol Sala')
        except:
            pass  # Ignorar si no se puede establecer el título
        
        # Configurar cancha de fútbol sala (40x20m)
        self.ax.set_xlim(-3, 43)
        self.ax.set_ylim(-3, 23)
        self.ax.set_aspect('equal')
        self.ax.set_facecolor('#2d5016')  # Verde césped
        
        # Dibujar líneas de la cancha
        self.draw_futsal_court()
        
        # Dibujar anclas UWB
        self.draw_uwb_anchors()
        
        # Configurar elementos dinámicos
        self.setup_dynamic_elements()
        
        # Panel de información
        self.setup_info_panel()
    
    def draw_futsal_court(self):
        """Dibujar las líneas oficiales de fútbol sala"""
        # Perímetro de la cancha (40x20m)
        court = patches.Rectangle((0, 0), 40, 20, linewidth=3, 
                                edgecolor='white', facecolor='none')
        self.ax.add_patch(court)
        
        # Línea central
        self.ax.plot([20, 20], [0, 20], 'white', linewidth=2)
        
        # Círculo central (radio 3m)
        center_circle = patches.Circle((20, 10), 3, linewidth=2, 
                                     edgecolor='white', facecolor='none')
        self.ax.add_patch(center_circle)
        
        # Áreas de penalti (semicírculo radio 6m)
        # Área izquierda
        penalty_left = patches.Wedge((0, 10), 6, -90, 90, linewidth=2,
                                   edgecolor='white', facecolor='none')
        self.ax.add_patch(penalty_left)
        
        # Área derecha  
        penalty_right = patches.Wedge((40, 10), 6, 90, 270, linewidth=2,
                                    edgecolor='white', facecolor='none')
        self.ax.add_patch(penalty_right)
        
        # Porterías (3x2m)
        # Portería izquierda
        self.ax.plot([0, 0], [9, 11], 'white', linewidth=4)
        goal_left = patches.Rectangle((-0.5, 9), 0.5, 2, linewidth=2,
                                    edgecolor='white', facecolor='lightgray')
        self.ax.add_patch(goal_left)
        
        # Portería derecha
        self.ax.plot([40, 40], [9, 11], 'white', linewidth=4)
        goal_right = patches.Rectangle((40, 9), 0.5, 2, linewidth=2,
                                     edgecolor='white', facecolor='lightgray')
        self.ax.add_patch(goal_right)
        
        # Puntos de penalti
        self.ax.plot(6, 10, 'wo', markersize=8)
        self.ax.plot(34, 10, 'wo', markersize=8)
        
        # Esquinas (cuarto de círculo radio 25cm)
        corners = [(0, 0), (0, 20), (40, 0), (40, 20)]
        for x, y in corners:
            if x == 0 and y == 0:  # Esquina inferior izquierda
                corner = patches.Wedge((x, y), 0.25, 0, 90, linewidth=1,
                                     edgecolor='white', facecolor='none')
            elif x == 0 and y == 20:  # Esquina superior izquierda
                corner = patches.Wedge((x, y), 0.25, 270, 360, linewidth=1,
                                     edgecolor='white', facecolor='none')
            elif x == 40 and y == 0:  # Esquina inferior derecha
                corner = patches.Wedge((x, y), 0.25, 90, 180, linewidth=1,
                                     edgecolor='white', facecolor='none')
            else:  # Esquina superior derecha
                corner = patches.Wedge((x, y), 0.25, 180, 270, linewidth=1,
                                     edgecolor='white', facecolor='none')
            self.ax.add_patch(corner)
    
    def draw_uwb_anchors(self):
        """Dibujar posiciones de anclas UWB optimizadas"""
        anchors = {
            'A10': (-1, -1, 'red'),     # Esquina Suroeste
            'A20': (-1, 21, 'blue'),    # Esquina Noroeste  
            'A30': (41, -1, 'green'),   # Esquina Sureste
            'A40': (41, 21, 'orange'),  # Esquina Noreste
            'A50': (20, -1, 'purple')   # Centro campo Sur
        }
        
        for anchor_id, (x, y, color) in anchors.items():
            # Dibujar ancla
            self.ax.plot(x, y, 's', color=color, markersize=12, 
                        markeredgecolor='white', markeredgewidth=2)
            
            # Etiqueta
            self.ax.annotate(anchor_id, (x, y), xytext=(5, 5), 
                           textcoords='offset points', color='white',
                           fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', 
                                   facecolor=color, alpha=0.8))
    
    def setup_dynamic_elements(self):
        """Configurar elementos que cambian durante la animación"""
        # Jugador (tag)
        self.player_dot, = self.ax.plot([], [], 'yo', markersize=15, 
                                       markeredgecolor='red', markeredgewidth=2,
                                       label='Jugador', zorder=10)
        
        # Trayectoria (últimos N puntos)
        self.trail_length = 100  # Mostrar últimos 100 puntos
        self.trail_line, = self.ax.plot([], [], 'r-', alpha=0.6, linewidth=2,
                                       label='Trayectoria')
        
        # Puntos de trayectoria con degradado
        self.trail_dots, = self.ax.plot([], [], 'ro', alpha=0.3, markersize=3)
        
        # Zona actual del jugador
        self.current_zone = self.ax.text(20, -2, '', ha='center', va='center',
                                       fontsize=12, color='white', fontweight='bold',
                                       bbox=dict(boxstyle='round,pad=0.5', 
                                               facecolor='black', alpha=0.8))
        
        # Velocidad instantánea
        self.speed_indicator = patches.Circle((0, 0), 0, linewidth=2,
                                            edgecolor='cyan', facecolor='none',
                                            alpha=0.7)
        self.ax.add_patch(self.speed_indicator)
        
    def setup_info_panel(self):
        """Configurar panel de información en tiempo real"""
        # Panel de información (esquina superior izquierda)
        info_text = ("🏟️ SISTEMA DE REPLAY UWB - FÚTBOL SALA\n"
                    "⌨️  CONTROLES:\n"
                    "   SPACE: ⏯️  Play/Pause\n"
                    "   ←/→: Frame anterior/siguiente\n"
                    "   ↑/↓: Velocidad +/-\n"
                    "   R: 🔄 Reiniciar\n"
                    "   Q: ❌ Salir")
        
        self.info_panel = self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes,
                                     va='top', ha='left', fontsize=10, color='white',
                                     bbox=dict(boxstyle='round,pad=0.8', 
                                             facecolor='black', alpha=0.9))
        
        # Panel de estadísticas (esquina inferior derecha)
        self.stats_panel = self.ax.text(0.98, 0.02, '', transform=self.ax.transAxes,
                                      va='bottom', ha='right', fontsize=10, color='white',
                                      bbox=dict(boxstyle='round,pad=0.5', 
                                              facecolor='navy', alpha=0.9))
        
    def setup_animation_controls(self):
        """Configurar controles de animación"""
        self.current_frame = 0
        self.total_frames = len(self.df)
        self.is_playing = False
        self.playback_speed = 1.0
        self.max_speed = 10.0
        self.min_speed = 0.1
        
        # Conectar eventos de teclado
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
    def get_player_zone(self, x, y):
        """Determinar la zona actual del jugador"""
        # Portería izquierda
        if x <= 6 and 7 <= y <= 13:
            return "🥅 ÁREA PORTERÍA IZQUIERDA"
        # Portería derecha  
        elif x >= 34 and 7 <= y <= 13:
            return "🥅 ÁREA PORTERÍA DERECHA"
        # Centro campo
        elif 17 <= x <= 23 and 7 <= y <= 13:
            return "⚽ CENTRO CAMPO"
        # Medio campo izquierdo
        elif x <= 20:
            return "👈 MEDIO CAMPO IZQUIERDO"
        # Medio campo derecho
        elif x > 20:
            return "👉 MEDIO CAMPO DERECHO"
        else:
            return "🏃 EN JUEGO"
    
    def calculate_speed(self, frame_idx):
        """Calcular velocidad instantánea"""
        if frame_idx == 0:
            return 0.0
            
        current_row = self.df.iloc[frame_idx]
        prev_row = self.df.iloc[frame_idx - 1]
        
        # Distancia euclidiana
        dx = current_row['x'] - prev_row['x'] 
        dy = current_row['y'] - prev_row['y']
        distance = np.sqrt(dx**2 + dy**2)
        
        # Tiempo transcurrido
        dt = (current_row['timestamp'] - prev_row['timestamp']).total_seconds()
        
        if dt > 0:
            speed = distance / dt  # m/s
            return speed
        return 0.0
    
    def update_frame(self, frame_idx):
        """Actualizar visualización para el frame actual"""
        if frame_idx >= self.total_frames:
            frame_idx = self.total_frames - 1
            
        # Datos del frame actual
        current_data = self.df.iloc[frame_idx]
        x, y = current_data['x'], current_data['y']
        timestamp = current_data['timestamp']
        
        # Actualizar posición del jugador
        self.player_dot.set_data([x], [y])
        
        # Actualizar trayectoria
        start_idx = max(0, frame_idx - self.trail_length)
        trail_data = self.df.iloc[start_idx:frame_idx + 1]
        
        if len(trail_data) > 1:
            self.trail_line.set_data(trail_data['x'], trail_data['y'])
            self.trail_dots.set_data(trail_data['x'], trail_data['y'])
        
        # Calcular velocidad
        speed = self.calculate_speed(frame_idx)
        
        # Indicador visual de velocidad (círculo proporcional)
        speed_radius = min(2.0, speed * 0.5)  # Radio máximo 2m
        self.speed_indicator.center = (x, y)
        self.speed_indicator.radius = speed_radius
        
        # Determinar zona actual
        zone = self.get_player_zone(x, y)
        self.current_zone.set_text(zone)
        
        # Actualizar panel de estadísticas
        elapsed_time = (timestamp - self.df['timestamp'].iloc[0]).total_seconds()
        progress = (frame_idx / self.total_frames) * 100
        
        stats_text = (f"⏱️  TIEMPO: {elapsed_time:.1f}s\n"
                     f"📍 POSICIÓN: ({x:.1f}, {y:.1f})m\n"
                     f"🏃 VELOCIDAD: {speed:.2f} m/s\n"
                     f"🎯 FRAME: {frame_idx + 1}/{self.total_frames}\n"
                     f"📊 PROGRESO: {progress:.1f}%\n"
                     f"⚡ VELOCIDAD REPR.: {self.playback_speed:.1f}x")
        
        self.stats_panel.set_text(stats_text)
        
        # Actualizar título con timestamp
        self.ax.set_title(f"🏟️ Replay UWB - Fútbol Sala | {timestamp.strftime('%H:%M:%S.%f')[:-3]} | {'▶️' if self.is_playing else '⏸️'}",
                         fontsize=14, fontweight='bold', color='white')
        
        return [self.player_dot, self.trail_line, self.trail_dots, 
                self.current_zone, self.stats_panel, self.speed_indicator]
    
    def animate(self, frame):
        """Función de animación principal"""
        if self.is_playing:
            # Avanzar frame según velocidad de reproducción
            step = max(1, int(self.playback_speed))
            self.current_frame = min(self.current_frame + step, self.total_frames - 1)
            
            # Pausar automáticamente al final
            if self.current_frame >= self.total_frames - 1:
                self.is_playing = False
                
        return self.update_frame(self.current_frame)
    
    def on_key_press(self, event):
        """Manejar eventos de teclado"""
        if event.key == ' ':  # Space - Play/Pause
            self.is_playing = not self.is_playing
            print(f"▶️ Reproducción: {'Iniciada' if self.is_playing else 'Pausada'}")
            
        elif event.key == 'left':  # Flecha izquierda - Frame anterior
            self.current_frame = max(0, self.current_frame - 1)
            print(f"⬅️ Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'right':  # Flecha derecha - Frame siguiente
            self.current_frame = min(self.total_frames - 1, self.current_frame + 1)
            print(f"➡️ Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'up':  # Flecha arriba - Aumentar velocidad
            self.playback_speed = min(self.max_speed, self.playback_speed + 0.5)
            print(f"⚡ Velocidad: {self.playback_speed:.1f}x")
            
        elif event.key == 'down':  # Flecha abajo - Reducir velocidad
            self.playback_speed = max(self.min_speed, self.playback_speed - 0.5)
            print(f"🐌 Velocidad: {self.playback_speed:.1f}x")
            
        elif event.key == 'r':  # R - Reiniciar
            self.current_frame = 0
            self.is_playing = False
            print("🔄 Replay reiniciado")
            
        elif event.key == 'q':  # Q - Salir
            print("❌ Cerrando replay...")
            plt.close(self.fig)
            
        # Actualizar visualización inmediatamente
        if not self.is_playing:
            self.update_frame(self.current_frame)
            self.fig.canvas.draw()
    
    def start_replay(self):
        """Iniciar el sistema de replay"""
        print("\n🎬 Iniciando Sistema de Replay UWB")
        print("═" * 50)
        print("⌨️  Usa las teclas para controlar la reproducción:")
        print("   SPACE: ⏯️  Play/Pause")
        print("   ←/→: Frame anterior/siguiente") 
        print("   ↑/↓: Velocidad +/-")
        print("   R: 🔄 Reiniciar")
        print("   Q: ❌ Salir")
        print("═" * 50)
        
        # Configurar animación
        self.anim = FuncAnimation(
            self.fig, self.animate, frames=self.total_frames,
            interval=40,  # 25 FPS = 40ms entre frames
            repeat=True, blit=False
        )
        
        # Mostrar replay
        plt.tight_layout()
        plt.show()

    def setup_interactive_controls(self):
        """Configurar controles interactivos avanzados"""
        # Área para controles interactivos (sliders, botones)
        plt.subplots_adjust(bottom=0.2)
        
        # Slider para velocidad de reproducción
        ax_speed = plt.axes((0.2, 0.02, 0.3, 0.03))
        self.speed_slider = Slider(ax_speed, 'Velocidad', 0.1, 5.0, valinit=1.0)
        self.speed_slider.on_changed(self.update_speed)
        
        # Botón para activar/desactivar filtros
        ax_kalman = plt.axes((0.55, 0.02, 0.1, 0.04))
        self.kalman_button = Button(ax_kalman, 'Kalman')
        self.kalman_button.on_clicked(self.toggle_kalman)
        
        # Botón para activar/desactivar ML
        ax_ml = plt.axes((0.67, 0.02, 0.1, 0.04))
        self.ml_button = Button(ax_ml, 'ML Pred')
        self.ml_button.on_clicked(self.toggle_ml)
        
        # Actualizar colores de botones según estado
        self.update_button_colors()
    
    def update_speed(self, val):
        """Actualizar velocidad de reproducción"""
        self.playback_speed = val
    
    def toggle_kalman(self, event):
        """Activar/desactivar filtro de Kalman"""
        self.use_kalman_filter = not self.use_kalman_filter
        print(f"🔧 Filtro de Kalman: {'Activado' if self.use_kalman_filter else 'Desactivado'}")
        self.update_button_colors()
        
        # Recargar datos con nuevo filtro
        self.apply_advanced_filtering()
    
    def toggle_ml(self, event):
        """Activar/desactivar predicción ML"""
        self.use_ml_prediction = not self.use_ml_prediction
        print(f"🤖 Predicción ML: {'Activada' if self.use_ml_prediction else 'Desactivada'}")
        self.update_button_colors()
        
        # Recargar datos con nueva configuración
        self.apply_advanced_filtering()
    
    def update_button_colors(self):
        """Actualizar colores de botones según estado"""
        kalman_color = 'lightgreen' if self.use_kalman_filter else 'lightcoral'
        ml_color = 'lightblue' if self.use_ml_prediction else 'lightcoral'
        
        self.kalman_button.color = kalman_color
        self.ml_button.color = ml_color

def generate_movement_report(csv_file):
    """Generar reporte de análisis de movimiento"""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calcular estadísticas
    total_time = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    
    # Distancia total recorrida
    distances = []
    for i in range(1, len(df)):
        dx = df['x'].iloc[i] - df['x'].iloc[i-1]
        dy = df['y'].iloc[i] - df['y'].iloc[i-1]
        distances.append(np.sqrt(dx**2 + dy**2))
    
    total_distance = sum(distances)
    avg_speed = total_distance / total_time if total_time > 0 else 0
    max_speed = max(distances) * 25 if distances else 0  # Asumiendo 25 Hz
    
    print(f"\n📊 REPORTE DE ANÁLISIS DE MOVIMIENTO")
    print("═" * 50)
    print(f"⏱️  Duración total: {total_time:.1f} segundos ({total_time/60:.1f} minutos)")
    print(f"📏 Distancia recorrida: {total_distance:.1f} metros")
    print(f"🏃 Velocidad promedio: {avg_speed:.2f} m/s")
    print(f"⚡ Velocidad máxima: {max_speed:.2f} m/s")
    print(f"📊 Total de frames: {len(df)}")
    print(f"🔄 Frecuencia de muestreo: ~{len(df)/total_time:.1f} Hz")
    print("═" * 50)

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='🏟️ Sistema de Replay UWB para Fútbol Sala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python movement_replay.py                                    # Usar archivo por defecto
  python movement_replay.py data/mi_partido.csv               # Archivo específico
  python movement_replay.py --report data/mi_partido.csv      # Solo mostrar reporte
        """
    )
    
    parser.add_argument('csv_file', nargs='?', 
                       default='data/uwb_data_futsal_game_20250621_160000.csv',
                       help='Archivo CSV con datos de movimiento')
    parser.add_argument('--report', action='store_true',
                       help='Mostrar solo reporte de análisis sin replay')
    
    args = parser.parse_args()
    
    # Verificar si el archivo existe
    import os
    if not os.path.exists(args.csv_file):
        print(f"❌ Error: No se encontró el archivo '{args.csv_file}'")
        print("💡 Archivos disponibles en data/:")
        if os.path.exists('data'):
            for file in os.listdir('data'):
                if file.endswith('.csv'):
                    print(f"   📄 {file}")
        sys.exit(1)
    
    try:
        if args.report:
            # Solo mostrar reporte
            generate_movement_report(args.csv_file)
        else:
            # Mostrar reporte y ejecutar replay
            generate_movement_report(args.csv_file)
            
            # Iniciar sistema de replay
            replay_system = FutsalReplaySystem(args.csv_file)
            replay_system.start_replay()
            
    except KeyboardInterrupt:
        print("\n👋 Sistema de replay finalizado por el usuario")
    except Exception as e:
        print(f"❌ Error durante el replay: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 