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
import os
import glob
from datetime import datetime, timedelta
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import WhiteKernel, Matern
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
            print(f"[DEBUG GPR] Entrenamiento rechazado: {len(timestamps)}/{self.min_samples_required} muestras válidas")
            return False
        
        # Filtrar posiciones válidas (excluir filas con x o y nulos)
        valid_indices = ~np.any(np.isnan(positions), axis=1)
        valid_timestamps = timestamps[valid_indices]
        valid_positions = positions[valid_indices]
        
        if len(valid_timestamps) < self.min_samples_required:
            print(f"[DEBUG GPR] Entrenamiento rechazado: {len(valid_timestamps)}/{self.min_samples_required} muestras válidas")
            self.is_trained = False
            return False
        
        # Normalizar timestamps
        self.min_ts = min(valid_timestamps)
        self.max_ts = max(valid_timestamps)
        ts_range = self.max_ts - self.min_ts
        
        if ts_range <= 0:
            print(f"[DEBUG GPR] Entrenamiento rechazado: rango temporal insuficiente ({ts_range})")
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
                # Silenciar ConvergenceWarning de GPR cuando hay pocos datos únicos
                # Nota: puede causar overhead en hardware lento con muestras próximas
                warnings.simplefilter("ignore")
                self.x_model.fit(norm_timestamps, valid_positions[:, 0])
                self.y_model.fit(norm_timestamps, valid_positions[:, 1])
                
            self.is_trained = True
            print(f"[DEBUG GPR] Entrenado exitosamente con {len(valid_timestamps)} muestras")
            return True
            
        except Exception as e:
            print(f"[DEBUG GPR] Error en entrenamiento: {e}")
            self.is_trained = False
            return False
    
    def predict(self, target_timestamps, max_speed=7.0):
        """
        Predice posiciones para timestamps objetivo usando GPR entrenado.
        
        Args:
            target_timestamps: Lista de timestamps objetivo en millisegundos
            max_speed: Velocidad máxima permitida en m/s (default: 7.0 m/s para fútbol sala)
            
        Returns:
            List[[x, y]]: Lista de posiciones predichas, o None/[] si error
        """
        if not self.is_trained or self.x_model is None or self.y_model is None:
            return None
        
        if len(target_timestamps) == 0:
            return []
        
        # Normalizar timestamps objetivo
        ts_range = self.max_ts - self.min_ts
        
        # Validación adicional: evitar división por cero si solo hay un timestamp
        if ts_range == 0:
            return []
        
        norm_ts = (np.array(target_timestamps) - self.min_ts) / ts_range
        norm_ts = norm_ts.reshape(-1, 1)
        
        # Predicción con GPR
        pred_x, _ = self.x_model.predict(norm_ts, return_std=True)
        pred_y, _ = self.y_model.predict(norm_ts, return_std=True)
        
        # Asegurar que las predicciones sean arrays
        pred_x = np.array(pred_x).flatten()
        pred_y = np.array(pred_y).flatten()
        
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
    def __init__(self, csv_file, optimize_memory=False, skip_trail=False):
        """
        Inicializar el sistema de replay avanzado
        
        Args:
            csv_file: Archivo CSV con datos de movimiento
            optimize_memory: Flag para optimizar memoria en datasets grandes (>1M filas)
            skip_trail: Flag para omitir trayectoria en tiempo real (reduce memoria)
        """
        print(" Cargando Sistema Avanzado de Replay UWB...")
        
        # Configuración avanzada
        self.use_kalman_filter = True
        self.use_ml_prediction = True
        self.optimize_memory = optimize_memory
        self.skip_trail = skip_trail
        
        # Ajustar parámetros según optimización de memoria
        if optimize_memory:
            self.trail_length = 50  # Reducir trail para datasets grandes
            print(" Modo optimización de memoria activado (trail reducido)")
        else:
            self.trail_length = 100
            
        self.animation_step_ms = 20  # 50 FPS
        self.max_player_speed = 7.0  # m/s (velocidad sprint fútbol sala - límite físico)
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
            # === OPTIMIZACIÓN DE MEMORIA: Detección de datasets grandes ===
            file_size_mb = os.path.getsize(csv_file) / (1024 * 1024)
            print(f" Tamaño del archivo: {file_size_mb:.1f} MB")
            
            if file_size_mb > 20:  # Datasets >20MB pueden generar ~100MB+ en memoria
                print("⚠️  ADVERTENCIA: Dataset grande detectado")
                print(f"   Archivo: {file_size_mb:.1f} MB → Memoria estimada: ~{file_size_mb * 5:.0f} MB")
                print("   Considera usar --optimize-memory para datasets >50MB")
                
                if not self.optimize_memory and file_size_mb > 50:
                    print("🔴 RECOMENDACIÓN CRÍTICA: Activa optimización de memoria")
                    print("   python movement_replay.py --optimize-memory [archivo]")
            
            self.original_df = pd.read_csv(csv_file)
            
            # Verificar número de filas para memoria
            num_rows = len(self.original_df)
            print(f" Registros originales: {num_rows:,}")
            
            if num_rows > 500_000:  # >500k filas pueden usar mucha RAM
                estimated_memory_gb = (num_rows * 5) / 1_000_000  # Estimación conservadora
                print(f"⚠️  Memoria estimada: ~{estimated_memory_gb:.1f} GB después del procesamiento")
                
                if num_rows > 1_000_000 and not self.optimize_memory:
                    print("🔴 DATASET CRÍTICO: >1M filas. Recomendado reiniciar con --optimize-memory")
            
            self.original_df['timestamp'] = pd.to_datetime(self.original_df['timestamp'])
            
            # Validar datos
            required_columns = ['timestamp', 'x', 'y', 'tag_id']
            missing_cols = [col for col in required_columns if col not in self.original_df.columns]
            if missing_cols:
                raise ValueError(f"Columnas faltantes: {missing_cols}")
            
            print(f" Datos originales cargados: {len(self.original_df)} registros")
            
            # Aplicar filtros avanzados
            self.apply_advanced_filtering()
            
            if self.df is not None and len(self.df) > 0:
                print(f" Duración: {(self.df['timestamp'].iloc[-1] - self.df['timestamp'].iloc[0]).total_seconds():.1f} segundos")
                print(f" Rango X: {self.df['x'].min():.1f} - {self.df['x'].max():.1f}m")
                print(f" Rango Y: {self.df['y'].min():.1f} - {self.df['y'].max():.1f}m")
            else:
                print(" No se pudieron procesar los datos correctamente")
                sys.exit(1)
                
        except Exception as e:
            print(f" Error cargando datos: {e}")
            sys.exit(1)
    
    def apply_advanced_filtering(self):
        """Aplicar filtros avanzados: Kalman + ML + Interpolación"""
        if self.original_df is None:
            print(" No hay datos originales para procesar")
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
            print(f" Filtros aplicados: {len(self.df)} frames interpolados")
        else:
            print(" Error: No se pudieron aplicar los filtros")
    
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
        
        # Crear timeline completo con step fijo (incluir último instante)
        start_ms = 0
        end_ms = timestamps_ms[-1]
        full_timeline = np.arange(start_ms, end_ms + self.animation_step_ms, self.animation_step_ms)
        
        # Preparar datos para interpolación
        positions = self.original_df[['x', 'y']].values
        
        # Identificar gaps grandes que requieren predicción ML
        interpolated_positions = []
        
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
                
            else:
                # Gap grande - usar predicción ML si está disponible
                if (self.use_ml_prediction and 
                    len(interpolated_positions) >= 10):
                    
                    # === OPTIMIZACIÓN: Usar índices directos en lugar de slice costoso ===
                    # Entrenar con datos recientes (evitar slice en arrays grandes)
                    recent_positions = np.array(interpolated_positions[-10:])
                    
                    # Calcular índices directos para evitar slice costoso de full_timeline
                    current_idx = len(interpolated_positions)
                    start_idx = current_idx - 10
                    recent_timestamps = np.array([full_timeline[i] for i in range(start_idx, current_idx)])
                    
                    # Verificar que hay al least 5 timestamps distintos para GPR
                    unique_timestamps = len(np.unique(recent_timestamps))
                    if unique_timestamps < 5:
                        print(f"[DEBUG GPR] Entrenamiento omitido: solo {unique_timestamps}/5 timestamps únicos")
                        # Fallback a interpolación lineal si pocos timestamps únicos
                        pos = self.linear_interpolation_fallback(
                            interpolated_positions, target_ms
                        )
                        interpolated_positions.append(pos)
                        continue
                    
                    if self.trajectory_predictor.train(recent_timestamps, recent_positions):
                        predictions = self.trajectory_predictor.predict([target_ms], self.max_player_speed)
                        if predictions:
                            pos = predictions[0]
                        else:
                            # Fallback a interpolación lineal
                            pos = self.linear_interpolation_fallback(
                                interpolated_positions, target_ms
                            )
                    else:
                        pos = self.linear_interpolation_fallback(
                            interpolated_positions, target_ms
                        )
                else:
                    # Interpolación lineal simple
                    pos = self.linear_interpolation_fallback(
                        interpolated_positions, target_ms
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
        
        # === OPTIMIZACIÓN: Cálculo previo de distancias ===
        # Calcular distancias step by step usando numpy (más eficiente)
        x_diff = interpolated_df['x'].diff()
        y_diff = interpolated_df['y'].diff()
        step_distances = np.hypot(x_diff, y_diff)
        step_distances[0] = 0  # Primera distancia es 0 (sin diferencia previa)
        interpolated_df['step_dist'] = step_distances
        # Distancia acumulativa para acceso O(1) en update_frame
        interpolated_df['cum_dist'] = interpolated_df['step_dist'].cumsum()
        
        return interpolated_df
    
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
        """Configurar la visualización de la cancha"""
        # Crear figura con tamaño optimizado
        self.fig, self.ax = plt.subplots(figsize=(18, 12))
        
        # Verificar si el manager existe antes de intentar establecer el título
        try:
            if hasattr(self.fig.canvas, 'manager') and self.fig.canvas.manager is not None:
                self.fig.canvas.manager.set_window_title(' Sistema de Replay UWB - Fútbol Sala Profesional')
        except:
            pass  # Ignorar si no se puede establecer el título
        
        # Configurar cancha de fútbol sala (40x20m) con márgenes amplios
        self.ax.set_xlim(-4, 44)
        self.ax.set_ylim(-6, 24)  # Mucho más espacio abajo para zona actual
        self.ax.set_aspect('equal')
        
        # Color de fondo - Pabellón deportivo
        self.ax.set_facecolor('#1a1a2e')  # Azul oscuro pabellón
        
        # Dibujar fondo de la cancha con degradado
        self.draw_futsal_court_professional()
        
        # Dibujar anclas UWB
        self.draw_uwb_anchors()
        
        # Configurar elementos dinámicos
        self.setup_dynamic_elements()
        
        # Panel de información
        self.setup_info_panel()
    
    def draw_futsal_court_professional(self):
        """Dibujar cancha de fútbol sala profesional con todos los elementos reglamentarios"""
        
        # === SUPERFICIE DE JUEGO ===
        # Fondo principal de la cancha (parquet/cemento pulido)
        court_surface = patches.Rectangle((0, 0), 40, 20, linewidth=0,
                                        facecolor='#8B7355', alpha=0.9)  # Color parquet
        self.ax.add_patch(court_surface)
        
        # Efecto de brillo en el centro (como parquet pulido)
        center_shine = patches.Ellipse((20, 10), 25, 12, linewidth=0,
                                     facecolor='#A0926B', alpha=0.3)
        self.ax.add_patch(center_shine)
        
        # === LÍNEAS REGLAMENTARIAS ===
        # Perímetro de la cancha (40x20m) - Línea más gruesa
        court = patches.Rectangle((0, 0), 40, 20, linewidth=4, 
                                edgecolor='white', facecolor='none')
        self.ax.add_patch(court)
        
        # Línea central
        self.ax.plot([20, 20], [0, 20], 'white', linewidth=3)
        
        # Círculo central (radio 3m) - FIFA
        center_circle = patches.Circle((20, 10), 3, linewidth=3, 
                                     edgecolor='white', facecolor='none')
        self.ax.add_patch(center_circle)
        
        # Punto central
        self.ax.plot(20, 10, 'wo', markersize=8)
        
        # === ÁREAS DE PORTERÍA ===
        # Área de portería izquierda (semicírculo 6m)
        penalty_left = patches.Wedge((0, 10), 6, -90, 90, linewidth=3,
                                   edgecolor='white', facecolor='none')
        self.ax.add_patch(penalty_left)
        
        # Área de portería derecha
        penalty_right = patches.Wedge((40, 10), 6, 90, 270, linewidth=3,
                                    edgecolor='white', facecolor='none')
        self.ax.add_patch(penalty_right)
        
        # === PORTERÍAS PROFESIONALES ===
        # Portería izquierda (3x2m) - Estructura 3D
        # Postes
        self.ax.plot([0, 0], [8.5, 11.5], 'white', linewidth=6)  # Poste más realista
        
        # Estructura de la portería (efecto 3D)
        goal_left_back = patches.Rectangle((-1.2, 8.5), 1.2, 3, linewidth=2,
                                         edgecolor='silver', facecolor='#f0f0f0', alpha=0.8)
        self.ax.add_patch(goal_left_back)
        
        # Red (efecto visual)
        for i in range(9, 12):
            self.ax.plot([-1.2, 0], [i, i], 'gray', linewidth=0.5, alpha=0.6)
        for i in range(-12, 1, 2):
            self.ax.plot([i/10, i/10], [8.5, 11.5], 'gray', linewidth=0.5, alpha=0.6)
        
        # Portería derecha (3x2m)
        self.ax.plot([40, 40], [8.5, 11.5], 'white', linewidth=6)
        
        goal_right_back = patches.Rectangle((40, 8.5), 1.2, 3, linewidth=2,
                                          edgecolor='silver', facecolor='#f0f0f0', alpha=0.8)
        self.ax.add_patch(goal_right_back)
        
        # Red portería derecha
        for i in range(9, 12):
            self.ax.plot([40, 41.2], [i, i], 'gray', linewidth=0.5, alpha=0.6)
        for i in range(0, 13, 2):
            self.ax.plot([40 + i/10, 40 + i/10], [8.5, 11.5], 'gray', linewidth=0.5, alpha=0.6)
        
        # === PUNTOS DE PENALTI ===
        # Punto de penalti 6 metros
        self.ax.plot(6, 10, 'wo', markersize=10)
        self.ax.plot(34, 10, 'wo', markersize=10)
        
        # Punto de doble penalti 10 metros
        self.ax.plot(10, 10, 'wo', markersize=8)
        self.ax.plot(30, 10, 'wo', markersize=8)
        
        # === ESQUINAS REGLAMENTARIAS ===
        # Cuartos de círculo radio 25cm (FIFA)
        corners = [(0, 0), (0, 20), (40, 0), (40, 20)]
        for x, y in corners:
            if x == 0 and y == 0:  # Esquina inferior izquierda
                corner = patches.Wedge((x, y), 0.25, 0, 90, linewidth=2,
                                     edgecolor='white', facecolor='none')
            elif x == 0 and y == 20:  # Esquina superior izquierda
                corner = patches.Wedge((x, y), 0.25, 270, 360, linewidth=2,
                                     edgecolor='white', facecolor='none')
            elif x == 40 and y == 0:  # Esquina inferior derecha
                corner = patches.Wedge((x, y), 0.25, 90, 180, linewidth=2,
                                     edgecolor='white', facecolor='none')
            else:  # Esquina superior derecha
                corner = patches.Wedge((x, y), 0.25, 180, 270, linewidth=2,
                                     edgecolor='white', facecolor='none')
            self.ax.add_patch(corner)
        
        # === ELEMENTOS ADICIONALES FÚTBOL SALA ===
        
        # Línea de saque (línea discontinua a 3m de cada portería)
        # Izquierda
        for i in range(3, 18, 2):
            self.ax.plot([3, 3], [i, i+0.8], 'white', linewidth=1.5, alpha=0.7)
        # Derecha  
        for i in range(3, 18, 2):
            self.ax.plot([37, 37], [i, i+0.8], 'white', linewidth=1.5, alpha=0.7)
        
        # === BANQUILLOS Y ÁREA TÉCNICA ===
        # Banquillo equipo local (lado izquierdo)
        bench_local = patches.Rectangle((-3.5, 7), 2.5, 6, linewidth=2,
                                      edgecolor='blue', facecolor='lightblue', alpha=0.7)
        self.ax.add_patch(bench_local)
        self.ax.text(-2.25, 10, 'EQUIPO\nLOCAL', ha='center', va='center',
                    fontsize=8, fontweight='bold', color='darkblue')
        
        # Banquillo equipo visitante (lado derecho)
        bench_visit = patches.Rectangle((41, 7), 2.5, 6, linewidth=2,
                                      edgecolor='red', facecolor='lightcoral', alpha=0.7)
        self.ax.add_patch(bench_visit)
        self.ax.text(42.25, 10, 'EQUIPO\nVISITANTE', ha='center', va='center',
                    fontsize=8, fontweight='bold', color='darkred')
        
        # Área técnica (línea de banda)
        # Local
        self.ax.plot([-0.1, -0.1], [5, 15], 'blue', linewidth=3, alpha=0.8)
        # Visitante
        self.ax.plot([40.1, 40.1], [5, 15], 'red', linewidth=3, alpha=0.8)
        
        # === ZONAS DE ANÁLISIS DEPORTIVO (sutiles) ===
        # Zona defensiva local
        defense_local = patches.Rectangle((0, 0), 13.33, 20, linewidth=0,
                                        facecolor='lightblue', alpha=0.1)
        self.ax.add_patch(defense_local)
        
        # Zona media
        middle_zone = patches.Rectangle((13.33, 0), 13.34, 20, linewidth=0,
                                      facecolor='yellow', alpha=0.1)
        self.ax.add_patch(middle_zone)
        
        # Zona ofensiva
        offense_zone = patches.Rectangle((26.67, 0), 13.33, 20, linewidth=0,
                                       facecolor='lightcoral', alpha=0.1)
        self.ax.add_patch(offense_zone)
        
        # === ILUMINACIÓN DEL PABELLÓN (efecto) ===
        # Focos principales (4 esquinas)
        spotlight_positions = [(-2, -2), (-2, 22), (42, -2), (42, 22)]
        for x, y in spotlight_positions:
            spotlight = patches.Circle((x, y), 0.8, linewidth=2,
                                     edgecolor='yellow', facecolor='lightyellow', alpha=0.6)
            self.ax.add_patch(spotlight)
    
    def draw_uwb_anchors(self):
        """Dibujar posiciones de anclas UWB con diseño mejorado"""
        anchors = {
            'A10': (-1, -1, 'red', ''),        # Esquina Suroeste
            'A20': (-1, 21, 'blue', '🔵'),       # Esquina Noroeste  
            'A30': (41, -1, 'green', ''),      # Esquina Sureste
            'A40': (41, 21, 'orange', '🟠'),     # Esquina Noreste
            'A50': (20, -1, 'purple', '🟣')      # Centro campo Sur
        }
        
        for anchor_id, (x, y, color, emoji) in anchors.items():
            # Círculo de cobertura (sutil)
            coverage = patches.Circle((x, y), 15, linewidth=1,
                                    edgecolor=color, facecolor='none', 
                                    alpha=0.2, linestyle='--')
            self.ax.add_patch(coverage)
            
            # Ancla principal (más grande y visible)
            self.ax.plot(x, y, 's', color=color, markersize=16, 
                        markeredgecolor='white', markeredgewidth=3, zorder=15)
            
            # Símbolo UWB
            self.ax.plot(x, y, marker='*', color='white', markersize=8, zorder=16)
            
            # Etiqueta mejorada
            self.ax.annotate(f'{emoji} {anchor_id}', (x, y), xytext=(8, 8), 
                           textcoords='offset points', color='white',
                           fontsize=11, fontweight='bold', zorder=17,
                           bbox=dict(boxstyle='round,pad=0.5', 
                                   facecolor=color, alpha=0.9,
                                   edgecolor='white', linewidth=1))
    
    def setup_dynamic_elements(self):
        """Configurar elementos que cambian durante la animación"""
        # === JUGADOR PRINCIPAL ===
        # Jugador con diseño mejorado (camiseta + número)
        self.player_dot, = self.ax.plot([], [], 'o', color='#FFD700', markersize=18, 
                                       markeredgecolor='#FF4500', markeredgewidth=3,
                                       label='Jugador', zorder=20)
        
        # Número del jugador
        self.player_number = self.ax.text(0, 0, '7', ha='center', va='center',
                                        fontsize=10, fontweight='bold', color='white', zorder=21)
        
        # === TRAYECTORIA AVANZADA (optimizada según memoria) ===
        if not self.skip_trail:
            # Trayectoria principal con degradado
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.8, linewidth=3,
                                           label='Trayectoria', zorder=10)
            
            # Trayectoria secundaria (sombra)
            self.trail_shadow, = self.ax.plot([], [], '-', color='black', alpha=0.3, linewidth=5,
                                             zorder=9)
            
            # Puntos de trayectoria con tamaño variable
            self.trail_dots, = self.ax.plot([], [], 'o', color='#FF8C42', alpha=0.4, markersize=4,
                                           zorder=11)
            print(" Trayectoria en tiempo real habilitada")
        else:
            # Modo optimización: solo línea básica con menos puntos
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.6, linewidth=2,
                                           label='Trayectoria (optimizada)', zorder=10)
            self.trail_shadow = None
            self.trail_dots = None
            print(" Modo optimización memoria: trayectoria simplificada")
        
        # === INDICADORES DE VELOCIDAD ===
        # Círculo de velocidad (radio proporcional)
        self.speed_indicator = patches.Circle((0, 0), 0, linewidth=3,
                                            edgecolor='cyan', facecolor='cyan',
                                            alpha=0.3, zorder=12)
        self.ax.add_patch(self.speed_indicator)
        
        # === ZONA ACTUAL ===
        # Posicionado muy abajo para evitar solapamiento total
        self.current_zone = self.ax.text(20, -4.5, '', ha='center', va='center',
                                       fontsize=10, color='white', fontweight='bold',
                                       bbox=dict(boxstyle='round,pad=0.4', 
                                               facecolor='black', alpha=0.9,
                                               edgecolor='yellow', linewidth=1))
        
        # === MAPA DE CALOR ===
        # Eliminado para optimización de memoria - usar directamente self.df si se necesita
        
    def setup_info_panel(self):
        """Configurar panel de información en tiempo real"""
        # Panel de información COMPACTO (esquina superior izquierda)
        info_text = ("CONTROLES: SPACE=Play/Pause | ←→=Frame | ↑↓=Velocidad | R=Reset | Q=Salir")
        
        self.info_panel = self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes,
                                     va='top', ha='left', fontsize=9, color='white',
                                     bbox=dict(boxstyle='round,pad=0.4', 
                                             facecolor='black', alpha=0.8))
        
        # Panel de estadísticas (lado izquierdo, debajo de controles)
        self.stats_panel = self.ax.text(0.02, 0.88, '', transform=self.ax.transAxes,
                                      va='top', ha='left', fontsize=8, color='white',
                                      bbox=dict(boxstyle='round,pad=0.3', 
                                              facecolor='darkgreen', alpha=0.85))
        
    def setup_animation_controls(self):
        """Configurar controles de animación con velocidades 0.1x-10x"""
        self.current_frame = 0
        self.total_frames = len(self.df) if self.df is not None else 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.max_playback_speed = 10.0  # Velocidad máxima de reproducción (10x)
        self.min_speed = 0.1            # Velocidad mínima de reproducción (0.1x)
        
        # Conectar eventos de teclado
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
    def get_player_zone(self, x, y):
        """Determinar la zona actual del jugador con zonas más específicas"""
        # Portería izquierda (área de 6m)
        if x <= 6 and 4 <= y <= 16:
            return "ÁREA LOCAL"
        # Portería derecha (área de 6m)
        elif x >= 34 and 4 <= y <= 16:
            return "ÁREA VISITANTE"
        # Círculo central
        elif 17 <= x <= 23 and 7 <= y <= 13:
            return "CENTRO"
        # Zona defensiva local
        elif x <= 13.33:
            return "DEFENSA"
        # Zona media
        elif 13.33 < x <= 26.67:
            return "MEDIO"
        # Zona ofensiva
        elif x > 26.67:
            return "ATAQUE"
        # Fuera de banda
        elif x < 0 or x > 40 or y < 0 or y > 20:
            return "FUERA"
        else:
            return "JUEGO"
    
    def calculate_speed(self, frame_idx):
        """Calcular velocidad instantánea"""
        if self.df is None or frame_idx == 0:
            return 0.0
            
        current_row = self.df.iloc[frame_idx]
        prev_row = self.df.iloc[frame_idx - 1]
        
        # Distancia euclidiana
        dx = current_row['x'] - prev_row['x'] 
        dy = current_row['y'] - prev_row['y']
        distance = np.sqrt(dx**2 + dy**2)
        
        # Tiempo transcurrido
        dt = (current_row['timestamp'] - prev_row['timestamp']).total_seconds()
        
        # Prevención de división entre cero
        if dt == 0 or dt <= 0:
            return 0.0
            
        speed = distance / dt  # m/s
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
        
        # === ACTUALIZAR TRAYECTORIA (optimizada según memoria) ===
        if not self.skip_trail:
            start_idx = max(0, frame_idx - self.trail_length)
            trail_data = self.df.iloc[start_idx:frame_idx + 1]
            
            if len(trail_data) > 1:
                # Trayectoria principal
                self.trail_line.set_data(trail_data['x'], trail_data['y'])
                
                # Sombra de la trayectoria (solo si no está optimizado)
                if self.trail_shadow:
                    self.trail_shadow.set_data(trail_data['x'], trail_data['y'])
                
                # Puntos de trayectoria con degradado (solo si no está optimizado)
                if self.trail_dots:
                    self.trail_dots.set_data(trail_data['x'], trail_data['y'])
        else:
            # Modo optimización: solo línea básica con menos puntos
            start_idx = max(0, frame_idx - 20)  # Solo 20 puntos en modo optimizado
            trail_data = self.df.iloc[start_idx:frame_idx + 1]
            if len(trail_data) > 1:
                self.trail_line.set_data(trail_data['x'], trail_data['y'])
        
        # === CALCULAR VELOCIDAD Y DIRECCIÓN ===
        speed = self.calculate_speed(frame_idx)
        
        # Indicador visual de velocidad (círculo proporcional)
        speed_radius = min(3.0, speed * 0.4)  # Radio máximo 3m
        self.speed_indicator.center = (x, y)
        self.speed_indicator.radius = speed_radius
        
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
        
        # Clasificación de velocidad (iconos ASCII compatibles)
        if speed < 1.0:
            speed_class = "[WALK] CAMINANDO"
        elif speed < 3.0:
            speed_class = "[JOG]  TROTE"
        elif speed < 5.0:
            speed_class = "[RUN]  CARRERA"
        else:
            speed_class = "[SPRINT] SPRINT"
        
        stats_text = (f"TIME {elapsed_time:.1f}s | POS({x:.1f},{y:.1f}) | {speed_class} {speed:.1f}m/s | DIST{total_distance:.0f}m | {frame_idx + 1}/{self.total_frames} | {progress:.0f}% | SPD{self.playback_speed:.1f}x")
        
        self.stats_panel.set_text(stats_text)
        
        # === TÍTULO DINÁMICO ===
        title_color = 'lightgreen' if self.is_playing else 'orange'
        status_icon = '▶️' if self.is_playing else '⏸️'
        
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
            # Siempre avanzar 1 frame, la velocidad se controla por el intervalo
            self.current_frame = min(self.current_frame + 1, self.total_frames - 1)
            
            # Actualizar intervalo de animación según velocidad (limitado a 60 FPS para hardware lento)
            if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                new_interval = max(17, int(40 / self.playback_speed))  # 40ms base / velocidad, límite 60 FPS
                self.anim.event_source.interval = new_interval
            
            # Pausar automáticamente al final
            if self.current_frame >= self.total_frames - 1:
                self.is_playing = False
                
        return self.update_frame(self.current_frame)
    
    def on_key_press(self, event):
        """Manejar eventos de teclado"""
        if event.key == ' ':  # Space - Play/Pause
            self.is_playing = not self.is_playing
            print(f"Reproducción: {'Iniciada' if self.is_playing else 'Pausada'}")
            
        elif event.key == 'left':  # Flecha izquierda - Frame anterior
            self.current_frame = max(0, self.current_frame - 1)
            print(f" Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'right':  # Flecha derecha - Frame siguiente
            self.current_frame = min(self.total_frames - 1, self.current_frame + 1)
            print(f" Frame: {self.current_frame + 1}/{self.total_frames}")
            
        elif event.key == 'up':  # Flecha arriba - Aumentar velocidad
            self.playback_speed = min(self.max_playback_speed, self.playback_speed + 0.5)
            print(f" Velocidad: {self.playback_speed:.1f}x")
            # Actualizar intervalo de animación instantáneamente (limitado a 60 FPS para hardware lento)
            if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                self.anim.event_source.interval = max(17, int(40 / self.playback_speed))
            # Sincronizar slider evitando callback recursivo
            self._sync_slider_safely(self.playback_speed)
            
        elif event.key == 'down':  # Flecha abajo - Reducir velocidad
            self.playback_speed = max(self.min_speed, self.playback_speed - 0.5)
            print(f" Velocidad: {self.playback_speed:.1f}x")
            # Actualizar intervalo de animación instantáneamente (limitado a 60 FPS para hardware lento)
            if hasattr(self, 'anim') and hasattr(self.anim, 'event_source'):
                self.anim.event_source.interval = max(17, int(40 / self.playback_speed))
            # Sincronizar slider evitando callback recursivo
            self._sync_slider_safely(self.playback_speed)
            
        elif event.key == 'r':  # R - Reiniciar
            self.current_frame = 0
            self.is_playing = False
            print(" Replay reiniciado")
            
        elif event.key == 'q':  # Q - Salir
            print(" Cerrando replay...")
            plt.close(self.fig)
            
        # Actualizar visualización inmediatamente
        if not self.is_playing:
            self.update_frame(self.current_frame)
            self.fig.canvas.draw()
    
    def start_replay(self):
        """Iniciar el sistema de replay"""
        print("\n Iniciando Sistema de Replay UWB")
        print("=" * 50)
        print("  Usa las teclas para controlar la reproducción:")
        print("   SPACE:   Play/Pause")
        print("   ←/→: Frame anterior/siguiente") 
        print("   ↑/↓: Velocidad +/-")
        print("   R:  Reiniciar")
        print("   Q:  Salir")
        print("=" * 50)
        
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
        """Configurar controles interactivos avanzados con slider 0.1x-10x"""
        # Área para controles interactivos (espacio optimizado)
        plt.subplots_adjust(bottom=0.12, top=0.94)
        
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
        """Activar/desactivar filtro de Kalman"""
        self.use_kalman_filter = not self.use_kalman_filter
        print(f" Filtro de Kalman: {'Activado' if self.use_kalman_filter else 'Desactivado'}")
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
        """Actualizar colores de botones y texto según estado"""
        # Colores de fondo
        kalman_color = 'lightgreen' if self.use_kalman_filter else 'lightcoral'
        ml_color = 'lightblue' if self.use_ml_prediction else 'lightcoral'
        
        # Colores de texto (mejor contraste para legibilidad)
        kalman_text_color = 'darkgreen' if self.use_kalman_filter else 'darkred'
        ml_text_color = '#002b5c' if self.use_ml_prediction else 'darkred'  # Azul más oscuro
        
        # Actualizar fondo de botones
        self.kalman_button.ax.set_facecolor(kalman_color)
        self.ml_button.ax.set_facecolor(ml_color)
        
        # Actualizar color del texto para máxima claridad
        self.kalman_button.label.set_color(kalman_text_color)
        self.ml_button.label.set_color(ml_text_color)
        
        # Refrescar UI al instante
        self.fig.canvas.draw_idle()

def generate_movement_report(csv_file):
    """Generar reporte de análisis de movimiento"""
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calcular estadísticas
    total_time = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    
    # Validación temprana: evitar división por cero
    if total_time <= 0:
        print("\n⚠️  ADVERTENCIA: Duración de datos insuficiente para análisis")
        print("   Los timestamps no tienen rango temporal válido")
        return
    
    # === OPTIMIZACIÓN: Cálculo eficiente de distancias ===
    # Usar numpy hypot para mejor rendimiento
    x_diff = df['x'].diff()
    y_diff = df['y'].diff()
    step_distances = np.hypot(x_diff, y_diff)
    step_distances[0] = 0  # Primera distancia es 0
    
    total_distance = step_distances.sum()
    avg_speed = total_distance / total_time  # Ya validamos total_time > 0
    
    # Calcular frecuencia real (ya validamos total_time > 0)
    freq = len(df) / total_time
    max_speed = step_distances.max() * freq if len(step_distances) > 0 else 0
    
    print(f"\n REPORTE DE ANÁLISIS DE MOVIMIENTO")
    print("=" * 50)
    print(f"  Duración total: {total_time:.1f} segundos ({total_time/60:.1f} minutos)")
    print(f"📏 Distancia recorrida: {total_distance:.1f} metros")
    print(f" Velocidad promedio: {avg_speed:.2f} m/s")
    print(f" Velocidad máxima: {max_speed:.2f} m/s")
    print(f" Total de frames: {len(df)}")
    print(f" Frecuencia de muestreo: ~{len(df)/total_time:.1f} Hz")
    print("=" * 50)

def select_replay_file_interactive():
    """
    Selección interactiva de archivos para replay con validación mejorada
    """
    
    print("\n SELECCIONAR ARCHIVO PARA REPLAY UWB")
    print("=" * 70)
    print("📍 Ubicación de archivos:")
    print(f"     Directorio actual: {os.getcwd()}")
    print(f"    data/: Datos originales sin procesar")
    print(f"    processed_data/: Datos ya procesados y filtrados")
    print("=" * 70)
    
    # Buscar archivos en ambos directorios
    data_files = []
    
    # Archivos en data/
    if os.path.exists("data"):
        for file_path in glob.glob("data/*.csv"):
            if os.path.exists(file_path):  # Verificar que existe físicamente
                data_files.append(file_path)
    
    # Archivos en processed_data/
    if os.path.exists("processed_data"):
        for file_path in glob.glob("processed_data/*.csv"):
            if os.path.exists(file_path):  # Verificar que existe físicamente
                data_files.append(file_path)
    
    if not data_files:
        print(" No se encontraron archivos CSV válidos")
        print("💡 Asegúrate de tener archivos .csv en las carpetas 'data/' o 'processed_data/'")
        return None
    
    # Ordenar por tamaño (archivos más grandes primero, más útiles para replay)
    data_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
    
    print(f"\n ARCHIVOS DISPONIBLES ({len(data_files)} encontrados):")
    print("=" * 70)
    
    for i, file_path in enumerate(data_files, 1):
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / 1024  # KB
            mod_time = os.path.getmtime(file_path)
            mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
            
            # Determinar carpeta y icono
            if file_path.startswith("data/"):
                folder_icon = "📥"
                folder_name = "data"
                folder_desc = "(original)"
            else:
                folder_icon = ""
                folder_name = "processed_data"
                folder_desc = "(procesado)"
            
            # Determinar si es un archivo bueno para replay (>15KB para datos UWB reales)
            if file_size > 15:
                quality_icon = "⭐"
                quality_desc = "RECOMENDADO"
            elif file_size > 5:
                quality_icon = ""
                quality_desc = "BUENO"
            else:
                quality_icon = ""
                quality_desc = "PEQUEÑO"
            
            print(f"{i:2d}. {quality_icon} {folder_icon} {folder_name}/{file_name:<35}")
            print(f"     {file_size:7.1f}KB |  {mod_date} |  {quality_desc}")
            print()
            
        except Exception as e:
            print(f"{i:2d}.  Error leyendo archivo: {file_path} - {e}")
    
    print("💡 RECOMENDACIÓN: Selecciona archivos marcados con ⭐ para mejor experiencia")
    print(f"\n 0.  Cancelar")
    
    while True:
        try:
            choice = input(f"\n👆 Selecciona un archivo (1-{len(data_files)}) o 0 para cancelar: ").strip()
            
            if choice == '0':
                print(" Operación cancelada")
                return None
            
            file_idx = int(choice) - 1
            if 0 <= file_idx < len(data_files):
                selected_file = data_files[file_idx]
                
                # Verificar que el archivo existe y validar contenido
                if not os.path.exists(selected_file):
                    print(f" Error: El archivo seleccionado no existe: {selected_file}")
                    continue
                
                # Mostrar información del archivo seleccionado
                file_size = os.path.getsize(selected_file) / 1024
                folder_name = "data" if selected_file.startswith("data/") else "processed_data"
                
                print(f"✓ ARCHIVO SELECCIONADO:")
                print(f"    Ubicación: {folder_name}/{os.path.basename(selected_file)}")
                print(f"    Tamaño: {file_size:.1f} KB")
                print(f"     Ruta completa: {os.path.abspath(selected_file)}")
                
                return selected_file
            else:
                print(f"  Número inválido. Ingresa un número entre 1 y {len(data_files)}")
                
        except ValueError:
            print("  Por favor ingresa un número válido")
        except KeyboardInterrupt:
            print("✗ Operación cancelada")
            return None


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description=' Sistema de Replay UWB para Fútbol Sala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python movement_replay.py                                    # Selección interactiva
  python movement_replay.py data/mi_partido.csv               # Archivo específico
  python movement_replay.py --report data/mi_partido.csv      # Solo mostrar reporte
  python movement_replay.py --optimize-memory large_data.csv  # Optimización memoria
  python movement_replay.py --skip-trail --optimize-memory huge_data.csv  # Máxima optimización
        """
    )
    
    parser.add_argument('csv_file', nargs='?', 
                       help='Archivo CSV con datos de movimiento (opcional - si no se especifica, selección interactiva)')
    parser.add_argument('--report', action='store_true',
                       help='Mostrar solo reporte de análisis sin replay')
    parser.add_argument('--optimize-memory', action='store_true',
                       help='Optimizar memoria para datasets grandes (>1M filas)')
    parser.add_argument('--skip-trail', action='store_true',
                       help='Omitir trayectoria en tiempo real para reducir memoria')
    
    args = parser.parse_args()
    
    # Selección de archivo
    if args.csv_file:
        # Archivo especificado por parámetro
        if not os.path.exists(args.csv_file):
            print(f" Error: No se encontró el archivo '{args.csv_file}'")
            return
        selected_file = args.csv_file
    else:
        # Selección interactiva
        selected_file = select_replay_file_interactive()
        if selected_file is None:
            return
    
    try:
        if args.report:
            # Solo mostrar reporte
            generate_movement_report(selected_file)
        else:
            # Mostrar reporte y ejecutar replay
            generate_movement_report(selected_file)
            
            # Iniciar sistema de replay
            replay_system = FutsalReplaySystem(selected_file, args.optimize_memory, args.skip_trail)
            replay_system.start_replay()
            
    except KeyboardInterrupt:
        print("\n Sistema de replay finalizado por el usuario")
    except Exception as e:
        print(f" Error durante el replay: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 