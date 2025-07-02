#!/usr/bin/env python3
"""
Sistema Avanzado de Replay UWB para Área Hexagonal Indoor
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
    Implementación del Filtro de Kalman optimizado para UWB indoor.
    Reduce el ruido y mejora la fluidez con parámetros específicos para movimiento humano.
    """
    def __init__(self, initial_pos=None, process_noise=0.002, measurement_noise=0.2):
        # Dimensiones: estado = 4 (x, y, vx, vy), medición = 2 (x, y)
        self.state = np.zeros(4)  # [x, y, vx, vy]
        if initial_pos is not None:
            self.state[:2] = initial_pos
            
        # Matriz de covarianza (incertidumbre inicial moderada)
        self.P = np.eye(4) * 50  # Reducido aún más para convergencia más rápida
        
        # Ruido del proceso optimizado para movimiento humano
        # Menor ruido = más suave, pero menos reactive a cambios reales
        # REDUCIDO para eliminar tirones
        self.Q = np.array([
            [process_noise, 0, 0, 0],
            [0, process_noise, 0, 0],
            [0, 0, process_noise * 1.5, 0],  # Velocidad puede cambiar menos
            [0, 0, 0, process_noise * 1.5]
        ])
        
        # Ruido de medición optimizado para UWB
        # Mayor ruido = más suavizado, menos reactivo a outliers
        # AUMENTADO para ser más conservativo con mediciones ruidosas
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
        
        # OPTIMIZACIÓN: Detección de outliers en la innovación
        innovation_magnitude = np.linalg.norm(y)
        max_innovation = 3.0  # 3 metros máximo de salto esperado
        
        if innovation_magnitude > max_innovation:
            # Si la innovación es muy grande, reducir la confianza en la medición
            measurement_noise_factor = min(5.0, innovation_magnitude / max_innovation)
            R_adaptive = self.R * measurement_noise_factor
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"🚨 Outlier Kalman: innovación={innovation_magnitude:.2f}m, factor={measurement_noise_factor:.1f}")
        else:
            R_adaptive = self.R
        
        # Covarianza de la innovación
        S = self.H @ self.P @ self.H.T + R_adaptive
        
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
    optimizado para movimientos indoor.
    """
    def __init__(self, context="indoor"):
        self.context = context
        self.x_model = None
        self.y_model = None
        self.min_samples_required = 5
        self.is_trained = False
        self.min_ts = 0
        self.max_ts = 0
        
        # Kernel optimizado para movimiento indoor
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
            max_speed: Velocidad máxima permitida en m/s (default: 7.0 m/s para movimiento indoor)
            
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

class UWBHexagonReplaySystem:
    def __init__(self, csv_file, optimize_memory=False, skip_trail=False, verbose_debug=False):
        """
        Inicializar el sistema de replay avanzado
        
        Args:
            csv_file: Archivo CSV con datos de movimiento
            optimize_memory: Flag para optimizar memoria en datasets grandes (>1M filas)
            skip_trail: Flag para omitir trayectoria en tiempo real (reduce memoria)
            verbose_debug: Flag para mostrar todos los logs de debug GPR (puede ser spam)
        """
        print("🔷 Cargando Sistema Avanzado de Replay UWB...")
        
        # Configuración avanzada
        self.use_kalman_filter = True
        self.use_ml_prediction = False  # Desactivado por defecto - overhead innecesario para datos de calidad actual
        self.optimize_memory = optimize_memory
        self.skip_trail = skip_trail
        self.verbose_debug = verbose_debug
        self.debug_log_counter = 0  # Contador para limitar spam de logs
        
        # Configuración de trayectoria (ahora SIEMPRE completa)
        # NOTA: La trayectoria ahora siempre se muestra completa desde el inicio
        if skip_trail:
            print(" Trail simplificado: trayectoria completa pero sin efectos visuales")
        elif optimize_memory:
            print(" Modo optimización de memoria: trayectoria completa optimizada")
        else:
            print(" Trayectoria completa con todos los efectos visuales")
        
        # trail_length ya no se usa - mantenemos toda la trayectoria visible
        self.trail_length = None  # No se usa más, trayectoria completa
        
        self.animation_step_ms = 20  # 50 FPS
        self.max_player_speed = 7.0  # m/s (velocidad sprint indoor - límite físico)
        self.interpolation_threshold = 100  # ms
        # Intervalo mínimo entre reentrenamientos GPR (para acelerar en datasets grandes)
        self.gpr_train_interval_ms = 500  # solo reentrenar cada 0.5 s de datos faltantes
        self._last_gpr_train_ms = -1  # Timestamp del último entrenamiento GPR
        
        # Filtros y predictores
        self.kalman_filter = None
        self.trajectory_predictor = TrajectoryPredictor("indoor")
        
        # Datos procesados - Inicializar como None
        self.original_df = None
        self.df = None
        
        self.load_data(csv_file)
        self.setup_plot()
        self.setup_animation_controls()
        self.setup_interactive_controls()
        
    def load_data(self, csv_file):
        """Cargar y procesar datos CSV con filtros avanzados"""
        try:
            # === OPTIMIZACIÓN DE MEMORIA: Detección precisa de datasets grandes ===
            file_size_mb = os.path.getsize(csv_file) / (1024 * 1024)
            print(f" Tamaño del archivo: {file_size_mb:.1f} MB")
            
            if file_size_mb > 20:  # Datasets >20MB requieren análisis detallado
                print("WARNING: Dataset grande detectado")
                print(f"   Archivo: {file_size_mb:.1f} MB")
                
                if not self.optimize_memory and file_size_mb > 50:
                    print("RECOMENDACION CRITICA: Activa optimización de memoria")
                    print("   python movement_replay.py --optimize-memory [archivo]")
            
            # Cargar con tipos optimizados si está activada la optimización
            if self.optimize_memory:
                print(" Modo optimización de memoria: cargando con tipos float32")
                try:
                    # Cargar primero y luego convertir tipos
                    self.original_df = pd.read_csv(csv_file)
                    # Convertir columnas numéricas a float32 para ahorrar memoria
                    for col in ['x', 'y']:
                        if col in self.original_df.columns:
                            self.original_df[col] = self.original_df[col].astype('float32')
                    if 'tag_id' in self.original_df.columns:
                        self.original_df['tag_id'] = self.original_df['tag_id'].astype('int32')
                except Exception as e:
                    print(f"   Advertencia: Error en optimización de tipos: {e}")
                    self.original_df = pd.read_csv(csv_file)
            else:
                self.original_df = pd.read_csv(csv_file)
            
            # === ESTIMACIÓN PRECISA DE MEMORIA ===
            num_rows = len(self.original_df)
            memory_usage_mb = self.original_df.memory_usage(deep=True).sum() / (1024 * 1024)
            
            print(f" Registros originales: {num_rows:,}")
            print(f" Memoria actual DataFrame: {memory_usage_mb:.1f} MB")
            
            # Estimación realista después del procesamiento (×8-10 por interpolación + cálculos)
            interpolation_factor = 8 if self.optimize_memory else 10
            estimated_final_memory_mb = memory_usage_mb * interpolation_factor
            
            if num_rows > 500_000:  # >500k filas requieren advertencia
                print(f"WARNING: Memoria estimada final: ~{estimated_final_memory_mb:.0f} MB ({estimated_final_memory_mb/1024:.1f} GB)")
                
                if estimated_final_memory_mb > 1024 and not self.optimize_memory:  # >1GB
                    print("DATASET CRITICO: Memoria estimada >1GB. Recomendado --optimize-memory")
                    print("   O usar --skip-trail para reducir aún más la memoria")
            
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
            
        print(" Aplicando filtros avanzados...")
        
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
        """Aplicar interpolación inteligente con ML y Kalman optimizada para fluidez"""
        if self.original_df is None:
            return None
            
        # Convertir timestamps a millisegundos para trabajar
        timestamps_ms = np.array([
            (ts - self.original_df['timestamp'].iloc[0]).total_seconds() * 1000
            for ts in self.original_df['timestamp']
        ], dtype=np.float64)
        
        # OPTIMIZACIÓN: Paso adaptativo basado en la frecuencia original
        original_avg_interval = np.mean(np.diff(timestamps_ms))
        print(f"🔍 Intervalo original promedio: {original_avg_interval:.1f}ms")
        
        # Si los datos son muy esparsos (>500ms), usar pasos más grandes inicialmente
        if original_avg_interval > 500:
            # Para datos esparsos: 30fps (33ms) es mejor que 60fps para evitar overprocessing
            fluid_step_ms = 33.33  
            print("⚡ Usando 30fps para datos esparsos")
        else:
            # Para datos densos: 60fps completo
            fluid_step_ms = 16.67  
            print("⚡ Usando 60fps para datos densos")
        
        # Crear timeline completo con step fijo (incluir último instante)
        start_ms = 0
        end_ms = timestamps_ms[-1]
        full_timeline = np.arange(start_ms, end_ms + fluid_step_ms, fluid_step_ms)
        
        # Preparar datos para interpolación
        positions = self.original_df[['x', 'y']].values
        
        # Identificar gaps grandes que requieren predicción ML
        interpolated_positions = []
        
        for target_ms in full_timeline:
            # Encontrar dato más cercano usando búsqueda binaria (searchsorted)
            idx = np.searchsorted(timestamps_ms, target_ms)
            if idx >= len(timestamps_ms):
                idx = len(timestamps_ms) - 1
            # Evaluar vecino anterior para localizar el más cercano
            if idx > 0 and abs(timestamps_ms[idx - 1] - target_ms) < abs(timestamps_ms[idx] - target_ms):
                closest_idx = idx - 1
            else:
                closest_idx = idx
            
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
    
    def apply_moving_average_smoothing(self, positions_list, window_size=7):
        """
        Aplicar suavizado con media móvil para eliminar tirones.
        MEJORADO: Ventana más grande y suavizado más agresivo para eliminar tirones hacia atrás.
        
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
        """Configurar la visualización del área hexagonal indoor"""
        # Crear figura y ejes
        self.fig, self.ax = plt.subplots(figsize=(18, 12))

        # Intentar poner título de ventana (puede fallar en algunos backends)
        try:
            if hasattr(self.fig.canvas, 'manager') and self.fig.canvas.manager is not None:
                self.fig.canvas.manager.set_window_title('Sistema de Replay UWB - Área Hexagonal')
        except Exception:
            pass
        
        # ======================== ÁREA HEXAGONAL ========================
        minX, maxX = -6.9, 6.8
        minY, maxY = -3.5, 10.36
        self.ax.set_xlim(minX - 1, maxX + 1)
        self.ax.set_ylim(minY - 1, maxY + 1)
        self.ax.set_aspect('equal')
        self.ax.set_facecolor('#f8f8f8')

        self.draw_hexagon_area()
        self.draw_hexagon_anchors()
        
        # Configurar elementos dinámicos
        self.setup_dynamic_elements()
        
        # Panel de información
        self.setup_info_panel()


    

    
    def draw_hexagon_anchors(self):
        """Dibujar anclas UWB en la disposición indoor"""
        anchors = {
            'A1': (-6.0, 0.0, 'blue'),
            'A2': (-2.6, 7.92, 'blue'),  
            'A3': (2.1, 10.36, 'blue'),
            'A4': (6.35, 0.0, 'blue'),
            'A5': (0.0, -1.8, 'blue')
        }

        for anchor_id, (x, y, color) in anchors.items():
            self.ax.plot(x, y, 's', color=color, markersize=10, zorder=5)
            self.ax.text(x, y + 0.3, anchor_id, ha='center', va='bottom', fontsize=9, color='black')
    
    def draw_hexagon_area(self):
        """Dibujar el perímetro del hexágono irregular con vértices ordenados correctamente"""
        # Vértices en orden horario empezando desde superior izquierdo
        verts = [
            (-6.9, -2),      # Vértice inferior izquierdo (corregido)
            (-1.6, 10.36),   # Vértice superior izquierdo
            (2.1, 10.36),    # Vértice superior derecho
            (6.8, -1.8),     # Vértice inferior derecho
            (0, -1.8),       # Vértice inferior centro
            (-0.4, -3.5)     # Vértice inferior extremo
        ]
        poly = patches.Polygon(verts, closed=True, fill=False, edgecolor='orange', linewidth=3, alpha=0.8)
        self.ax.add_patch(poly)
        
        # Añadir etiquetas de vértices para debug
        for i, (x, y) in enumerate(verts):
            self.ax.plot(x, y, 'ro', markersize=6, alpha=0.7)
            self.ax.text(x+0.2, y+0.2, f'V{i+1}', fontsize=8, color='red', alpha=0.8)
    
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
        
        # === TRAYECTORIA COMPLETA (toda la trayectoria visible) ===
        if not self.skip_trail:
            # Trayectoria principal con degradado
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.8, linewidth=3,
                                           label='Trayectoria Completa', zorder=10)
            
            # Trayectoria secundaria (sombra)
            self.trail_shadow, = self.ax.plot([], [], '-', color='black', alpha=0.3, linewidth=5,
                                             zorder=9)
            
            # Puntos de trayectoria con tamaño variable
            self.trail_dots, = self.ax.plot([], [], 'o', color='#FF8C42', alpha=0.4, markersize=3,
                                           zorder=11)
            print(" Trayectoria completa habilitada (toda la ruta visible)")
        else:
            # Modo optimización: solo línea básica pero completa
            self.trail_line, = self.ax.plot([], [], '-', color='#FF6B35', alpha=0.6, linewidth=2,
                                           label='Trayectoria Completa (optimizada)', zorder=10)
            self.trail_shadow = None
            self.trail_dots = None
            print(" Modo optimización memoria: trayectoria completa simplificada")
        
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
        """Determinar la zona actual del jugador en el área hexagonal indoor"""
        # === ZONAS PARA ÁREA HEXAGONAL INDOOR ===
        # Verificar si está dentro del área válida
        if not (-6.9 <= x <= 6.8 and -3.5 <= y <= 10.36):
            return "FUERA DEL ÁREA"
        
        # Zonas específicas del área indoor
        if y >= 8.0:
            return "ZONA NORTE"
        elif y <= -1.0:
            return "ZONA SUR"
        elif x >= 4.0:
            return "ZONA ESTE"
        elif x <= -4.0:
            return "ZONA OESTE"
        elif -2.0 <= x <= 2.0 and 2.0 <= y <= 6.0:
            return "ZONA CENTRAL"
        else:
            return "ÁREA INDOOR"
    
    def calculate_speed(self, frame_idx):
        """Calcular velocidad instantánea con límites realistas"""
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
        
        # === CORRECCIÓN: Limitar velocidades físicamente imposibles ===
        # Velocidad máxima humana realista indoor: 8 m/s (incluye margen)
        max_realistic_speed = 8.0
        
        if speed > max_realistic_speed:
            # Advertencia solo para casos extremos (>2x límite)
            if speed > max_realistic_speed * 2 and self.verbose_debug:
                print(f"   [SPEED WARNING] Velocidad irreal detectada: {speed:.1f} m/s → limitada a {max_realistic_speed} m/s")
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
        # Ajuste de layout manual ya realizado con subplots_adjust para evitar solapamientos
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
        """Activar/desactivar filtro de Kalman"""
        self.use_kalman_filter = not self.use_kalman_filter
        print(f" Filtro de Kalman: {'Activado' if self.use_kalman_filter else 'Desactivado'}")
        self.update_button_colors()
        
        # === OPTIMIZACIÓN: Solo reprocessar Kalman si ya hay datos interpolados ===
        if self.df is not None and len(self.df) > 0:
            # Mantener datos base y solo reaplicar Kalman
            self._reapply_kalman_filter()
        else:
            # Primer procesado o datos no válidos - recarga completa
            self.apply_advanced_filtering()
    
    def _reapply_kalman_filter(self):
        """Reaplicar solo el filtro de Kalman a datos ya interpolados"""
        if self.df is None:
            return
            
        print(" Reaplicando filtro de Kalman...")
        
        # Reinicializar filtro de Kalman si está activado
        if self.use_kalman_filter:
            first_valid_pos = self.find_first_valid_position()
            if first_valid_pos is not None:
                self.kalman_filter = KalmanPositionFilter(
                    initial_pos=first_valid_pos,
                    process_noise=0.01,
                    measurement_noise=0.1
                )
                
                # Reaplicar Kalman a las posiciones existentes
                dt = self.animation_step_ms / 1000.0
                for i in range(len(self.df)):
                    pos = [self.df.iloc[i]['x'], self.df.iloc[i]['y']]
                    filtered_pos = self.kalman_filter.process(pos, dt)
                    self.df.iloc[i, self.df.columns.get_loc('x')] = filtered_pos[0]
                    self.df.iloc[i, self.df.columns.get_loc('y')] = filtered_pos[1]
        else:
            # Si se desactiva Kalman, necesitamos datos originales - recarga completa
            self.apply_advanced_filtering()
    
    def toggle_ml(self, event):
        """Activar/desactivar predicción ML"""
        self.use_ml_prediction = not self.use_ml_prediction
        print(f"Prediccion ML: {'Activada' if self.use_ml_prediction else 'Desactivada'}")
        self.update_button_colors()
        
        # === OPTIMIZACIÓN: Solo recalcular si realmente es necesario ===
        # ML solo afecta interpolación de gaps, no datos ya válidos
        # Solo recarga si hay grandes cambios en la interpolación
        print(" Configuración ML actualizada (efecto en próximos huecos de señal)")
        
        # Reset del timestamp de entrenamiento para forzar reentrenamiento
        self._last_gpr_train_ms = -1
    
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
    
    # === CORRECCIÓN: Calcular velocidades realistas ===
    # Calcular frecuencia real y velocidades frame a frame
    freq = len(df) / total_time
    
    # Velocidades frame a frame con límite realista
    frame_speeds = step_distances * freq  # velocidad por frame
    
    # Aplicar límite físico realista
    max_realistic_speed = 8.0  # m/s - límite humano indoor
    frame_speeds = np.clip(frame_speeds, 0, max_realistic_speed)
    
    max_speed = frame_speeds.max() if len(frame_speeds) > 0 else 0
    
    # === ADVERTENCIAS DE REALISMO ===
    original_max_speed = (step_distances * freq).max() if len(step_distances) > 0 else 0
    if original_max_speed > max_realistic_speed:
        print(f"\n⚠️  VELOCIDADES CORREGIDAS:")
        print(f"   Velocidad máxima original: {original_max_speed:.1f} m/s (irreal)")
        print(f"   Velocidad máxima corregida: {max_speed:.1f} m/s (limitada)")
        print(f"   Las velocidades >8 m/s se limitaron por realismo físico")
    
    print(f"\n REPORTE DE ANÁLISIS DE MOVIMIENTO")
    print("=" * 50)
    print(f"  Duración total: {total_time:.1f} segundos ({total_time/60:.1f} minutos)")
    print(f" Distancia recorrida: {total_distance:.1f} metros")
    print(f" Velocidad promedio: {avg_speed:.2f} m/s")
    print(f" Velocidad máxima: {max_speed:.2f} m/s")
    print(f" Total de frames: {len(df)}")
    print(f" Frecuencia de muestreo: ~{len(df)/total_time:.1f} Hz")
    
    # === ANÁLISIS DE REALISMO ===
    if avg_speed > 4.0:
        print(f"⚠️  ADVERTENCIA: Velocidad promedio muy alta ({avg_speed:.1f} m/s)")
        print("   Velocidad típica indoor: 1.5-3.0 m/s promedio")
    elif avg_speed < 0.5:
        print(f"ℹ️  INFO: Velocidad promedio baja ({avg_speed:.1f} m/s) - movimiento lento o estático")
    else:
        print(f"✅ Velocidad promedio realista ({avg_speed:.1f} m/s)")
    
    if max_speed > 7.0:
        print(f"⚠️  ADVERTENCIA: Velocidad máxima muy alta ({max_speed:.1f} m/s)")
    else:
        print(f"✅ Velocidad máxima realista ({max_speed:.1f} m/s)")
    
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
                folder_icon = ""
                folder_name = "data"
                folder_desc = "(original)"
            else:
                folder_icon = ""
                folder_name = "processed_data"
                folder_desc = "(procesado)"
            
            # Determinar si es un archivo bueno para replay (>15KB para datos UWB reales)
            if file_size > 15:
                quality_icon = "*"
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
    
    print(" RECOMENDACION: Selecciona archivos marcados con * para mejor experiencia")
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
        description='🔷 Sistema de Replay UWB para Área Hexagonal Indoor',
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
    parser.add_argument('--verbose-debug', action='store_true',
                       help='Mostrar todos los logs de debug GPR (puede generar spam)')
    
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
            replay_system = UWBHexagonReplaySystem(selected_file, args.optimize_memory, args.skip_trail, args.verbose_debug)
            replay_system.start_replay()
            
    except KeyboardInterrupt:
        print("\n Sistema de replay finalizado por el usuario")
    except Exception as e:
        print(f" Error durante el replay: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 