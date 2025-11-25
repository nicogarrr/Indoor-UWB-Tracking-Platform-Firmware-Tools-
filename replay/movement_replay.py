#!/usr/bin/env python3
"""
UWB Replay System for Indoor Localization Analysis
Interactive player for movement data with advanced filters
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
import argparse
import sys
import os
import glob
from datetime import datetime, timedelta
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import WhiteKernel, Matern
import warnings

class KalmanPositionFilter:
    """
    Implementation of the Kalman Filter for UWB indoor systems.
    Reduces measurement noise and improves positioning accuracy.
    """
    def __init__(self, initial_pos=None, process_noise=0.002, measurement_noise=0.2):
        self.state = np.zeros(4)  # [x, y, vx, vy]
        if initial_pos is not None:
            self.state[:2] = initial_pos
            
        self.P = np.eye(4) * 50
        
        self.Q = np.array([
            [process_noise, 0, 0, 0],
            [0, process_noise, 0, 0],
            [0, 0, process_noise * 1.5, 0],
            [0, 0, 0, process_noise * 1.5]
        ])
        
        self.R = np.eye(2) * measurement_noise
        self.F = np.eye(4)
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]])
        
        self.initialized = False
        
    def predict(self, dt):
        """Predict the next state based on the movement model."""
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        
    def update(self, measurement):
        """Update the state with a new measurement."""
        y = measurement - self.H @ self.state
        
        # Detection of outliers in the innovation
        innovation_magnitude = np.linalg.norm(y)
        max_innovation = 3.0
        
        if innovation_magnitude > max_innovation:
            measurement_noise_factor = min(5.0, innovation_magnitude / max_innovation)
            R_adaptive = self.R * measurement_noise_factor
        else:
            R_adaptive = self.R
        
        # Covariance of the innovation
        S = self.H @ self.P @ self.H.T + R_adaptive
        
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        self.state = self.state + K @ y
        
        # Update covariance
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P
        
    def process(self, position, dt=0.02):
        """Process a new position, returning the filtered position."""
        # If the position is NaN, only predict without updating
        if np.isnan(position[0]) or np.isnan(position[1]):
            if self.initialized:
                self.predict(dt)
                return self.state[:2]
            else:
                return position
        
        if not self.initialized:
            # First valid measurement: initialize
            self.state[:2] = position
            self.initialized = True
            return position
        
        # Perform prediction
        self.predict(dt)
        
        # Update with measurement
        self.update(position)
        
        # Return filtered position
        return self.state[:2]

class TrajectoryPredictor:
    """
    Prediction of trajectories using Gaussian Process Regression (GPR)
    for indoor movements.
    """
    def __init__(self, context="indoor"):
        self.context = context
        self.x_model = None
        self.y_model = None
        self.min_samples_required = 5
        self.is_trained = False
        self.min_ts = 0
        self.max_ts = 0
        
        length_scale_bounds = (1e-3, 25.0)
        noise_level_bounds = (1e-8, 1.0)
        
        self.kernel_x = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                       WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
        
        self.kernel_y = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                       WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
    
    def train(self, timestamps, positions):
        """Train the GPR models using historical data."""
        if len(timestamps) < self.min_samples_required:
            self.is_trained = False
            return False
        
        valid_indices = ~np.any(np.isnan(positions), axis=1)
        valid_timestamps = timestamps[valid_indices]
        valid_positions = positions[valid_indices]
        
        if len(valid_timestamps) < self.min_samples_required:
            self.is_trained = False
            return False
        
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
            self.is_trained = False
            return False
    
    def predict(self, target_timestamps, max_speed=7.0):
        """
        Predict positions for target timestamps using trained GPR.
        
        Args:
            target_timestamps: List of target timestamps in milliseconds
            max_speed: Maximum allowed speed in m/s (default: 7.0 m/s for indoor movement)
            
        Returns:
            List[[x, y]]: List of predicted positions, or None/[] if error
        """
        if not self.is_trained or self.x_model is None or self.y_model is None:
            return None
        
        if len(target_timestamps) == 0:
            return []
        
        # Normalize target timestamps
        ts_range = self.max_ts - self.min_ts
        
        # Additional validation: avoid division by zero if there is only one timestamp
        if ts_range == 0:
            return []
        
        norm_ts = (np.array(target_timestamps) - self.min_ts) / ts_range
        norm_ts = norm_ts.reshape(-1, 1)
        
        # Prediction with GPR
        pred_x, _ = self.x_model.predict(norm_ts, return_std=True)
        pred_y, _ = self.y_model.predict(norm_ts, return_std=True)
        
        # Ensure predictions are arrays
        pred_x = np.array(pred_x).flatten()
        pred_y = np.array(pred_y).flatten()
        
        # Apply speed restrictions
        predictions = []
        last_pos = None
        last_ts = None
        
        for i in range(len(target_timestamps)):
            pos = [float(pred_x[i]), float(pred_y[i])]
            ts = target_timestamps[i]
            
            # Limit speed between consecutive points
            if last_pos is not None and last_ts is not None:
                dt = (ts - last_ts) / 1000.0  # seconds
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

class UWBHexagonReplaySystem:
    def __init__(self, csv_file, optimize_memory=False, skip_trail=False, verbose_debug=False):
        """
        Initialize the advanced replay system
        
        Args:
            csv_file: CSV file with movement data
            optimize_memory: Flag to optimize memory in large datasets (>1M rows)
            skip_trail: Flag to omit real-time trajectory (reduces memory)
            verbose_debug: Flag to show all GPR debug logs (can be spam)
        """
        print("Loading UWB Replay System...")
        
        self.use_kalman_filter = True
        self.use_ml_prediction = False
        self.optimize_memory = optimize_memory
        self.skip_trail = skip_trail
        self.verbose_debug = verbose_debug
        self.debug_log_counter = 0  # Counter to limit spam of logs
        
        if skip_trail:
            print("Simplified trail")
        elif optimize_memory:
            print("Memory optimization mode")
        else:
            print("Full trail enabled")
        
        self.trail_length = None
        
        self.animation_step_ms = 20
        self.max_player_speed = 7.0
        self.interpolation_threshold = 100
        self.gpr_train_interval_ms = 500
        self._last_gpr_train_ms = -1
        
        self.kalman_filter = None
        self.trajectory_predictor = TrajectoryPredictor("indoor")
        
        self.original_df = None
        self.df = None
        
        self.load_data(csv_file)
        self.setup_plot()
        self.setup_animation_controls()
        self.setup_interactive_controls()
        
    def load_data(self, csv_file):
        """Load and process CSV data with advanced filters"""
        try:
            file_size_mb = os.path.getsize(csv_file) / (1024 * 1024)
            print(f"File size: {file_size_mb:.1f} MB")
            
            if file_size_mb > 20:
                print("WARNING: Large dataset detected")
                
                if not self.optimize_memory and file_size_mb > 50:
                    print("RECOMMENDATION: Activate memory optimization")
            
            if self.optimize_memory:
                print("Memory optimization mode active")
                try:
                    self.original_df = pd.read_csv(csv_file)
                    for col in ['x', 'y']:
                        if col in self.original_df.columns:
                            self.original_df[col] = self.original_df[col].astype('float32')
                    if 'tag_id' in self.original_df.columns:
                        self.original_df['tag_id'] = self.original_df['tag_id'].astype('int32')
                except Exception as e:
                    self.original_df = pd.read_csv(csv_file)
            else:
                self.original_df = pd.read_csv(csv_file)
            
            num_rows = len(self.original_df)
            memory_usage_mb = self.original_df.memory_usage(deep=True).sum() / (1024 * 1024)
            
            print(f"Original rows: {num_rows:,}")
            print(f"Current DataFrame memory: {memory_usage_mb:.1f} MB")
            
            self.original_df['timestamp'] = pd.to_datetime(self.original_df['timestamp'])
            
            required_columns = ['timestamp', 'x', 'y', 'tag_id']
            missing_cols = [col for col in required_columns if col not in self.original_df.columns]
            if missing_cols:
                raise ValueError(f"Missing columns: {missing_cols}")
            
            print(f"Original data loaded: {len(self.original_df)} rows")
            
            self.apply_advanced_filtering()
            
            if self.df is not None and len(self.df) > 0:
                print(f"Duration: {(self.df['timestamp'].iloc[-1] - self.df['timestamp'].iloc[0]).total_seconds():.1f} seconds")
                print(f"X range: {self.df['x'].min():.1f} - {self.df['x'].max():.1f}m")
                print(f"Y range: {self.df['y'].min():.1f} - {self.df['y'].max():.1f}m")
            else:
                print("Could not process data correctly")
                sys.exit(1)
                
        except Exception as e:
            print(f"Error loading data: {e}")
            sys.exit(1)
    
    def apply_advanced_filtering(self):
        """Apply advanced filters: Kalman + ML + Interpolation"""
        if self.original_df is None:
            print("No original data to process")
            return
            
        print("Applying advanced filters...")
        
        if self.use_kalman_filter:
            first_valid_pos = self.find_first_valid_position()
            if first_valid_pos is not None:
                # OPTIMIZED: Increased process_noise (0.1 -> 0.3) for SPORTS (high reactivity)
                self.kalman_filter = KalmanPositionFilter(
                    initial_pos=first_valid_pos,
                    process_noise=0.3,
                    measurement_noise=0.1
                )
        
        self.df = self.apply_intelligent_interpolation()
        
        if self.df is not None:
            print(f"Filters applied: {len(self.df)} interpolated frames")
        else:
            print("Error: Could not apply filters")
    
    def find_first_valid_position(self):
        """Find the first valid position in the data"""
        if self.original_df is None:
            return None
            
        for _, row in self.original_df.iterrows():
            if not (np.isnan(row['x']) or np.isnan(row['y'])):
                return [row['x'], row['y']]
        return None
    
    def apply_intelligent_interpolation(self):
        """Aplicar interpolación inteligente con ML y Kalman optimizada para fluidez"""
        if self.original_df is None:
            return None
            
        # Convert timestamps to milliseconds to work
        timestamps_ms = np.array([
            (ts - self.original_df['timestamp'].iloc[0]).total_seconds() * 1000
            for ts in self.original_df['timestamp']
        ], dtype=np.float64)
        
        original_avg_interval = np.mean(np.diff(timestamps_ms))
        print(f"Original average interval: {original_avg_interval:.1f}ms")
        
        if original_avg_interval > 500:
            fluid_step_ms = 33.33  
            print("Using 30fps for sparse data")
        else:
            fluid_step_ms = 16.67  
            print("Using 60fps for dense data")
        
        start_ms = 0
        end_ms = timestamps_ms[-1]
        full_timeline = np.arange(start_ms, end_ms + fluid_step_ms, fluid_step_ms)
        
        positions = self.original_df[['x', 'y']].values
        interpolated_positions = []
        
        for target_ms in full_timeline:
            idx = np.searchsorted(timestamps_ms, target_ms)
            if idx >= len(timestamps_ms):
                idx = len(timestamps_ms) - 1
            if idx > 0 and abs(timestamps_ms[idx - 1] - target_ms) < abs(timestamps_ms[idx] - target_ms):
                closest_idx = idx - 1
            else:
                closest_idx = idx
            
            if abs(timestamps_ms[closest_idx] - target_ms) <= self.interpolation_threshold:
                pos = positions[closest_idx]
                
                if self.use_kalman_filter and self.kalman_filter is not None:
                    dt = self.animation_step_ms / 1000.0
                    pos = self.kalman_filter.process(pos, dt)
                
                interpolated_positions.append(pos)
                
            else:
                if (
                    self.use_ml_prediction and
                    len(interpolated_positions) >= 10
                ):

                    # Solo reentrenar GPR si ha pasado el intervalo mínimo
                    should_train = (
                        (self._last_gpr_train_ms < 0) or
                        (target_ms - self._last_gpr_train_ms >= self.gpr_train_interval_ms) or
                        (not self.trajectory_predictor.is_trained)
                    )

                    if should_train:
                        # Entrenar con las 10 últimas muestras válidas
                        recent_positions = np.array(interpolated_positions[-10:])
                        recent_timestamps = np.array(full_timeline[len(interpolated_positions)-10 : len(interpolated_positions)])

                        # Verificar que haya al menos 5 timestamps distintos
                        unique_ts = len(np.unique(recent_timestamps))
                        if unique_ts >= 5 and self.trajectory_predictor.train(recent_timestamps, recent_positions):
                            self._last_gpr_train_ms = target_ms
                        else:
                            # Si no se pudo entrenar, caeremos en fallback lineal más abajo
                            pass

                    # Predecir si el modelo está entrenado
                    if self.trajectory_predictor.is_trained:
                        predictions = self.trajectory_predictor.predict([target_ms], self.max_player_speed)
                        if predictions:
                            pos = predictions[0]
                        else:
                            pos = self.linear_interpolation_fallback(interpolated_positions, target_ms)
                    else:
                        pos = self.linear_interpolation_fallback(interpolated_positions, target_ms)
                
                interpolated_positions.append(pos)
        
        # NUEVO: Aplicar suavizado adicional con media móvil
        smoothed_positions = self.apply_moving_average_smoothing(interpolated_positions)
        
        # Crear DataFrame interpolado
        interpolated_df = pd.DataFrame({
            'timestamp': [self.original_df['timestamp'].iloc[0] + timedelta(milliseconds=ms) 
                         for ms in full_timeline],
            'x': [pos[0] for pos in smoothed_positions],
            'y': [pos[1] for pos in smoothed_positions],
            'tag_id': [self.original_df['tag_id'].iloc[0]] * len(full_timeline)
        })
        
        # === OPTIMIZACIÓN MEMORIA: Mantener tipos eficientes ===
        if self.optimize_memory:
            # Convertir a tipos optimizados para ahorrar memoria
            interpolated_df = interpolated_df.astype({
                'x': 'float32',
                'y': 'float32',
                'tag_id': 'int32'
            })
        
        # === OPTIMIZACIÓN: Cálculo previo de distancias ===
        # Calcular distancias step by step usando numpy (más eficiente)
        x_diff = interpolated_df['x'].diff()
        y_diff = interpolated_df['y'].diff()
        step_distances = np.hypot(x_diff, y_diff)
        step_distances[0] = 0  # Primera distancia es 0 (sin diferencia previa)
        interpolated_df['step_dist'] = step_distances
        # Distancia acumulativa para acceso O(1) en update_frame
        interpolated_df['cum_dist'] = interpolated_df['step_dist'].cumsum()
        
        # === OPTIMIZACIÓN MEMORIA: Convertir distancias también ===
        if self.optimize_memory:
            interpolated_df = interpolated_df.astype({
                'step_dist': 'float32',
                'cum_dist': 'float32'
            })
        
        return interpolated_df
    
    def apply_moving_average_smoothing(self, positions_list, window_size=3):
        """
        Aplicar suavizado con media móvil para eliminar tirones.
        MEJORADO: Ventana reducida (7->3) para evitar recortar las esquinas.
        
        Args:
            positions_list: Lista de posiciones [x, y]
            window_size: Tamaño de la ventana deslizante (impar recomendado)
            
        Returns:
            Lista de posiciones suavizadas
        """
        if len(positions_list) <= window_size:
            return positions_list
        
        # === PASO 1: Aplicar detección de tirones y corrección ===
        corrected_positions = self.detect_and_fix_jitter(positions_list)
        
        # === PASO 2: Suavizado con media móvil ===
        smoothed = []
        half_window = window_size // 2
        
        for i in range(len(corrected_positions)):
            # Determinar límites de la ventana
            start_idx = max(0, i - half_window)
            end_idx = min(len(corrected_positions), i + half_window + 1)
            
            # Calcular media de la ventana
            window_positions = corrected_positions[start_idx:end_idx]
            avg_x = sum(pos[0] for pos in window_positions) / len(window_positions)
            avg_y = sum(pos[1] for pos in window_positions) / len(window_positions)
            
            # Usar suavizado más agresivo en todas las posiciones
            if i < half_window or i >= len(corrected_positions) - half_window:
                # Extremos: 90% suavizado, 10% original para eliminar tirones
                original_x, original_y = corrected_positions[i]
                smooth_x = 0.9 * avg_x + 0.1 * original_x
                smooth_y = 0.9 * avg_y + 0.1 * original_y
                smoothed.append([smooth_x, smooth_y])
            else:
                # Centro: suavizado completo
                smoothed.append([avg_x, avg_y])
        
        return smoothed
        
    def detect_and_fix_jitter(self, positions_list, jitter_threshold=1.5):
        """
        Detectar y corregir tirones hacia atrás (movimiento errático).
        
        Args:
            positions_list: Lista de posiciones [x, y]
            jitter_threshold: Umbral para detectar cambios bruscos de dirección (metros)
            
        Returns:
            Lista de posiciones con tirones corregidos
        """
        if len(positions_list) < 3:
            return positions_list
        
        corrected = positions_list.copy()
        
        for i in range(1, len(positions_list) - 1):
            prev_pos = positions_list[i-1]
            curr_pos = positions_list[i]
            next_pos = positions_list[i+1]
            
            # Calcular vectores de movimiento
            vec1 = [curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1]]
            vec2 = [next_pos[0] - curr_pos[0], next_pos[1] - curr_pos[1]]
            
            # Calcular magnitudes
            mag1 = np.sqrt(vec1[0]**2 + vec1[1]**2)
            mag2 = np.sqrt(vec2[0]**2 + vec2[1]**2)
            
            # Detectar cambio brusco de dirección (tirón hacia atrás)
            if mag1 > jitter_threshold and mag2 > jitter_threshold:
                # Calcular producto escalar para detectar cambio de dirección
                dot_product = vec1[0]*vec2[0] + vec1[1]*vec2[1]
                
                # Si el ángulo es > 120 grados (dot < -0.5), es un tirón
                if dot_product < -0.5 * mag1 * mag2:
                    # Corregir usando interpolación lineal
                    corrected[i] = [
                        (prev_pos[0] + next_pos[0]) * 0.5,
                        (prev_pos[1] + next_pos[1]) * 0.5
                    ]
        
        return corrected
    
    def linear_interpolation_fallback(self, positions_list, target_ms):
        """
        Fallback de interpolación lineal cuando ML no está disponible.
        
        Args:
            positions_list: Lista de posiciones [x, y] válidas anteriores
            target_ms: Timestamp objetivo en millisegundos (no usado en cálculo)
            
        Returns:
            [x, y]: Posición interpolada/extrapolada
        """
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
            
            # Limitar extrapolación vinculada a la frecuencia de muestreo  
            max_extrapolation = 0.5 * (self.animation_step_ms / 20)
            distance = np.sqrt(dx*dx + dy*dy)
            if distance > max_extrapolation:
                scale = max_extrapolation / distance
                dx *= scale
                dy *= scale
            
            return [last_pos[0] + dx, last_pos[1] + dy]
        
        return positions_list[-1]
    
    def setup_plot(self):
        """Configure the visualization of the indoor hexagonal area"""
        # Create figure and axes
        self.fig, self.ax = plt.subplots(figsize=(18, 12))

        # Try to set window title (may fail on some backends)
        try:
            if hasattr(self.fig.canvas, 'manager') and self.fig.canvas.manager is not None:
                self.fig.canvas.manager.set_window_title('UWB Replay System - Indoor Hexagon Area')
        except Exception:
            pass
        
        # ======================== INDOOR AREA (updated to 10.60 x 7.35) ========================
        minX, maxX = 0.0, 10.6
        minY, maxY = 0.0, 7.35
        self.ax.set_xlim(minX - 1, maxX + 1)
        self.ax.set_ylim(minY - 1, maxY + 1)
        self.ax.set_aspect('equal')
        self.ax.set_facecolor('#f8f8f8')

        self.draw_hexagon_area()
        self.draw_hexagon_anchors()
        
        # Configure dynamic elements
        self.setup_dynamic_elements()
        
        # Information panel
        self.setup_info_panel()


    

    
    def draw_hexagon_anchors(self):
        """Draw UWB anchors in the indoor arrangement (6 anchors) - updated positions for 10.60 x 7.35"""
        anchors = {
            'A1': (0.0,  0.0,  'blue'),  # Left Bottom Corner
            'A2': (0.0,  7.35, 'blue'),  # Left Top Corner
            'A3': (5.3,  7.35, 'blue'),  # Top Edge Midpoint
            'A4': (10.6, 7.35, 'blue'),  # Right Top Corner
            'A5': (10.6, 0.0,  'blue'),  # Right Bottom Corner
            'A6': (5.3,  0.0,  'blue')   # Bottom Edge Midpoint
        }

        for anchor_id, (x, y, color) in anchors.items():
            self.ax.plot(x, y, 's', color=color, markersize=10, zorder=5)
            # Place the label slightly offset inside the area for readability
            label_offset_y = 0.25 if y <= 0.5 else 0.3
            self.ax.text(x, y + label_offset_y, anchor_id, ha='center', va='bottom', fontsize=9, color='black')
    
    def draw_hexagon_area(self):
        """Draw the play area perimeter"""
        # Vertices of the room (Rectangular 10.6m x 7.35m)
        verts = [
            (0.0, 0.0),       # Lower left
            (0.0, 7.35),      # Upper left
            (10.6, 7.35),     # Upper right
            (10.6, 0.0),      # Lower right
            (0.0, 0.0)        # Close loop
        ]
        poly = patches.Polygon(verts, closed=True, fill=False, edgecolor='orange', linewidth=3, alpha=0.8)
        self.ax.add_patch(poly)
        
        # Add vertex labels for debug
        for i, (x, y) in enumerate(verts[:-1]):
            self.ax.plot(x, y, 'ro', markersize=6, alpha=0.7)
            self.ax.text(x+0.2, y+0.2, f'V{i+1}', fontsize=8, color='red', alpha=0.8)
    
    def setup_dynamic_elements(self):
        """Configure elements that change during the animation"""
        # === MAIN PLAYER ===
        # Player with improved design (shirt + number)
        self.player_dot, = self.ax.plot([], [], 'o', color='#FFD700', markersize=18, 
                                       markeredgecolor='#FF4500', markeredgewidth=3,
                                       label='Player', zorder=20)
        
        # Player number
        self.player_number = self.ax.text(0, 0, '7', ha='center', va='center',
                                        fontsize=10, fontweight='bold', color='white', zorder=21)
        
        # === FULL TRAJECTORY (all trajectory visible) ===
        if not self.skip_trail:
            # Main trajectory with gradient
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.8, linewidth=3,
                                           label='Complete Trajectory', zorder=10)
            
            # Secondary trajectory (shadow)
            self.trail_shadow, = self.ax.plot([], [], '-', color='black', alpha=0.3, linewidth=5,
                                             zorder=9)
            
            # Trajectory points with variable size
            self.trail_dots, = self.ax.plot([], [], 'o', color='#FF8C42', alpha=0.4, markersize=3,
                                           zorder=11)
            print(" Full trajectory enabled (all path visible)")
        else:
            # Optimization mode: only basic line but complete
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.6, linewidth=2,
                                           label='Complete Trajectory (optimized)', zorder=10)
            self.trail_shadow = None
            self.trail_dots = None
            print(" Memory optimization mode: simplified full trajectory")
        
        # === INDICADORES DE VELOCIDAD ===
        # Círculo de velocidad (DESACTIVADO para máxima fluidez)
        self.speed_indicator = None  # Desactivado por rendimiento
        # self.speed_indicator = patches.Circle((0, 0), 0, linewidth=3,
        #                                     edgecolor='cyan', facecolor='cyan',
        #                                     alpha=0.3, zorder=12)
        # self.ax.add_patch(self.speed_indicator)
        
        # === ZONA ACTUAL ===
        # Posicionado muy abajo para evitar solapamiento total
        self.current_zone = self.ax.text(20, -4.5, '', ha='center', va='center',
                                       fontsize=10, color='white', fontweight='bold',
                                       bbox=dict(boxstyle='round,pad=0.4', 
                                               facecolor='black', alpha=0.9,
                                               edgecolor='yellow', linewidth=1))
        
        # === TRAYECTORIA PERSISTENTE ===
        # La trayectoria completa permanece visible durante todo el replay
        # Desde el punto inicial hasta la posición actual del jugador
        
        # === MAPA DE CALOR ===
        # Eliminado para optimización de memoria - usar directamente self.df si se necesita
        
    def setup_info_panel(self):
        """Configure real-time information panel"""
        # Compact information panel (upper left corner)
        info_text = ("CONTROLS: SPACE=Play/Pause | ←→=Frame | ↑↓=Speed | R=Reset | Q=Exit")
        
        self.info_panel = self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes,
                                     va='top', ha='left', fontsize=9, color='white',
                                     bbox=dict(boxstyle='round,pad=0.4', 
                                             facecolor='black', alpha=0.8))
        
        # Statistics panel (left side, below controls)
        self.stats_panel = self.ax.text(0.02, 0.88, '', transform=self.ax.transAxes,
                                      va='top', ha='left', fontsize=8, color='white',
                                      bbox=dict(boxstyle='round,pad=0.3', 
                                              facecolor='darkgreen', alpha=0.85))
        
    def setup_animation_controls(self):
        """Configure animation controls with speeds 0.1x-10x"""
        self.current_frame = 0
        self.total_frames = len(self.df) if self.df is not None else 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.max_playback_speed = 10.0  # Maximum playback speed (10x)
        self.min_speed = 0.1            # Minimum playback speed (0.1x)
        
        # Connect keyboard events
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
    def get_player_zone(self, x, y):
        """Determine the current player zone in the indoor area"""
        # === ZONES FOR INDOOR AREA ===
        # Verify if it is within the valid area
        if not (-1.0 <= x <= 7.0 and -1.0 <= y <= 8.5):
            return "OUTSIDE THE AREA"
        
        # Specific zones for the indoor area (10.6m x 7.35m)
        if y >= 5.5:
            return "NORTH ZONE"
        elif y <= 1.8:
            return "SOUTH ZONE"
        elif x >= 4.0:
            return "EAST ZONE"
        elif x <= 2.0:
            return "WEST ZONE"
        elif 2.0 <= x <= 4.0 and 1.8 <= y <= 5.5:
            return "CENTER ZONE"
        else:
            return "INDOOR AREA"
    
    def calculate_speed(self, frame_idx):
        """Calculate instantaneous speed with realistic limits"""
        if self.df is None or frame_idx == 0:
            return 0.0
            
        current_row = self.df.iloc[frame_idx]
        prev_row = self.df.iloc[frame_idx - 1]
        
        # Euclidean distance
        dx = current_row['x'] - prev_row['x'] 
        dy = current_row['y'] - prev_row['y']
        distance = np.sqrt(dx**2 + dy**2)
        
        # Elapsed time
        dt = (current_row['timestamp'] - prev_row['timestamp']).total_seconds()
        
        # Prevent division by zero
        if dt == 0 or dt <= 0:
            return 0.0
            
        speed = distance / dt  # m/s
        
        # === CORRECCIÓN: Limitar velocidades físicamente imposibles ===
        # Velocidad máxima humana realista indoor: 8 m/s (incluye margen)
        max_realistic_speed = 8.0
        
        if speed > max_realistic_speed:
            # Warning only for extreme cases (>2x limit)
            if speed > max_realistic_speed * 2 and self.verbose_debug:
                print(f"   [SPEED WARNING] Unrealistic speed detected: {speed:.1f} m/s → limited to {max_realistic_speed} m/s")
            speed = max_realistic_speed
        
        # Suavizado simple con frame anterior para evitar picos
        if hasattr(self, '_last_calculated_speed') and self._last_calculated_speed is not None:
            # Evitar cambios bruscos >50% entre frames consecutivos
            speed_change_ratio = abs(speed - self._last_calculated_speed) / max(self._last_calculated_speed, 0.1)
            if speed_change_ratio > 0.5:
                # Suavizar cambio brusco
                speed = 0.7 * self._last_calculated_speed + 0.3 * speed
        
        # Almacenar para próximo frame
        self._last_calculated_speed = speed
        
        return speed
    
    def update_frame(self, frame_idx):
        """Actualizar visualización para el frame actual"""
        if self.df is None or len(self.df) == 0:
            return []
            
        if frame_idx >= self.total_frames:
            frame_idx = self.total_frames - 1
            
        # Datos del frame actual
        current_data = self.df.iloc[frame_idx]
        x, y = current_data['x'], current_data['y']
        timestamp = current_data['timestamp']
        
        # === ACTUALIZAR JUGADOR ===
        # Posición del jugador
        self.player_dot.set_data([x], [y])
        
        # Número del jugador (sigue al jugador)
        self.player_number.set_position((x, y))
        
        # === ACTUALIZAR TRAYECTORIA COMPLETA (desde inicio hasta posición actual) ===
        if not self.skip_trail:
            # Mostrar TODA la trayectoria desde el inicio hasta el frame actual
            trail_data = self.df.iloc[0:frame_idx + 1]
            
            if len(trail_data) > 1:
                # Trayectoria principal completa
                self.trail_line.set_data(trail_data['x'], trail_data['y'])
                
                # Sombra de la trayectoria completa (solo si no está optimizado)
                if self.trail_shadow:
                    self.trail_shadow.set_data(trail_data['x'], trail_data['y'])
                
                # Puntos de trayectoria completa con degradado (solo si no está optimizado)
                if self.trail_dots:
                    self.trail_dots.set_data(trail_data['x'], trail_data['y'])
        else:
            # Modo optimización: trayectoria completa pero simplificada
            trail_data = self.df.iloc[0:frame_idx + 1]
            if len(trail_data) > 1:
                self.trail_line.set_data(trail_data['x'], trail_data['y'])
        
        # === CALCULAR VELOCIDAD Y DIRECCIÓN ===
        speed = self.calculate_speed(frame_idx)
        
        # Indicador visual de velocidad (DESACTIVADO para máxima fluidez)
        # speed_radius = min(3.0, speed * 0.4)  # Radio máximo 3m
        # if self.speed_indicator:
        #     self.speed_indicator.center = (x, y)
        #     self.speed_indicator.radius = speed_radius
        
        # === ZONA ACTUAL ===
        zone = self.get_player_zone(x, y)
        self.current_zone.set_text(zone)
        
        # Cambiar color de la zona según el área
        if "ÁREA" in zone:
            zone_color = 'red'
            zone_edge = 'yellow'
        elif "DEFENSA" in zone:
            zone_color = 'blue'
            zone_edge = 'lightblue'
        elif "ATAQUE" in zone:
            zone_color = 'orangered'
            zone_edge = 'orange'
        elif "CENTRO" in zone or "MEDIO" in zone:
            zone_color = 'green'
            zone_edge = 'lightgreen'
        else:
            zone_color = 'black'
            zone_edge = 'yellow'
        
        self.current_zone.set_bbox(dict(boxstyle='round,pad=0.5', 
                                      facecolor=zone_color, alpha=0.85,
                                      edgecolor=zone_edge, linewidth=1.5))
        
        # === MAPA DE CALOR ===
        # Optimización: Eliminado almacenamiento en memoria - datos disponibles en self.df
        
        # === ESTADÍSTICAS AVANZADAS ===
        elapsed_time = (timestamp - self.df['timestamp'].iloc[0]).total_seconds()
        progress = (frame_idx / self.total_frames) * 100
        
        # === OPTIMIZACIÓN: Usar distancia acumulativa precalculada ===
        total_distance = self.df['cum_dist'].iloc[frame_idx] if frame_idx < len(self.df) else 0
        
        # Speed classification (ASCII compatible icons)
        if speed < 1.0:
            speed_class = "[WALK] WALKING"
        elif speed < 3.0:
            speed_class = "[JOG]  JOGGING"
        elif speed < 5.0:
            speed_class = "[RUN]  RUNNING"
        else:
            speed_class = "[SPRINT] SPRINT"
        
        stats_text = (f"TIME {elapsed_time:.1f}s | POS({x:.1f},{y:.1f}) | {speed_class} {speed:.1f}m/s | DIST{total_distance:.0f}m | {frame_idx + 1}/{self.total_frames} | {progress:.0f}% | SPD{self.playback_speed:.1f}x")
        
        self.stats_panel.set_text(stats_text)
        
        # === TÍTULO DINÁMICO ===
        title_color = 'lightgreen' if self.is_playing else 'orange'
        status_icon = 'PLAY' if self.is_playing else 'PAUSE'
        
        self.ax.set_title(f"{status_icon} {timestamp.strftime('%H:%M:%S.%f')[:-3]}",
                         fontsize=12, fontweight='bold', color=title_color,
                         bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
        
        return [element for element in [
            self.player_dot, self.player_number, self.trail_line, 
            self.trail_shadow, self.trail_dots, self.current_zone, 
            self.stats_panel, self.speed_indicator
        ] if element is not None]
    
    def animate(self, frame):
        """Función de animación principal con control de velocidad mejorado"""
        if self.is_playing:
            # --- NUEVO CONTROL DE VELOCIDAD ---
            if self.playback_speed >= 1.0:
                frames_to_advance = int(round(self.playback_speed))
                self.current_frame = min(self.current_frame + frames_to_advance, self.total_frames - 1)
                # Mantener un intervalo constante (40 ms ≈ 25 FPS)
                if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                    self.anim.event_source.interval = 40
            else:
                # Velocidad más lenta: avanzar 1 frame pero alargar intervalo
                self.current_frame = min(self.current_frame + 1, self.total_frames - 1)
                if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                    slow_interval = int(40 / self.playback_speed)  # Ej.: 0.5x → 80 ms
                    self.anim.event_source.interval = slow_interval
            
            # Pausar automáticamente al final
            if self.current_frame >= self.total_frames - 1:
                self.is_playing = False
                
        return self.update_frame(self.current_frame)
    
    def on_key_press(self, event):
        """Handle keyboard events"""
        if event.key == ' ':  # Space - Play/Pause
            self.is_playing = not self.is_playing
            print(f"Replay: {'Started' if self.is_playing else 'Paused'}")
            
        elif event.key == 'left':  # Left arrow
            self.current_frame = max(0, self.current_frame - 1)
            print(f" Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'right':  # Right arrow
            self.current_frame = min(self.total_frames - 1, self.current_frame + 1)
            print(f" Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'up':  # Up arrow
            self.playback_speed = min(self.max_playback_speed, self.playback_speed + 0.5)
            print(f" Speed: {self.playback_speed:.1f}x")
            # Update animation interval immediately (limited to 60 FPS for slow hardware)
            if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                self.anim.event_source.interval = max(17, int(40 / self.playback_speed))
            # Synchronize slider avoiding recursive callback
            self._sync_slider_safely(self.playback_speed)
            
        elif event.key == 'down':  # Down arrow
            self.playback_speed = max(self.min_speed, self.playback_speed - 0.5)
            print(f" Speed: {self.playback_speed:.1f}x")
            # Update animation interval immediately (limited to 60 FPS for slow hardware)
            if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                self.anim.event_source.interval = max(17, int(40 / self.playback_speed))
            # Synchronize slider avoiding recursive callback
            self._sync_slider_safely(self.playback_speed)
            
        elif event.key == 'r':  # R - Restart
            self.current_frame = 0
            self.is_playing = False
            print(" Replay restarted")
            
        elif event.key == 'q':  # Q - Exit
            print(" Closing replay...")
            plt.close(self.fig)
            
        # Update visualization immediately
        if not self.is_playing:
            self.update_frame(self.current_frame)
            self.fig.canvas.draw()
    
    def start_replay(self):
        """Start the replay system"""
        print("\n Starting UWB Replay System")
        print("=" * 50)
        print("  Use the keys to control the replay:")
        print("   SPACE:   Play/Pause")
        print("   ←/→: Previous/Next frame") 
        print("   ↑/↓: Speed +/-")
        print("   R:  Restart")
        print("   Q:  Exit")
        print("=" * 50)
        
        # Configure animation
        self.anim = FuncAnimation(
            self.fig, self.animate, frames=self.total_frames,
            interval=40,  # 25 FPS = 40ms between frames
            repeat=True, blit=False
        )
        
        # Show replay
        # Manual layout adjustment already done with subplots_adjust to avoid overlaps
        plt.subplots_adjust(left=0.05, right=0.98, bottom=0.12, top=0.94)
        plt.show()

    def setup_interactive_controls(self):
        """Configurar controles interactivos avanzados con slider 0.1x-10x"""
        # Área para controles interactivos (espacio optimizado)
        plt.subplots_adjust(left=0.05, right=0.98, bottom=0.12, top=0.94)
        
        # Slider para velocidad de reproducción (rango 0.1x a 10x)
        ax_speed = plt.axes((0.15, 0.05, 0.35, 0.025))
        self.speed_slider = Slider(ax_speed, 'Velocidad', 0.1, self.max_playback_speed, valinit=1.0)
        self.speed_slider.on_changed(self.update_speed)
        
        # Botón para activar/desactivar filtros (separados más)
        ax_kalman = plt.axes((0.55, 0.05, 0.08, 0.03))
        self.kalman_button = Button(ax_kalman, 'Kalman')
        self.kalman_button.on_clicked(self.toggle_kalman)
        
        # Botón para activar/desactivar ML
        ax_ml = plt.axes((0.65, 0.05, 0.08, 0.03))
        self.ml_button = Button(ax_ml, 'ML Pred')
        self.ml_button.on_clicked(self.toggle_ml)
        
        # Etiqueta de información de controles (pequeña)
        ax_info = plt.axes((0.75, 0.05, 0.22, 0.03))
        ax_info.text(0.5, 0.5, 'Usa teclado para control fino', 
                    ha='center', va='center', fontsize=8, color='gray',
                    transform=ax_info.transAxes)
        ax_info.set_xticks([])
        ax_info.set_yticks([])
        ax_info.patch.set_alpha(0)
        
        # Actualizar colores de botones según estado
        self.update_button_colors()
    
    def _sync_slider_safely(self, new_value):
        """Sincronizar slider evitando callbacks recursivos"""
        if hasattr(self, 'speed_slider'):
            # Método compatible con todas las versiones de matplotlib
            original_eventson = self.speed_slider.eventson
            self.speed_slider.eventson = False
            self.speed_slider.set_val(new_value)
            self.speed_slider.eventson = original_eventson
    
    def update_speed(self, val):
        """
        Actualizar velocidad de reproducción con límites seguros.
        
        Args:
            val: Valor del slider (0.1 a 10.0)
        """
        self.playback_speed = np.clip(val, 0.1, self.max_playback_speed)
        
        # Actualizar intervalo de animación instantáneamente (limitado a 60 FPS para hardware lento)
        if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
            self.anim.event_source.interval = max(17, int(40 / self.playback_speed))
    
    def toggle_kalman(self, event):
        """Activate/deactivate Kalman filter"""
        self.use_kalman_filter = not self.use_kalman_filter
        print(f" Kalman filter: {'Activated' if self.use_kalman_filter else 'Deactivated'}")
        self.update_button_colors()
        
        # === OPTIMIZATION: Only reprocess Kalman if already interpolated data ===
        if self.df is not None and len(self.df) > 0:
            # Keep base data and only reapply Kalman
            self._reapply_kalman_filter()
        else:
            # First processing or invalid data - full reload
            self.apply_advanced_filtering()
    
    def _reapply_kalman_filter(self):
        """Reapply Kalman filter to already interpolated data"""
        if self.df is None:
            return
            
        print(" Reapplying Kalman filter...")
        
        # Reinitialize Kalman filter if activated
        if self.use_kalman_filter:
            first_valid_pos = self.find_first_valid_position()
            if first_valid_pos is not None:
                # OPTIMIZED: Increased process_noise (0.1 -> 0.3) for SPORTS (high reactivity)
                self.kalman_filter = KalmanPositionFilter(
                    initial_pos=first_valid_pos,
                    process_noise=0.3,
                    measurement_noise=0.1
                )
                
                # Reapply Kalman to existing positions
                dt = self.animation_step_ms / 1000.0
                for i in range(len(self.df)):
                    pos = [self.df.iloc[i]['x'], self.df.iloc[i]['y']]
                    filtered_pos = self.kalman_filter.process(pos, dt)
                    self.df.iloc[i, self.df.columns.get_loc('x')] = filtered_pos[0]
                    self.df.iloc[i, self.df.columns.get_loc('y')] = filtered_pos[1]
        else:
            # If Kalman is deactivated, we need original data - full reload
            self.apply_advanced_filtering()
    
    def toggle_ml(self, event):
        """Activate/deactivate ML prediction"""
        self.use_ml_prediction = not self.use_ml_prediction
        print(f"ML prediction: {'Activated' if self.use_ml_prediction else 'Deactivated'}")
        self.update_button_colors()
        
        # === OPTIMIZATION: Only recalculate if really necessary ===
        # ML only affects gap interpolation, not already valid data
        # Only reload if there are large changes in interpolation
        print(" ML configuration updated (effect on upcoming signal gaps)")
        
        # Reset training timestamp to force re-training
        self._last_gpr_train_ms = -1
    
    def update_button_colors(self):
        """Update button and text colors according to state"""
        # Background colors
        kalman_color = 'lightgreen' if self.use_kalman_filter else 'lightcoral'
        ml_color = 'lightblue' if self.use_ml_prediction else 'lightcoral'
        
        # Text colors (better contrast for readability)
        kalman_text_color = 'darkgreen' if self.use_kalman_filter else 'darkred'
        ml_text_color = '#002b5c' if self.use_ml_prediction else 'darkred'  # Darker blue
        
        # Update button background color
        self.kalman_button.ax.set_facecolor(kalman_color)
        self.ml_button.ax.set_facecolor(ml_color)
        
        # Update text color for maximum clarity
        self.kalman_button.label.set_color(kalman_text_color)
        self.ml_button.label.set_color(ml_text_color)
        
        # Refresh UI immediately
        self.fig.canvas.draw_idle()

def generate_movement_report(csv_file):
    """Generate movement analysis report"""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate statistics
    total_time = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    
    # Early validation: avoid division by zero
    if total_time <= 0:
        print("\n  WARNING: Data duration insufficient for analysis")
        print("   Timestamps do not have a valid temporal range")
        return
    
    # === OPTIMIZACIÓN: Cálculo eficiente de distancias ===
    # Usar numpy hypot para mejor rendimiento
    x_diff = df['x'].diff()
    y_diff = df['y'].diff()
    step_distances = np.hypot(x_diff, y_diff)
    step_distances[0] = 0  # First distance is 0
    
    total_distance = step_distances.sum()
    avg_speed = total_distance / total_time  # We already validated total_time > 0
    
    # === CORRECTION: Calculate realistic speeds ===
    # Calculate real frequency and frame-by-frame speeds
    freq = len(df) / total_time
    
    # Frame-by-frame speeds with realistic limit
    frame_speeds = step_distances * freq  # speed per frame
    
    # Apply realistic physical limit
    max_realistic_speed = 8.0  # m/s - human indoor limit
    frame_speeds = np.clip(frame_speeds, 0, max_realistic_speed)
    
    max_speed = frame_speeds.max() if len(frame_speeds) > 0 else 0
    
    # === REALISM WARNINGS ===
    original_max_speed = (step_distances * freq).max() if len(step_distances) > 0 else 0
    if original_max_speed > max_realistic_speed:
        print(f"\n  CORRECTED SPEEDS:")
        print(f"   Original maximum speed: {original_max_speed:.1f} m/s (unrealistic)")
        print(f"   Corrected maximum speed: {max_speed:.1f} m/s (limited)")
        print(f"   Speeds >8 m/s were limited by physical realism")
    
    print(f"\n MOVEMENT ANALYSIS REPORT")
    print("=" * 50)
    print(f"  Total duration: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f" Total distance: {total_distance:.1f} meters")
    print(f" Average speed: {avg_speed:.2f} m/s")
    print(f" Maximum speed: {max_speed:.2f} m/s")
    print(f" Total frames: {len(df)}")
    print(f" Sampling frequency: ~{len(df)/total_time:.1f} Hz")
    
    # === REALISM ANALYSIS ===
    if avg_speed > 4.0:
        print(f"  WARNING: Average speed too high ({avg_speed:.1f} m/s)")
        print("   Typical indoor speed: 1.5-3.0 m/s average")
    elif avg_speed < 0.5:
        print(f"  INFO: Low average speed ({avg_speed:.1f} m/s) - slow or static movement")
    else:
        print(f" Realistic average speed ({avg_speed:.1f} m/s)")
    
    if max_speed > 7.0:
        print(f"  WARNING: Maximum speed too high ({max_speed:.1f} m/s)")
    else:
        print(f" Realistic maximum speed ({max_speed:.1f} m/s)")
    
    # === PACKET LOSS ANALYSIS ===
    print("\n PACKET LOSS ANALYSIS (per Anchor)")
    print("-" * 50)
    anchor_cols = [col for col in df.columns if 'anchor_' in col and '_dist' in col]
    if anchor_cols:
        for col in anchor_cols:
            anchor_id = col.replace('anchor_', '').replace('_dist', '')
            total_samples = len(df)
            lost_samples = (df[col] == 0).sum()
            loss_rate = (lost_samples / total_samples) * 100
            
            status = "OK"
            if loss_rate > 50: status = "CRITICAL"
            elif loss_rate > 20: status = "WARNING"
            
            print(f" Anchor {anchor_id}: {loss_rate:5.1f}% Loss ({lost_samples}/{total_samples}) - {status}")
    else:
        print(" No anchor distance data found in CSV")
    
    print("=" * 50)

def select_replay_file_interactive():
    """
    Interactive file selection for replay from uwb_data
    """
    
    print("\n SELECT REPLAY FILE FOR UWB")
    print("=" * 70)
    print("File location:")
    print(f"     Current directory: {os.getcwd()}")
    print(f"    uwb_data/: UWB position files")
    print("=" * 70)
    
    # Search for uwb_positions_ in uwb_data/
    data_files = []
    
    if os.path.exists("uwb_data"):
        for file_path in glob.glob("uwb_data/uwb_positions_*.csv"):
            if os.path.exists(file_path):
                data_files.append(file_path)
    
    if not data_files:
        print("No UWB position files found")
        print("Make sure you have uwb_positions_*.csv files in the 'uwb_data/' folder")
        return None
    
    # Sort by modification date (most recent first)
    data_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    print(f"\nAVAILABLE FILES ({len(data_files)} found):")
    print("=" * 70)
    
    for i, file_path in enumerate(data_files, 1):
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / 1024
            mod_time = os.path.getmtime(file_path)
            mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
            
            # Extract timestamp from file name
            timestamp_part = file_name.replace("uwb_positions_", "").replace(".csv", "")
            
            if file_size > 15:
                quality_desc = "RECOMMENDED"
            elif file_size > 5:
                quality_desc = "GOOD"
            else:
                quality_desc = "SMALL"
            
            print(f"{i:2d}. {file_name}")
            print(f"     {file_size:7.1f}KB | {mod_date} | {quality_desc}")
            print()
            
        except Exception as e:
            print(f"{i:2d}. Error reading file: {file_path} - {e}")
    
    print("0. Cancel")
    
    while True:
        try:
            choice = input(f"\nSelect a file (1-{len(data_files)}) or 0 to cancel: ").strip()
            
            if choice == '0':
                print("Operation cancelled")
                return None
            
            file_idx = int(choice) - 1
            if 0 <= file_idx < len(data_files):
                selected_file = data_files[file_idx]
                
                if not os.path.exists(selected_file):
                    print(f"Error: The selected file does not exist: {selected_file}")
                    continue
                
                file_size = os.path.getsize(selected_file) / 1024
                
                print(f"SELECTED FILE:")
                print(f"    File: {os.path.basename(selected_file)}")
                print(f"    Size: {file_size:.1f} KB")
                print(f"    Full path: {os.path.abspath(selected_file)}")
                
                return selected_file
            else:
                print(f"Invalid number. Enter a number between 1 and {len(data_files)}")
                
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("Operation cancelled")
            return None


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='UWB Replay System for Indoor Localization Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python movement_replay.py                                    # Interactive selection
  python movement_replay.py uwb_data/uwb_positions_xxx.csv    # Specific file
  python movement_replay.py --report uwb_data/uwb_positions_xxx.csv  # Only report
  python movement_replay.py --optimize-memory large_data.csv  # Memory optimization
        """
    )
    
    parser.add_argument('csv_file', nargs='?', 
                       help='CSV file with movement data (optional - if not specified, interactive selection)')
    parser.add_argument('--report', action='store_true',
                       help='Show only analysis report without replay')
    parser.add_argument('--optimize-memory', action='store_true',
                       help='Optimize memory for large datasets (>1M rows)')
    parser.add_argument('--skip-trail', action='store_true',
                       help='Omit real-time trail to reduce memory')
    parser.add_argument('--verbose-debug', action='store_true',
                       help='Show all GPR debug logs (can generate spam)')
    
    args = parser.parse_args()
    
    # File selection
    if args.csv_file:
        # File specified by parameter
        if not os.path.exists(args.csv_file):
            print(f"Error: File '{args.csv_file}' not found")
            return
        selected_file = args.csv_file
    else:
        selected_file = select_replay_file_interactive()
        if selected_file is None:
            return
    
    try:
        if args.report:
            generate_movement_report(selected_file)
        else:
            generate_movement_report(selected_file)
            
            replay_system = UWBHexagonReplaySystem(selected_file, args.optimize_memory, args.skip_trail, args.verbose_debug)
            replay_system.start_replay()
            
    except KeyboardInterrupt:
        print("\nReplay system cancelled by user")
    except Exception as e:
        print(f"Error during replay: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()