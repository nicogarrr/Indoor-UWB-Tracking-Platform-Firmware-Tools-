import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.image as mpimg
import os
import json
from tkinter import Tk, filedialog
from scipy.optimize import minimize
from scipy.interpolate import CubicSpline, interp1d
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, Matern, DotProduct
import datetime
import time

class KalmanPositionFilter:
    """
    Implementación simple del Filtro de Kalman para suavizar posiciones 2D.
    Útil para reducir el ruido en las posiciones calculadas.
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
        # F[0,2] y F[1,3] se actualizarán con dt en cada paso
        
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

class TagReplay:
    def __init__(self):
        # Configuración del espacio experimental (3.45m x 5.1m)
        self.field_length = 6.6   # metros (largo)
        self.field_width = 6.26   # metros (ancho)
        self.anchor_height = 1.5 # Added: Common anchor height
        self.time_window_ms = 50 # Added time window parameter
        self.animation_step_ms = 20 # Intervalo para frames interpolados (aprox 50 FPS)
        self.gap_threshold_ms = 100 # Reducido de 500ms a 100ms para usar más el modelo GPR
        self.max_speed = 5.0 # Velocidad máxima razonable en metros/segundo
        self.motion_smoothing = 0.8 # Factor de suavizado para movimientos (0-1)
        self.use_ml_prediction = True # Usar predicción con machine learning
        self.sport_context = "futsal" # Contexto deportivo: fútbol sala
        self.use_kalman_filter = True # Usar filtro de Kalman para suavizar posiciones
        self.show_trail = True # Mostrar rastro de movimiento
        self.trail_length = 30 # Número de frames previos para mostrar el rastro
        
        # Parámetros específicos para fútbol sala
        self.futsal_sprint_speed = 7.0 # Velocidad máxima en sprint (m/s)
        self.futsal_typical_speed = 3.0 # Velocidad típica de juego (m/s)
        self.futsal_max_acceleration = 4.0 # Aceleración máxima (m/s²)
        self.futsal_court_bounds = [0, self.field_width, 0, self.field_length] # Límites de la cancha
        
        # Posiciones de los anchors (x, y, z) en metros
        # Updated Z to self.anchor_height
        self.anchors = {
            10: {'position': [0.0, 2.00, self.anchor_height], 'color': 'red', 'label': 'Anchor 10'},
            20: {'position': [0.0, 6.66, self.anchor_height], 'color': 'green', 'label': 'Anchor 20'},
            30: {'position': [6.25, 0.1, self.anchor_height], 'color': 'blue', 'label': 'Anchor 30'},
            40: {'position': [6.25, 3.00, self.anchor_height], 'color': 'purple', 'label': 'Anchor 40'}
        }
        
        self.data = None
        self.all_data = {} # Store data per tag_id
        self.positions = {} # Store calculated positions and status per tag_id
        self.animation_frames = {} # Store interpolated frames for animation
        self.animation = None
        self.fig = None
        self.ax = None
        self.tag_plots = {}
        self.anchor_plots = {}
        self.radius_circles = {}
        self.info_text = None
        self.time_text = None
        self.trail_plots = {} # Almacenar los plots de rastros
        self.kalman_filters = {} # Filtros de Kalman para cada tag
        self.current_frame = 0
        self.total_frames = 0
        self.playing = False
        self.play_speed = 1.0 
        self.tag_ids_available = []
        self.selected_tag_id = None # Track which tag is being displayed
        self.trajectory_predictor = None # Machine learning predictor

        # Cargar posiciones guardadas de anchors si existen
        self.config_file = 'anchor_positions.json'
        self.load_anchor_positions() 
    
    def load_anchor_positions(self):
        """Carga las posiciones de los anchors desde un archivo de configuración."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for anchor_id_str, data in config.items():
                        anchor_id = int(anchor_id_str)
                        if anchor_id in self.anchors:
                            # Ensure position includes Z, default to self.anchor_height if missing
                            pos = data.get('position', [0, 0, self.anchor_height])
                            if len(pos) == 2:
                                pos.append(self.anchor_height) # Add Z if only X,Y saved
                            self.anchors[anchor_id]['position'] = pos[:3] # Take only X,Y,Z
                print(f"Posiciones de anchors cargadas desde {self.config_file}")
            except Exception as e:
                print(f"Error al cargar posiciones de anchors: {e}. Usando predeterminadas.")
                # Re-initialize Z if loading failed
                for anchor_id in self.anchors:
                    self.anchors[anchor_id]['position'][2] = self.anchor_height

    def save_anchor_positions(self):
        """Guarda las posiciones de los anchors en un archivo de configuración."""
        try:
            config = {}
            for anchor_id, data in self.anchors.items():
                config[str(anchor_id)] = {'position': data['position'][:3]} # Save X,Y,Z
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error al guardar posiciones de anchors: {e}")

    def setup_anchors(self):
        """Configura las posiciones de los anchors mediante entrada del usuario."""
        print("\nConfiguración de posiciones de anchors en el espacio experimental (en metros)")
        print(f"Dimensiones del espacio: {self.field_length}m x {self.field_width}m")
        print(f"Altura común de anchors actual: {self.anchor_height}m")
        height_input = input(f"Nueva altura común para todos los anchors (Enter para mantener {self.anchor_height}m): ")
        if height_input.strip():
            try:
                self.anchor_height = float(height_input)
                print(f"Altura común actualizada a: {self.anchor_height}m")
            except ValueError:
                print("Entrada inválida. Manteniendo altura actual.")

        print("Posiciones X, Y. Formato: x y (ejemplo: 1.5 2.0)")
        for anchor_id in self.anchors:
            current_pos = self.anchors[anchor_id]['position']
            print(f"\nAnchor {anchor_id} - Posición actual: [{current_pos[0]:.2f}, {current_pos[1]:.2f}, {self.anchor_height:.2f}]")
            pos_input = input(f"Nuevas coordenadas X Y para Anchor {anchor_id} (Enter para mantener actual): ")
            
            if pos_input.strip():
                try:
                    x, y = map(float, pos_input.split())
                    # Validar que las coordenadas estén dentro del espacio
                    x = max(0, min(x, self.field_width))
                    y = max(0, min(y, self.field_length))
                    self.anchors[anchor_id]['position'] = [x, y, self.anchor_height] # Update with new common height
                    print(f"Posición actualizada: [{x:.2f}, {y:.2f}, {self.anchor_height:.2f}]")
                except ValueError:
                    print("Formato inválido. Manteniendo la posición actual.")
            else:
                 # Ensure height is updated even if X,Y are kept
                 self.anchors[anchor_id]['position'][2] = self.anchor_height 

        self.save_anchor_positions()
        print("\nConfiguración de Anchors finalizada.")

    def load_data(self, csv_file=None):
        """Carga los datos desde un archivo CSV."""
        if csv_file is None:
            print("No se proporcionó archivo CSV.")
            return False
            
        try:
            # Updated columns to include Anchor_Status
            expected_columns = ['Tag_ID', 'Timestamp_ms', 'Anchor_ID', 'Raw_Distance_cm', 
                                'Filtered_Distance_cm', 'Signal_Power_dBm']
            optional_column = 'Anchor_Status'
            expected_columns_with_optional = expected_columns + [optional_column]
            
            # Leer CSV, intentando detectar delimitador y manejando errores
            try:
                df = pd.read_csv(csv_file, header=0, on_bad_lines='warn') 
            except pd.errors.ParserError as e:
                print(f"Error al parsear CSV: {e}. Verifique el formato del archivo.")
                return False
            except FileNotFoundError:
                print(f"Error: Archivo no encontrado - {csv_file}")
                return False

            # Verificar columnas base
            missing_base_columns = [col for col in expected_columns if col not in df.columns]
            if missing_base_columns:
                print(f"Error: Faltan columnas base esperadas en el archivo CSV: {missing_base_columns}")
                print(f"Columnas encontradas: {list(df.columns)}")
                return False

            # Verificar si la columna opcional está presente
            has_anchor_status = optional_column in df.columns
            if not has_anchor_status:
                print(f"Advertencia: La columna '{optional_column}' no se encontró. Se continuará sin datos de estado del ancla.")
                # Definir las columnas a usar si falta la opcional
                columns_to_use = expected_columns
            else:
                columns_to_use = expected_columns_with_optional

            # Limpieza y conversión de tipos
            df = df[columns_to_use].copy() # Asegurarse de tener solo las columnas necesarias
            df['Timestamp_ms'] = pd.to_numeric(df['Timestamp_ms'], errors='coerce')
            df['Tag_ID'] = pd.to_numeric(df['Tag_ID'], errors='coerce').astype('Int64') # Use Int64 for potential NaNs
            df['Anchor_ID'] = pd.to_numeric(df['Anchor_ID'], errors='coerce').astype('Int64')
            # Convert distance to meters
            df['Filtered_Distance_m'] = pd.to_numeric(df['Filtered_Distance_cm'], errors='coerce') / 100.0 
            if has_anchor_status:
                df['Anchor_Status'] = pd.to_numeric(df['Anchor_Status'], errors='coerce').astype('Int64')
            else:
                df['Anchor_Status'] = 'Unknown' # O np.nan, o lo que sea apropiado
            df.dropna(subset=['Timestamp_ms', 'Tag_ID', 'Anchor_ID', 'Filtered_Distance_m'], inplace=True)
            
            # Ordenar por timestamp
            df.sort_values(by='Timestamp_ms', inplace=True)
            df.reset_index(drop=True, inplace=True)

            # Almacenar datos crudos por Tag ID
            self.all_data = {tag_id: group for tag_id, group in df.groupby('Tag_ID')}
            self.tag_ids_available = sorted(list(self.all_data.keys()))

            if not self.tag_ids_available:
                print("No se encontraron datos válidos de tags en el archivo.")
                return False

            # Seleccionar el primer tag por defecto
            self.selected_tag_id = self.tag_ids_available[0]
            print(f"Tags disponibles: {self.tag_ids_available}. Mostrando Tag ID: {self.selected_tag_id}")

            # Inicializar el predictor de trayectorias con contexto deportivo
            self.trajectory_predictor = TrajectoryPredictor(context=self.sport_context)
            
            # Procesar posiciones para el tag seleccionado
            self.process_positions_for_tag(self.selected_tag_id)
            
            print(f"Datos cargados y procesados para Tag ID {self.selected_tag_id}. Total frames: {self.total_frames}")
            return True

        except Exception as e:
            import traceback
            print(f"Error inesperado al cargar datos: {e}")
            traceback.print_exc()
            return False

    def process_positions_for_tag(self, tag_id):
        """Calcula las posiciones para un tag_id específico usando una ventana de tiempo."""
        if tag_id not in self.all_data:
            print(f"Error: Tag ID {tag_id} no encontrado en los datos cargados.")
            self.positions[tag_id] = []
            self.total_frames = 0
            return

        # Crear un nuevo filtro de Kalman para este tag
        self.kalman_filters[tag_id] = KalmanPositionFilter(process_noise=0.01, measurement_noise=0.1)

        df_tag = self.all_data[tag_id]
        processed_data = []
        unique_timestamps = sorted(df_tag['Timestamp_ms'].unique()) # Ensure timestamps are sorted

        anchor_ids_list = list(self.anchors.keys())

        for ts in unique_timestamps:
            # Define the time window: (ts - time_window_ms, ts]
            window_start_ts = ts - self.time_window_ms
            window_data = df_tag[(df_tag['Timestamp_ms'] > window_start_ts) & (df_tag['Timestamp_ms'] <= ts)]
            
            latest_distances = {} # Store latest distance for each anchor in the window
            latest_statuses = {} # Store latest status for each anchor in the window
            responding_anchors_dist = {}
            responding_anchors_pos = {}
            num_responding = 0

            if not window_data.empty:
                for anchor_id in anchor_ids_list:
                    anchor_window_data = window_data[window_data['Anchor_ID'] == anchor_id]
                    if not anchor_window_data.empty:
                        # Get the row with the latest timestamp for this anchor within the window
                        latest_anchor_row = anchor_window_data.loc[anchor_window_data['Timestamp_ms'].idxmax()]
                        dist = latest_anchor_row['Filtered_Distance_m']
                        status = latest_anchor_row['Anchor_Status']
                        latest_distances[anchor_id] = dist
                        latest_statuses[anchor_id] = status

                        # Check if this latest measurement is valid for trilateration
                        if not np.isnan(dist) and dist > 0.01:
                            responding_anchors_dist[anchor_id] = dist
                            responding_anchors_pos[anchor_id] = self.anchors[anchor_id]['position']
                            num_responding += 1
                    else:
                        # No data for this anchor in the window
                        latest_distances[anchor_id] = np.nan
                        latest_statuses[anchor_id] = 0
            else:
                 # No data in the entire window for any anchor
                 for anchor_id in anchor_ids_list:
                    latest_distances[anchor_id] = np.nan
                    latest_statuses[anchor_id] = 0

            calculated_position = [np.nan, np.nan] # Default to NaN
            
            # --- 3D Multilateration (using latest valid data within the window) ---
            if num_responding >= 3: # Need at least 3 anchors for 3D
                try:
                    # Pass only responding anchors' latest data
                    pos_3d = self.multilateration_3d(responding_anchors_dist, responding_anchors_pos)
                    if pos_3d is not None:
                        calculated_position = pos_3d[:2] # Use only X, Y for 2D plot
                except Exception as e:
                     print(f"Error en multilateración en ventana hasta TS {ts}: {e}")
                     # Position remains NaN
            
            processed_data.append({
                'timestamp': ts, # Timestamp represents the end of the window
                'position': calculated_position,
                'distances': latest_distances, # Store latest distances from window
                'statuses': latest_statuses # Store latest statuses from window
            })

        self.positions[tag_id] = processed_data
        self.total_frames = len(self.positions[tag_id])
        self.current_frame = 0 # Reset frame counter when data reloaded

        # Generar frames interpolados para la animación
        self.generate_interpolated_frames(tag_id)
        # Actualizar total_frames para que se base en los frames interpolados
        self.total_frames = len(self.animation_frames.get(tag_id, []))
        self.current_frame = 0 # Asegurarse de que el contador de frames se reinicia

    # Renamed and updated for 3D
    def multilateration_3d(self, responding_distances, responding_anchor_positions):
        """Calcula la posición 3D del tag usando multilateración optimizada."""
        
        anchor_ids = list(responding_distances.keys())
        if len(anchor_ids) < 3:
            return None # No se puede calcular con menos de 3

        # Función de error: suma de cuadrados de las diferencias entre distancias medidas y calculadas
        def error_function(point): # point is [x, y, z]
            error = 0
            for anchor_id in anchor_ids:
                anchor_pos = responding_anchor_positions[anchor_id]
                measured_dist = responding_distances[anchor_id]
                # Calculated distance in 3D
                calculated_dist = np.sqrt(
                    (point[0] - anchor_pos[0])**2 + 
                    (point[1] - anchor_pos[1])**2 + 
                    (point[2] - anchor_pos[2])**2
                )
                error += (calculated_dist - measured_dist)**2
            return error

        # Estimación inicial (centro del campo, a media altura)
        initial_guess = [self.field_width / 2, self.field_length / 2, self.anchor_height / 2]
        
        # Límites para la búsqueda (dentro del campo y altura razonable)
        bounds = [(0, self.field_width), (0, self.field_length), (0, self.anchor_height * 2)] 

        # Optimización para encontrar el punto que minimiza el error
        result = minimize(error_function, initial_guess, method='L-BFGS-B', bounds=bounds)

        if result.success:
            # Devolver la posición 3D calculada [x, y, z]
            return result.x
        else:
            # print(f"Optimización fallida: {result.message}")
            return None

    def generate_interpolated_frames(self, tag_id):
        """Genera frames interpolados para una animación más fluida."""
        keyframes = self.positions.get(tag_id)

        if not keyframes or len(keyframes) < 2:
            self.animation_frames[tag_id] = keyframes if keyframes else []
            return

        # Aplicar relleno básico para asegurar que no hay NaNs
        processed_keyframes = self._fill_nan_positions(keyframes)
        
        # Detectar y corregir movimientos erráticos
        corrected_keyframes = self._correct_erratic_movements(processed_keyframes)
        
        # Resultado con las posiciones interpoladas
        result_frames = []
        
        # Inicializar con el primer keyframe
        result_frames.append(corrected_keyframes[0])
        
        # Para cada par de keyframes consecutivos
        for i in range(1, len(corrected_keyframes)):
            prev_frame = corrected_keyframes[i-1]
            curr_frame = corrected_keyframes[i]
            prev_ts = prev_frame['timestamp']
            curr_ts = curr_frame['timestamp']
            
            # Verificar si hay un salto grande de tiempo que requiera predicción
            time_gap = curr_ts - prev_ts
            is_large_gap = time_gap > self.gap_threshold_ms
            
            # Si hay un salto y está activada la predicción ML, usar el predictor 
            # (Ahora favorecemos usar el predictor para casi todos los saltos)
            if time_gap > self.animation_step_ms * 2 and self.use_ml_prediction and self.trajectory_predictor is not None:
                # Generar los timestamps para los frames intermedios
                missing_timestamps = []
                current_ts = prev_ts + self.animation_step_ms
                while current_ts < curr_ts:
                    missing_timestamps.append(current_ts)
                    current_ts += self.animation_step_ms
                
                # Obtener suficientes frames históricos para que el predictor aprenda patrones
                history_start_idx = max(0, i - 10)  # Considerar hasta 10 frames anteriores
                history_frames = corrected_keyframes[history_start_idx:i+1]  # Incluir frame actual
                
                # Intentar predecir con el contexto deportivo
                predicted_positions = self.trajectory_predictor.predict_with_context(
                    history_frames, 
                    missing_timestamps,
                    court_bounds=self.futsal_court_bounds,
                    max_sprint_speed=self.futsal_sprint_speed
                )
                
                # Si la predicción fue exitosa, crear frames con las posiciones predichas
                if predicted_positions is not None and len(predicted_positions) > 0:
                    for j, ts in enumerate(missing_timestamps):
                        predicted_frame = {
                            'timestamp': ts,
                            'position': predicted_positions[j],
                            'distances': prev_frame['distances'],
                            'statuses': prev_frame['statuses']
                        }
                        result_frames.append(predicted_frame)
                else:
                    # Si la predicción falló, realizar un fallback basado en el tamaño del gap
                    if time_gap <= 5 * self.animation_step_ms:
                        # Solo para gaps muy pequeños: interpolación lineal simple
                        simple_frames = self._interpolate_segment(prev_frame, curr_frame, None)
                        result_frames.extend(simple_frames[1:])
                    else:
                        # Para gaps medianos y grandes: transición suave
                        interp_frames = self._create_smooth_transition(
                            prev_frame, curr_frame, time_gap
                        )
                        result_frames.extend(interp_frames[1:])
            else:
                # Solo para gaps extremadamente pequeños o si ML está desactivado
                if time_gap <= 2 * self.animation_step_ms:
                    # Interpolación lineal para gaps muy pequeños (< 40ms)
                    simple_frames = self._interpolate_segment(prev_frame, curr_frame, None)
                    result_frames.extend(simple_frames[1:])
                else:
                    # Para el resto, usar transición suave
                    smooth_frames = self._create_smooth_transition(prev_frame, curr_frame, time_gap)
                    result_frames.extend(smooth_frames[1:])
            
            # Agregar el keyframe actual si no fue incluido en la interpolación/predicción
            if result_frames[-1]['timestamp'] < curr_ts:
                result_frames.append(curr_frame)
        
        # Aplicar filtro final de suavizado para eliminar movimientos bruscos residuales
        smoothed_frames = self._apply_smoothing_filter(result_frames)
        
        # Aplicar filtro de Kalman si está activado
        if self.use_kalman_filter:
            kalman_filter = self.kalman_filters.get(tag_id)
            if kalman_filter:
                filtered_frames = []
                last_ts = None
                
                for frame in smoothed_frames:
                    pos = frame['position']
                    ts = frame['timestamp']
                    
                    # Calcular dt para el modelo de velocidad
                    dt = 0.02  # Valor por defecto (20ms)
                    if last_ts is not None:
                        dt = (ts - last_ts) / 1000.0  # Convertir a segundos
                    last_ts = ts
                    
                    # Aplicar filtro
                    filtered_pos = kalman_filter.process(pos, dt)
                    
                    # Crear frame filtrado
                    filtered_frame = frame.copy()
                    filtered_frame['position'] = filtered_pos
                    filtered_frames.append(filtered_frame)
                
                # Guardar frames con filtro de Kalman aplicado
                self.animation_frames[tag_id] = filtered_frames
            else:
                self.animation_frames[tag_id] = smoothed_frames
        else:
            # Usar frames sin filtro de Kalman
            self.animation_frames[tag_id] = smoothed_frames

    def predict_trajectory(self, keyframes):
        """
        Método avanzado para predecir trayectorias entre puntos utilizando técnicas de ML simplificadas.
        Utiliza splines cúbicos y análisis de patrones de movimiento para generar trayectorias más naturales.
        """
        result_frames = [keyframes[0]]  # Comenzar con el primer keyframe
        
        # Pre-procesar para reemplazar NaNs
        processed_keyframes = self._fill_nan_positions(keyframes)
        
        # Detectar y corregir puntos que causarían movimientos extraños
        corrected_keyframes = self._correct_erratic_movements(processed_keyframes)
        
        # Extraer timestamps y posiciones para análisis
        timestamps = np.array([frame['timestamp'] for frame in corrected_keyframes])
        positions_x = np.array([frame['position'][0] for frame in corrected_keyframes])
        positions_y = np.array([frame['position'][1] for frame in corrected_keyframes])
        
        # Todos los índices son válidos ahora porque hemos rellenado los NaNs
        valid_indices = np.arange(len(corrected_keyframes))
        
        if len(valid_indices) < 3:
            # No hay suficientes puntos para splines, usar interpolación lineal tradicional
            return self._linear_interpolation(corrected_keyframes)
        
        # Procesar cada secuencia válida
        segments = self._find_continuous_segments(valid_indices)
        
        last_point = None  # Para almacenar el último punto generado (usado para suavizar)
        
        for i in range(1, len(corrected_keyframes)):
            prev_frame = corrected_keyframes[i-1]
            curr_frame = corrected_keyframes[i]
            prev_ts = prev_frame['timestamp']
            curr_ts = curr_frame['timestamp']
            prev_pos = prev_frame['position']
            curr_pos = curr_frame['position']
            
            # Si no hay cambio de tiempo o es negativo, continuar
            if curr_ts <= prev_ts:
                if result_frames[-1]['timestamp'] < curr_ts:
                    result_frames.append(curr_frame)
                    last_point = curr_pos
                continue
            
            # Calcular la velocidad directa entre puntos para detección de anomalías
            time_diff_sec = (curr_ts - prev_ts) / 1000.0  # ms a segundos
            if time_diff_sec > 0:
                direct_distance = np.sqrt((curr_pos[0] - prev_pos[0])**2 + (curr_pos[1] - prev_pos[1])**2)
                direct_speed = direct_distance / time_diff_sec
                
                # Si la velocidad es sospechosamente alta, usar un movimiento más simple
                if direct_speed > self.max_speed:
                    # Usar movimiento directo pero limitando la velocidad
                    frames = self._create_simple_motion(prev_frame, curr_frame, last_point)
                    result_frames.extend(frames[1:])
                    if frames:
                        last_point = frames[-1]['position']
                    continue
            
            # Si el salto de tiempo es muy grande, usar un enfoque específico
            if curr_ts - prev_ts > 2 * self.gap_threshold_ms:
                frames = self._create_smooth_transition(prev_frame, curr_frame, curr_ts - prev_ts, last_point)
                result_frames.extend(frames[1:])
                if frames:
                    last_point = frames[-1]['position']
                continue
                
            # Verificar si estamos en un segmento donde podemos predecir con splines
            segment_idx = self._find_segment_for_index(i, segments)
            if segment_idx is not None and len(segments[segment_idx]) >= 4:  # Mínimo 4 puntos para splines confiables
                segment = segments[segment_idx]
                
                # Tiempo entre keyframes
                time_gap = curr_ts - prev_ts
                
                # Si el salto de tiempo es pequeño, usar interpolación simple
                if time_gap <= 5 * self.animation_step_ms:
                    # Añadir frames interpolados linealmente
                    frames = self._interpolate_segment(prev_frame, curr_frame, last_point)
                    result_frames.extend(frames[1:])  # Excluir el primero para evitar duplicados
                    if frames:
                        last_point = frames[-1]['position']
                else:
                    # Para saltos grandes, utilizar predicciones basadas en splines
                    try:
                        # Extraer segmento para análisis de movimiento
                        seg_timestamps = timestamps[segment]
                        seg_positions_x = positions_x[segment]
                        seg_positions_y = positions_y[segment]
                        
                        # Calcular posiciones interpoladas
                        interp_ts = np.arange(prev_ts + self.animation_step_ms, curr_ts, self.animation_step_ms)
                        
                        # Si hay pocos puntos o están muy dispersos, usar un enfoque más conservador
                        if len(seg_timestamps) < 5 or curr_ts - prev_ts > self.gap_threshold_ms:
                            # Usar interpolación lineal con suavizado para evitar brusquedad
                            frames = self._create_smooth_linear_transition(prev_frame, curr_frame, interp_ts, last_point)
                        else:
                            # Intentar usar splines pero con restricciones estrictas
                            frames = self._create_constrained_spline_prediction(
                                prev_frame, curr_frame, 
                                seg_timestamps, seg_positions_x, seg_positions_y, 
                                interp_ts, last_point
                            )
                            
                        result_frames.extend(frames)
                        if frames:
                            last_point = frames[-1]['position']
                    except Exception as e:
                        print(f"Error en predicción avanzada: {e}. Usando interpolación simple.")
                        frames = self._interpolate_segment(prev_frame, curr_frame, last_point)
                        result_frames.extend(frames[1:])
                        if frames:
                            last_point = frames[-1]['position']
            else:
                # Usar interpolación simple con suavizado
                frames = self._interpolate_segment(prev_frame, curr_frame, last_point)
                result_frames.extend(frames[1:])
                if frames:
                    last_point = frames[-1]['position']
            
            # Asegurarse de añadir el keyframe actual si no está duplicado
            if not result_frames or result_frames[-1]['timestamp'] < curr_ts:
                result_frames.append(curr_frame)
                last_point = curr_pos
        
        # Aplicar filtro final de suavizado para eliminar cualquier movimiento extraño restante
        final_result = self._apply_smoothing_filter(result_frames)
        
        return final_result

    def _correct_erratic_movements(self, keyframes):
        """
        Detecta y corrige movimientos erráticos en los keyframes originales.
        Estos pueden surgir de errores de medición o problemas en los datos brutos.
        """
        if len(keyframes) < 3:
            return keyframes
            
        # Crear una copia para no modificar los originales
        frames = [dict(frame) for frame in keyframes]
        
        for i in range(1, len(frames) - 1):
            prev_pos = frames[i-1]['position']
            curr_pos = frames[i]['position']
            next_pos = frames[i+1]['position']
            
            prev_ts = frames[i-1]['timestamp']
            curr_ts = frames[i]['timestamp']
            next_ts = frames[i+1]['timestamp']
            
            # Detectar cambios bruscos de dirección
            if prev_ts < curr_ts < next_ts:
                # Calcular vectores de movimiento
                v1 = [curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1]]
                v2 = [next_pos[0] - curr_pos[0], next_pos[1] - curr_pos[1]]
                
                # Normalizar vectores si no son cero
                mag_v1 = np.sqrt(v1[0]**2 + v1[1]**2)
                mag_v2 = np.sqrt(v2[0]**2 + v2[1]**2)
                
                if mag_v1 > 0 and mag_v2 > 0:
                    v1 = [v1[0]/mag_v1, v1[1]/mag_v1]
                    v2 = [v2[0]/mag_v2, v2[1]/mag_v2]
                    
                    # Producto punto para ver el ángulo entre vectores
                    dot_product = v1[0]*v2[0] + v1[1]*v2[1]
                    
                    # Si los vectores forman un ángulo grande (movimiento errático)
                    # dot_product < 0 significa más de 90 grados
                    if dot_product < -0.3:  # Umbral ajustable, -1 sería exactamente opuesto
                        # Corregir la posición con una interpolación
                        alpha = (curr_ts - prev_ts) / (next_ts - prev_ts)
                        corrected_pos = [
                            prev_pos[0] + alpha * (next_pos[0] - prev_pos[0]),
                            prev_pos[1] + alpha * (next_pos[1] - prev_pos[1])
                        ]
                        frames[i]['position'] = corrected_pos
                
                # También detectar velocidades anormalmente altas
                time_prev_to_curr = (curr_ts - prev_ts) / 1000.0  # ms a segundos
                time_curr_to_next = (next_ts - curr_ts) / 1000.0
                
                if time_prev_to_curr > 0 and time_curr_to_next > 0:
                    speed_to_curr = mag_v1 / time_prev_to_curr
                    speed_from_curr = mag_v2 / time_curr_to_next
                    
                    # Si la velocidad es anormalmente alta (más de 3 m/s)
                    if speed_to_curr > self.max_speed or speed_from_curr > self.max_speed:
                        # Ajustar la posición interpolando los puntos vecinos
                        alpha = (curr_ts - prev_ts) / (next_ts - prev_ts)
                        corrected_pos = [
                            prev_pos[0] + alpha * (next_pos[0] - prev_pos[0]),
                            prev_pos[1] + alpha * (next_pos[1] - prev_pos[1])
                        ]
                        frames[i]['position'] = corrected_pos
        
        return frames

    def _fill_nan_positions(self, keyframes):
        """
        Pre-procesa los keyframes rellenando posiciones NaN con predicciones
        basadas en puntos válidos cercanos, para que no haya desapariciones del tag.
        """
        if not keyframes:
            return []
            
        # Crear una copia para no modificar los originales
        frames = [dict(frame) for frame in keyframes]
        
        # Extraer posiciones
        positions = [frame['position'] for frame in frames]
        valid_positions = [not np.isnan(pos[0]) for pos in positions]
        
        # Si no hay ninguna posición válida, no podemos hacer mucho
        if not any(valid_positions):
            # Crear posiciones artificiales en el centro del espacio experimental
            default_pos = [self.field_width / 2, self.field_length / 2]
            for i in range(len(frames)):
                frames[i]['position'] = default_pos.copy()
            return frames
            
        # Si el primer punto es NaN, rellenarlo con el primer punto válido
        if not valid_positions[0]:
            first_valid_idx = valid_positions.index(True)
            frames[0]['position'] = frames[first_valid_idx]['position'].copy()
            valid_positions[0] = True
        
        # Si el último punto es NaN, rellenarlo con el último punto válido
        if not valid_positions[-1]:
            last_valid_idx = len(valid_positions) - 1 - valid_positions[::-1].index(True)
            frames[-1]['position'] = frames[last_valid_idx]['position'].copy()
            valid_positions[-1] = True
        
        # Rellenar NaNs intermedios usando valores anterior y siguiente válidos
        i = 1
        while i < len(frames) - 1:
            if not valid_positions[i]:
                # Buscar el punto válido anterior y siguiente
                prev_valid_idx = i - 1
                while prev_valid_idx >= 0 and not valid_positions[prev_valid_idx]:
                    prev_valid_idx -= 1
                
                next_valid_idx = i + 1
                while next_valid_idx < len(frames) and not valid_positions[next_valid_idx]:
                    next_valid_idx += 1
                
                # Si encontramos ambos, interpolar
                if prev_valid_idx >= 0 and next_valid_idx < len(frames):
                    prev_pos = frames[prev_valid_idx]['position']
                    next_pos = frames[next_valid_idx]['position']
                    prev_ts = frames[prev_valid_idx]['timestamp']
                    next_ts = frames[next_valid_idx]['timestamp']
                    curr_ts = frames[i]['timestamp']
                    
                    # Interpolar posición
                    if next_ts != prev_ts:  # Evitar división por cero
                        alpha = (curr_ts - prev_ts) / (next_ts - prev_ts)
                        interpolated_x = prev_pos[0] + alpha * (next_pos[0] - prev_pos[0])
                        interpolated_y = prev_pos[1] + alpha * (next_pos[1] - prev_pos[1])
                        frames[i]['position'] = [interpolated_x, interpolated_y]
                    else:
                        # Si los timestamps son iguales, usar la posición previa
                        frames[i]['position'] = prev_pos.copy()
                    
                    valid_positions[i] = True
                elif prev_valid_idx >= 0:
                    # Si solo hay un punto válido anterior, usar ese
                    frames[i]['position'] = frames[prev_valid_idx]['position'].copy()
                    valid_positions[i] = True
                elif next_valid_idx < len(frames):
                    # Si solo hay un punto válido siguiente, usar ese
                    frames[i]['position'] = frames[next_valid_idx]['position'].copy()
                    valid_positions[i] = True
            i += 1
        
        return frames
        
    def _find_continuous_segments(self, indices):
        """Encuentra segmentos continuos de índices."""
        if len(indices) == 0:
            return []
            
        segments = []
        current_segment = [indices[0]]
        
        for i in range(1, len(indices)):
            if indices[i] == indices[i-1] + 1:
                current_segment.append(indices[i])
            else:
                if len(current_segment) >= 3:  # Mínimo 3 puntos para splines
                    segments.append(np.array(current_segment))
                current_segment = [indices[i]]
        
        if len(current_segment) >= 3:
            segments.append(np.array(current_segment))
        
        return segments

    def _find_segment_for_index(self, index, segments):
        """Determina si un índice está en algún segmento continuo."""
        for i, segment in enumerate(segments):
            if index in segment:
                return i
        return None
        
    def _linear_interpolation(self, keyframes):
        """Método tradicional de interpolación lineal."""
        new_frames = [keyframes[0]]
        
        for i in range(1, len(keyframes)):
            prev_frame = keyframes[i-1]
            curr_frame = keyframes[i]
            
            frames = self._interpolate_segment(prev_frame, curr_frame, None)
            # Añadir todos excepto el primero para evitar duplicados
            new_frames.extend(frames[1:])
            
        return new_frames

    def _create_simple_motion(self, prev_frame, curr_frame, last_point):
        """
        Crea una trayectoria directa simple entre dos puntos, respetando límites físicos.
        """
        prev_ts = prev_frame['timestamp']
        curr_ts = curr_frame['timestamp']
        prev_pos = prev_frame['position']
        curr_pos = curr_frame['position']
        
        # Calcular vector directo y distancia
        direct_vector = [curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1]]
        distance = np.sqrt(direct_vector[0]**2 + direct_vector[1]**2)
        
        # Normalizar el vector si no es cero
        if distance > 0:
            direct_vector = [direct_vector[0]/distance, direct_vector[1]/distance]
        
        # Crear timestamps intermedios
        time_diff = curr_ts - prev_ts
        num_steps = max(1, int(time_diff / self.animation_step_ms))
        interp_ts = np.linspace(prev_ts, curr_ts, num_steps + 2)[1:-1]  # Excluir extremos
        
        # Calcular tiempo en segundos
        time_diff_sec = time_diff / 1000.0
        
        # Limitar la velocidad si es necesario
        max_distance = self.max_speed * time_diff_sec
        actual_distance = min(distance, max_distance)
        
        # Distribuir la distancia total en pasos intermedios con aceleración/desaceleración
        result = []
        
        for i, ts in enumerate(interp_ts):
            # Factor de progreso no lineal (aceleración/desaceleración)
            progress = (ts - prev_ts) / time_diff
            
            # Función de ease-in/ease-out para movimiento más natural
            if progress < 0.5:
                smooth_progress = 2 * progress * progress  # Ease-in
            else:
                smooth_progress = -1 + (4 - 2 * progress) * progress  # Ease-out
            
            # Calcular posición interpolada
            current_distance = smooth_progress * actual_distance
            
            # Posición en el vector directo
            pos = [
                prev_pos[0] + current_distance * direct_vector[0],
                prev_pos[1] + current_distance * direct_vector[1]
            ]
            
            # Aplicar suavizado con el último punto si existe
            if last_point is not None:
                smooth_factor = 0.15  # Factor de suavizado menos agresivo
                pos = [
                    (1 - smooth_factor) * pos[0] + smooth_factor * last_point[0],
                    (1 - smooth_factor) * pos[1] + smooth_factor * last_point[1]
                ]
            
            result.append({
                'timestamp': ts,
                'position': pos,
                'distances': prev_frame['distances'],
                'statuses': prev_frame['statuses']
            })
            
            # Actualizar last_point para el siguiente paso
            last_point = pos
        
        return result

    def _create_smooth_transition(self, start_frame, end_frame, time_gap, last_point=None):
        """
        Crea una transición suave para saltos muy grandes utilizando
        curvas de aceleración/desaceleración (ease-in/ease-out).
        """
        start_ts = start_frame['timestamp']
        end_ts = end_frame['timestamp']
        start_pos = start_frame['position']
        end_pos = end_frame['position']
        
        # Si alguna posición es NaN, no debería pasar pero por si acaso
        if np.isnan(start_pos[0]) or np.isnan(end_pos[0]):
            # Usar posiciones por defecto
            if np.isnan(start_pos[0]):
                start_pos = [self.field_width/2, self.field_length/2]
            if np.isnan(end_pos[0]):
                end_pos = [self.field_width/2, self.field_length/2]
        
        # Calcular número de frames intermedios
        num_frames = int((end_ts - start_ts) / self.animation_step_ms)
        if num_frames < 2:
            return [start_frame, end_frame]
        
        # Calcular dirección directa y distancia
        direct_vector = [end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]]
        direct_distance = np.sqrt(direct_vector[0]**2 + direct_vector[1]**2)
        
        # Normalizar vector de dirección
        if direct_distance > 0:
            direct_vector = [direct_vector[0]/direct_distance, direct_vector[1]/direct_distance]
        else:
            direct_vector = [0, 0]
        
        # Calcular tiempo en segundos
        time_diff_sec = (end_ts - start_ts) / 1000.0
        
        # Limitar la velocidad si es necesario (para movimientos físicamente plausibles)
        max_allowed_distance = self.max_speed * time_diff_sec
        scaled_distance = min(direct_distance, max_allowed_distance)
        
        if scaled_distance < direct_distance:
            # Si limitamos la distancia, ajustar el punto final
            end_pos = [
                start_pos[0] + scaled_distance * direct_vector[0],
                start_pos[1] + scaled_distance * direct_vector[1]
            ]
        
        # Generar timestamps intermedios
        interp_ts = np.linspace(start_ts, end_ts, num_frames + 2)[1:-1]  # Excluir extremos
        
        # Función de ease-in/ease-out mejorada
        def improved_ease(t):
            # Combinación de funciones para movimiento muy suave
            if t < 0.4:
                return 3 * t * t / 0.4  # Arranque suave
            elif t < 0.6:
                return 0.3 + (t - 0.4) / 0.2 * 0.4  # Velocidad constante en el medio
            else:
                p = (t - 0.6) / 0.4
                return 0.7 + 0.3 * (1 - (1 - p) * (1 - p))  # Frenado suave
        
        # Calcular factores de interpolación con ease mejorado
        t_values = np.linspace(0, 1, num_frames)
        t_smooth = np.array([improved_ease(t) for t in t_values])
        
        # Calcular posiciones suavizadas
        x_positions = start_pos[0] + t_smooth * (end_pos[0] - start_pos[0])
        y_positions = start_pos[1] + t_smooth * (end_pos[1] - start_pos[1])
        
        # Crear frames
        result = []
        
        for i in range(len(interp_ts)):
            # Crear posición base con interpolación ease-in/ease-out
            pos = [x_positions[i], y_positions[i]]
            
            # Aplicar suavizado con el último punto conocido si existe
            if last_point is not None and i == 0:
                # Solo suavizar el primer punto para evitar desviaciones
                smooth_factor = 0.3
                pos = [
                    (1 - smooth_factor) * pos[0] + smooth_factor * last_point[0],
                    (1 - smooth_factor) * pos[1] + smooth_factor * last_point[1]
                ]
            
            result.append({
                'timestamp': interp_ts[i],
                'position': pos,
                'distances': start_frame['distances'],
                'statuses': start_frame['statuses']
            })
            
            # Actualizar last_point para el siguiente paso
            last_point = pos
        
        return result

    def _create_smooth_linear_transition(self, start_frame, end_frame, timestamps, last_point=None):
        """
        Crea una transición lineal suavizada entre dos puntos.
        Más conservadora que los splines para evitar comportamientos extraños.
        """
        start_pos = start_frame['position']
        end_pos = end_frame['position']
        
        result = []
        
        # Calcular vector directo
        direct_vector = [end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]]
        
        for i, ts in enumerate(timestamps):
            # Interpolación lineal básica
            alpha = (ts - start_frame['timestamp']) / (end_frame['timestamp'] - start_frame['timestamp'])
            
            # Aplicar un poco de ease-in/ease-out para que no sea perfectamente lineal
            if alpha < 0.5:
                smooth_alpha = 2 * alpha * alpha
            else:
                smooth_alpha = -1 + (4 - 2 * alpha) * alpha
            
            # Posición interpolada
            pos = [
                start_pos[0] + smooth_alpha * direct_vector[0],
                start_pos[1] + smooth_alpha * direct_vector[1]
            ]
            
            # Aplicar suavizado con punto anterior si existe y es el primer punto
            if last_point is not None and i == 0:
                smooth_factor = 0.2
                pos = [
                    (1 - smooth_factor) * pos[0] + smooth_factor * last_point[0],
                    (1 - smooth_factor) * pos[1] + smooth_factor * last_point[1]
                ]
            
            result.append({
                'timestamp': ts,
                'position': pos,
                'distances': start_frame['distances'],
                'statuses': start_frame['statuses']
            })
        
        return result

    def _create_constrained_spline_prediction(self, start_frame, end_frame, timestamps, positions_x, positions_y, interp_ts, last_point=None):
        """
        Crea predicciones basadas en splines pero con restricciones estrictas
        para evitar comportamientos erráticos.
        """
        try:
            # Crear splines cúbicos
            cs_x = CubicSpline(timestamps, positions_x)
            cs_y = CubicSpline(timestamps, positions_y)
            
            # Predecir posiciones
            pred_x = cs_x(interp_ts)
            pred_y = cs_y(interp_ts)
            
            # Calcular posiciones esperadas con interpolación lineal (para comparación)
            start_pos = start_frame['position']
            end_pos = end_frame['position']
            expected_x = np.linspace(start_pos[0], end_pos[0], len(interp_ts))
            expected_y = np.linspace(start_pos[1], end_pos[1], len(interp_ts))
            
            # Corregir las predicciones para evitar comportamientos erráticos
            corrected_frames = []
            
            # Vector de dirección principal
            dir_vector = [end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]]
            dir_mag = np.sqrt(dir_vector[0]**2 + dir_vector[1]**2)
            
            if dir_mag > 0:
                dir_vector = [dir_vector[0]/dir_mag, dir_vector[1]/dir_mag]
                
                # Máxima desviación permitida del camino directo
                max_deviation = 0.3  # metros
                
                for i in range(len(interp_ts)):
                    # Calcular desviación de la línea directa
                    point_to_line_vector = [
                        pred_x[i] - expected_x[i],
                        pred_y[i] - expected_y[i]
                    ]
                    
                    # Proyección perpendicular (desviación)
                    deviation = abs(point_to_line_vector[0] * (-dir_vector[1]) + 
                                   point_to_line_vector[1] * dir_vector[0])
                    
                    # Si la desviación es demasiado grande, mezclar con la trayectoria directa
                    if deviation > max_deviation:
                        blend_factor = max_deviation / deviation
                        pred_x[i] = blend_factor * pred_x[i] + (1 - blend_factor) * expected_x[i]
                        pred_y[i] = blend_factor * pred_y[i] + (1 - blend_factor) * expected_y[i]
                    
                    # Comprobar también que no se mueva demasiado rápido
                    if i > 0:
                        # Calcular velocidad entre puntos consecutivos
                        dt = (interp_ts[i] - interp_ts[i-1]) / 1000.0  # segundos
                        dx = pred_x[i] - pred_x[i-1]
                        dy = pred_y[i] - pred_y[i-1]
                        speed = np.sqrt(dx*dx + dy*dy) / dt
                        
                        # Limitar la velocidad si es necesario
                        if speed > self.max_speed:
                            scale_factor = self.max_speed / speed
                            # Ajustar solo el punto actual, no el anterior
                            pred_x[i] = pred_x[i-1] + dx * scale_factor
                            pred_y[i] = pred_y[i-1] + dy * scale_factor
            
            # Aplicar suavizado adicional para el primer punto si tenemos un punto anterior
            pos_first = [pred_x[0], pred_y[0]]
            if last_point is not None:
                smooth_factor = 0.3
                pos_first = [
                    (1 - smooth_factor) * pos_first[0] + smooth_factor * last_point[0],
                    (1 - smooth_factor) * pos_first[1] + smooth_factor * last_point[1]
                ]
                pred_x[0], pred_y[0] = pos_first
            
            # Crear los frames con las posiciones corregidas
            for i in range(len(interp_ts)):
                corrected_frames.append({
                    'timestamp': interp_ts[i],
                    'position': [pred_x[i], pred_y[i]],
                    'distances': start_frame['distances'],
                    'statuses': start_frame['statuses']
                })
            
            return corrected_frames
            
        except Exception as e:
            print(f"Error en splines con restricciones: {e}")
            # Fallback a interpolación lineal suavizada
            return self._create_smooth_linear_transition(start_frame, end_frame, interp_ts, last_point)

    def _interpolate_segment(self, prev_frame, curr_frame, last_point=None):
        """Interpolación lineal simple entre dos frames."""
        prev_ts = prev_frame['timestamp']
        curr_ts = curr_frame['timestamp']
        prev_pos = prev_frame['position']
        curr_pos = curr_frame['position']
        
        result = [prev_frame]  # Incluir el frame inicial
        
        # En este punto, las posiciones siempre deberían ser válidas debido al pre-procesamiento
        current_ts = prev_ts + self.animation_step_ms
        
        while current_ts < curr_ts:
            alpha = (current_ts - prev_ts) / (curr_ts - prev_ts)
            interp_pos = [
                prev_pos[0] + alpha * (curr_pos[0] - prev_pos[0]),
                prev_pos[1] + alpha * (curr_pos[1] - prev_pos[1])
            ]
            
            # Aplicar suavizado con punto anterior si existe y es el primer punto
            if last_point is not None and current_ts == prev_ts + self.animation_step_ms:
                smooth_factor = 0.15  # Factor menor para suavizado sutil
                interp_pos = [
                    (1 - smooth_factor) * interp_pos[0] + smooth_factor * last_point[0],
                    (1 - smooth_factor) * interp_pos[1] + smooth_factor * last_point[1]
                ]
            
            result.append({
                'timestamp': current_ts,
                'position': interp_pos,
                'distances': prev_frame['distances'],
                'statuses': prev_frame['statuses']
            })
            
            # Actualizar last_point para el siguiente punto
            last_point = interp_pos
            current_ts += self.animation_step_ms
        
        return result

    def _apply_smoothing_filter(self, frames):
        """
        Aplica un filtro de suavizado a la trayectoria completa para eliminar
        cualquier movimiento brusco o errático.
        """
        if len(frames) < 3:
            return frames
            
        # Crear copia para no modificar los originales
        smoothed_frames = [dict(frame) for frame in frames]
        
        # Primer y último punto se mantienen iguales
        for i in range(1, len(smoothed_frames) - 1):
            prev_pos = frames[i-1]['position']
            curr_pos = frames[i]['position']
            next_pos = frames[i+1]['position']
            
            # Factor de suavizado depende de la velocidad
            prev_ts = frames[i-1]['timestamp']
            curr_ts = frames[i]['timestamp']
            next_ts = frames[i+1]['timestamp']
            
            try:
                # Calcular velocidades
                dt_prev = (curr_ts - prev_ts) / 1000.0  # segundos
                dt_next = (next_ts - curr_ts) / 1000.0
                
                if dt_prev > 0 and dt_next > 0:
                    dx_prev = (curr_pos[0] - prev_pos[0])
                    dy_prev = (curr_pos[1] - prev_pos[1])
                    speed_prev = np.sqrt(dx_prev*dx_prev + dy_prev*dy_prev) / dt_prev
                    
                    dx_next = (next_pos[0] - curr_pos[0])
                    dy_next = (next_pos[1] - curr_pos[1])
                    speed_next = np.sqrt(dx_next*dx_next + dy_next*dy_next) / dt_next
                    
                    # Si hay un cambio brusco de velocidad, aplicar más suavizado
                    speed_ratio = max(speed_prev, speed_next) / (min(speed_prev, speed_next) + 0.01)
                    dynamic_factor = min(0.4, 0.1 + 0.3 * (speed_ratio - 1) / 10)
                else:
                    dynamic_factor = 0.2  # Valor por defecto
            except:
                dynamic_factor = 0.2  # En caso de error
            
            # Media ponderada para suavizar
            smoothed_pos = [
                (1 - dynamic_factor) * curr_pos[0] + dynamic_factor * 0.5 * (prev_pos[0] + next_pos[0]),
                (1 - dynamic_factor) * curr_pos[1] + dynamic_factor * 0.5 * (prev_pos[1] + next_pos[1])
            ]
            
            smoothed_frames[i]['position'] = smoothed_pos
        
        return smoothed_frames

    def create_visualization(self):
        """Crea la visualización y la animación."""
        
        # Configuración de la figura
        plt.close('all')  # Cerrar figuras anteriores
        plt.ioff()  # Desactivar modo interactivo durante la creación
        
        self.fig, self.ax = plt.subplots(figsize=(12, 9))
        self.fig.canvas.manager.set_window_title('Visualizador de Tag UWB')
        
        # Configurar límites del área con espacio adicional para visibilidad
        margin = 0.5  # margen en metros alrededor del área
        self.ax.set_xlim(-margin, self.field_width + margin)
        self.ax.set_ylim(-margin, self.field_length + margin)
        
        # Dibujar el contorno del área experimental
        rect = plt.Rectangle((0, 0), self.field_width, self.field_length, 
                            fill=False, linestyle='-', linewidth=2, color='gray')
        self.ax.add_patch(rect)
        
        # Configurar estética
        self.ax.set_xlabel('X (metros)', fontsize=12)
        self.ax.set_ylabel('Y (metros)', fontsize=12)
        self.ax.set_title(f'Posicionamiento UWB - Espacio {self.field_width}m x {self.field_length}m', fontsize=14)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        
        # Dibujar anchors
        for anchor_id, props in self.anchors.items():
            pos = props['position']
            # Store plot object to update alpha later
            self.anchor_plots[anchor_id] = self.ax.plot(pos[0], pos[1], 'o', markersize=10, color=props['color'], label=props['label'])[0]
            self.ax.text(pos[0] + 0.1, pos[1], str(anchor_id))
            # Inicializar círculos de radio (ocultos)
            self.radius_circles[anchor_id] = plt.Circle((pos[0], pos[1]), 0.1, color=props['color'], fill=False, linestyle='--', visible=False)
            self.ax.add_patch(self.radius_circles[anchor_id])
        
        # Plot inicial para el tag (se moverá en update)
        initial_pos = [np.nan, np.nan] # Start off-screen or at NaN
        if self.selected_tag_id and self.animation_frames.get(self.selected_tag_id) and len(self.animation_frames[self.selected_tag_id]) > 0:
            first_frame_data = self.animation_frames[self.selected_tag_id][0]
            if not np.isnan(first_frame_data['position'][0]):
                 initial_pos = first_frame_data['position']
 
        self.tag_plots[self.selected_tag_id] = self.ax.plot(initial_pos[0], initial_pos[1], 'X', markersize=12, color='black', label=f'Tag {self.selected_tag_id}')[0]
        
        # Inicializar rastro de movimiento
        if self.show_trail:
            self.trail_plots[self.selected_tag_id] = self.ax.plot([], [], 'o-', color='blue', alpha=0.5, 
                                                                 linewidth=2, markersize=3, zorder=0)[0]

        # Añadir texto para información
        self.info_text = self.ax.text(0.02, 0.95, '', transform=self.ax.transAxes, verticalalignment='top', 
                                      bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.5))
        self.time_text = self.ax.text(0.98, 0.95, '', transform=self.ax.transAxes, verticalalignment='top', horizontalalignment='right',
                                     bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.5))

        # Ajustar márgenes y establecer aspecto igual para dimensiones correctas
        plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.15)
        self.ax.set_aspect('equal')
        
        # Añadir controles de forma más visible
        axcolor = 'lightgoldenrodyellow'
        play_ax = plt.axes([0.78, 0.04, 0.1, 0.05])
        self.play_button = plt.Button(play_ax, 'Play/Pause', color=axcolor)
        self.play_button.on_clicked(self.toggle_play)
        
        reset_ax = plt.axes([0.89, 0.04, 0.1, 0.05])
        self.reset_button = plt.Button(reset_ax, 'Reset', color=axcolor)
        self.reset_button.on_clicked(self.reset_animation)
        
        # Iniciar la animación con intervalo más corto para fluidez
        self.animation = FuncAnimation(
            self.fig, 
            self.update, 
            frames=range(self.total_frames),
            interval=self.animation_step_ms,  # Sincronizar con el paso de los frames interpolados
            blit=True,  # Mantener blit=True para rendimiento
            repeat=True
        )
    
    def update(self, frame):
        """Actualiza la animación para el cuadro actual."""
        if not self.playing or frame >= self.total_frames:
            self.playing = False # Stop if paused or reached end
            return [] # No updates
            
        self.current_frame = frame
        
        # Usar animation_frames en lugar de self.positions
        if self.selected_tag_id not in self.animation_frames or frame >= len(self.animation_frames[self.selected_tag_id]):
            print(f"Frame {frame} fuera de rango para los frames animados del tag {self.selected_tag_id}")
            return []
            
        current_data = self.animation_frames[self.selected_tag_id][frame]
        position = current_data['position']
        distances = current_data['distances']
        statuses = current_data['statuses']
        timestamp_ms = current_data['timestamp']

        # Actualizar posición del tag si es válida
        if position is not None and not np.isnan(position[0]):
            self.tag_plots[self.selected_tag_id].set_data([position[0]], [position[1]]) # Wrap in lists
            self.tag_plots[self.selected_tag_id].set_visible(True)
            # Store the last valid position only if current position is valid
            self.last_valid_position = position 
        else:
            # Position is NaN for the current animation frame, make tag invisible
            self.tag_plots[self.selected_tag_id].set_visible(False)
            # position variable para el texto ya es [np.nan, np.nan] o similar desde generate_interpolated_frames
            # o se actualizará aquí para el texto informativo si es necesario
            if position is None: position = [np.nan, np.nan] # Asegurar para el texto

        # Actualizar rastro de movimiento si está activado
        if self.show_trail and self.selected_tag_id in self.trail_plots:
            # Recopilar posiciones del rastro (últimos trail_length frames)
            start_frame = max(0, frame - self.trail_length)
            trail_x = []
            trail_y = []
            
            for i in range(start_frame, frame + 1):
                if i < len(self.animation_frames[self.selected_tag_id]):
                    trail_frame = self.animation_frames[self.selected_tag_id][i]
                    trail_pos = trail_frame['position']
                    if not np.isnan(trail_pos[0]):
                        trail_x.append(trail_pos[0])
                        trail_y.append(trail_pos[1])
            
            # Actualizar datos del rastro
            if trail_x:
                # Aplicar degradado de color según la longitud
                self.trail_plots[self.selected_tag_id].set_data(trail_x, trail_y)
                self.trail_plots[self.selected_tag_id].set_visible(True)
            else:
                self.trail_plots[self.selected_tag_id].set_visible(False)

        info_str = f'Tag: {self.selected_tag_id}\nFrame: {frame}/{self.total_frames-1}\n' \
                   f'Pos (X,Y): ({position[0]:.2f}, {position[1]:.2f}) m\nDistances (m):\n'

        # Actualizar círculos de radio y estado de anchors
        for anchor_id, props in self.anchors.items():
            dist = distances.get(anchor_id, np.nan)
            status = statuses.get(anchor_id, 0) # Default to 0 (Fail) if missing
            
            # Update anchor visual status
            if status == 1:
                self.anchor_plots[anchor_id].set_alpha(1.0) # Full opacity if OK
            else:
                self.anchor_plots[anchor_id].set_alpha(0.3) # Faded if FAIL

            info_str += f"  A{anchor_id}: {dist:.2f} ({'OK' if status==1 else 'FAIL'})\n"
            
            # Actualizar círculo (opcional)
            circle = self.radius_circles[anchor_id]
            if not np.isnan(dist) and dist > 0 and status == 1:
                circle.set_radius(dist)
                circle.center = self.anchor_plots[anchor_id].get_data() # Center on anchor
                circle.set_visible(True)
            else:
                circle.set_visible(False)

        self.info_text.set_text(info_str)
        
        # Actualizar tiempo
        # Asegurarse de que hay frames y timestamps para calcular el tiempo transcurrido
        if self.animation_frames.get(self.selected_tag_id) and len(self.animation_frames[self.selected_tag_id]) > 0:
            first_timestamp_ms = self.animation_frames[self.selected_tag_id][0]['timestamp']
            elapsed_time_s = (timestamp_ms - first_timestamp_ms) / 1000.0
            self.time_text.set_text(f'Tiempo: {elapsed_time_s:.2f} s')
        else:
            self.time_text.set_text('Tiempo: N/A')

        # Devolver los elementos modificados para blitting
        updated_elements = [self.tag_plots[self.selected_tag_id], self.info_text, self.time_text] + \
                           list(self.radius_circles.values()) + list(self.anchor_plots.values())
        
        # Añadir rastro a la lista de elementos actualizados
        if self.show_trail and self.selected_tag_id in self.trail_plots:
            updated_elements.append(self.trail_plots[self.selected_tag_id])
            
        return updated_elements

    def toggle_play(self, event):
        """Alterna entre reproducir y pausar la animación."""
        self.playing = not self.playing
        if self.playing:
            print("Reproduciendo...")
        else:
            print("Pausado.")

    def reset_animation(self, event):
        """Reinicia la animación al principio."""
        self.current_frame = 0
        print("Animación reiniciada.")
        self.update(0)  # Actualizar visualización al frame inicial
        plt.draw()      # Refrescar la visualización

    def run(self):
        """Ejecuta el visor completo con funcionalidad interactiva."""
        # Cargar datos directamente desde una ruta específica
        csv_file = self.select_csv_file()
        if csv_file is None:
            print("No se seleccionó archivo CSV. Saliendo.")
            return
        
        if self.load_data(csv_file):
            # Crear la visualización y la animación
            self.create_visualization()
            
            # Activar reproducción inmediata
            self.playing = True
            print("Iniciando reproducción automática...")
            
            # Mantener referencia a la animación y mostrar
            try:
                plt.show(block=True)
            except KeyboardInterrupt:
                print("Visualización interrumpida por el usuario")
            
            # Forzar cierre de todas las figuras al salir
            plt.close('all')
            
            # Mostrar el mapa de calor solo si se cerró la animación normalmente
            print("\nGenerando mapa de calor...")
            self.generate_heatmap()
            plt.show()
        else:
            print("No se pudieron cargar los datos. Saliendo.")

    def select_csv_file(self):
        """Abre un diálogo para seleccionar un archivo CSV de datos."""
        root = Tk()
        root.withdraw()  # Ocultar la ventana principal
        
        # Directorio inicial para el diálogo
        initial_dir = os.path.join(os.getcwd(), "data_recordings")
        if not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
        
        # Abrir diálogo para seleccionar archivo
        file_path = filedialog.askopenfilename(
            title="Seleccione un archivo CSV de datos",
            initialdir=initial_dir,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        root.destroy()
        
        if file_path:
            print(f"Archivo seleccionado: {file_path}")
            return file_path
        else:
            print("No se seleccionó ningún archivo.")
            return None

    def generate_heatmap(self):
        """Genera un mapa de calor de las posiciones del tag."""
        if not hasattr(self, 'positions') or len(self.positions) == 0:
            print("No hay datos cargados para generar el mapa de calor.")
            return
        
        # Extraer todas las posiciones
        positions = np.array([p['position'] for p in self.positions[self.selected_tag_id]])
        
        # Filtrar posiciones NaN antes de calcular límites y el heatmap
        valid_positions = [pos for pos in positions if not np.isnan(pos[0]) and not np.isnan(pos[1])]
        if not valid_positions:
            print("No hay posiciones válidas para generar el mapa de calor.")
            return

        positions_array = np.array(valid_positions)
        min_x, min_y = np.min(positions_array, axis=0)
        max_x, max_y = np.max(positions_array, axis=0)

        # Añadir un margen para asegurar que todos los puntos estén dentro
        margin = 1.0 # Ajusta este margen según sea necesario
        self.field_width = (max_x - min_x) + 2 * margin
        self.field_height = (max_y - min_y) + 2 * margin
        self.origin_offset = np.array([min_x - margin, min_y - margin])

        if self.field_width <= 0 or self.field_height <= 0:
             print(f"Dimensiones del campo inválidas: width={self.field_width}, height={self.field_height}. Ajustando a valores mínimos.")
             # Asignar un tamaño mínimo si las dimensiones son inválidas o cero
             self.field_width = max(self.field_width, margin * 2)
             self.field_height = max(self.field_height, margin * 2)
             # Recalcular el offset si es necesario basado en un punto de referencia o dejarlo como está

        grid_size = 100  # Tamaño de la cuadrícula para el mapa de calor
        heatmap = np.zeros((grid_size, grid_size))

        for pos in valid_positions: # Usar solo posiciones válidas
            # Normalizar posición relativa al origen del heatmap (esquina inferior izquierda)
            relative_pos = pos - self.origin_offset

            # Asegurarse de que relative_pos no contenga NaN (aunque ya filtramos, doble chequeo)
            if np.isnan(relative_pos[0]) or np.isnan(relative_pos[1]):
                continue # Saltar este punto si es NaN

            # Calcular índices en la cuadrícula, asegurándose de que estén dentro de los límites
            # Evitar división por cero si field_width o field_height son <= 0
            if self.field_width > 0 and self.field_height > 0:
                 x_idx = int(relative_pos[0] / self.field_width * (grid_size - 1))
                 y_idx = int(relative_pos[1] / self.field_height * (grid_size - 1))

                 # Asegurarse de que los índices estén dentro del rango [0, grid_size-1]
                 x_idx = np.clip(x_idx, 0, grid_size - 1)
                 y_idx = np.clip(y_idx, 0, grid_size - 1)

                 heatmap[y_idx, x_idx] += 1 # Incrementar la celda correspondiente
            else:
                 # Opcional: Loguear si se salta un punto debido a dimensiones inválidas
                 # print(f"Skipping point {pos} due to invalid field dimensions.")
                 pass

        if np.sum(heatmap) == 0:
            print("No hay datos válidos para el mapa de calor.")
            return

        # Crear figura
        plt.figure(figsize=(10, 8))
        
        # Dibujar mapa de calor
        plt.imshow(heatmap, extent=[0, self.field_width, 0, self.field_height], 
                  origin='lower', cmap='hot', interpolation='bilinear')
        
        plt.colorbar(label='Densidad de posiciones')
        
        # Dibujar anchors
        for anchor_id, data in self.anchors.items():
            x, y = data['position'][0], data['position'][1]
            plt.plot(x, y, 'o', color=data['color'], markersize=10)
            plt.text(x, y, f" {anchor_id}", fontsize=10, verticalalignment='bottom')
        
        # Configuración adicional
        plt.title('Mapa de calor de posiciones')
        plt.xlabel('X (metros)')
        plt.ylabel('Y (metros)')
        plt.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout()
        plt.show()

class TrajectoryPredictor:
    """
    Clase especializada en predicción de trayectorias usando Gaussian Process Regression (GPR)
    con optimizaciones específicas para movimientos de fútbol sala.
    """
    def __init__(self, context="futsal"):
        self.context = context
        self.x_model = None
        self.y_model = None
        self.min_samples_required = 5
        self.history_window = 10 # Número de frames históricos a considerar
        self.is_trained = False
        self.min_ts = 0
        self.max_ts = 0
        
        # Seleccionar kernel de acuerdo al contexto deportivo
        if context == "futsal":
            # Kernel simplificado para fútbol sala - evita problemas de convergencia
            # Matern es bueno para cambios bruscos de dirección (nu=1.5)
            length_scale_bounds = (1e-3, 25.0)   # Ampliamos el límite superior
            noise_level_bounds = (1e-8, 1.0)     # Reducimos el límite inferior
            
            # Valores fijos que sabemos que funcionan bien para fútbol sala
            # en lugar de depender tanto de la optimización
            self.kernel_x = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                           WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
            
            self.kernel_y = 1.0 * Matern(length_scale=0.5, nu=1.5, length_scale_bounds=length_scale_bounds) + \
                           WhiteKernel(noise_level=0.01, noise_level_bounds=noise_level_bounds)
        else:
            # Kernel general para otros contextos - también ajustado
            self.kernel_x = 1.0 * RBF(length_scale=0.3, length_scale_bounds=(1e-3, 25.0)) + \
                           WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-8, 1.0))
            self.kernel_y = 1.0 * RBF(length_scale=0.3, length_scale_bounds=(1e-3, 25.0)) + \
                           WhiteKernel(noise_level=0.01, noise_level_bounds=(1e-8, 1.0))
    
    def train(self, frames):
        """
        Entrena los modelos GPR usando los frames históricos.
        """
        if len(frames) < self.min_samples_required:
            self.is_trained = False
            return False
        
        # Extraer datos de entrenamiento
        timestamps = np.array([frame['timestamp'] for frame in frames])
        positions = np.array([frame['position'] for frame in frames])
        
        # Filtrar frames con posiciones válidas
        valid_indices = ~np.isnan(positions[:, 0])
        valid_timestamps = timestamps[valid_indices]
        valid_positions = positions[valid_indices]
        
        if len(valid_timestamps) < self.min_samples_required:
            self.is_trained = False
            return False
        
        # Almacenar min/max de timestamps para normalización futura
        self.min_ts = min(valid_timestamps)
        self.max_ts = max(valid_timestamps)
        ts_range = self.max_ts - self.min_ts
        
        if ts_range <= 0:
            self.is_trained = False
            return False
        
        # Normalizar timestamps para el entrenamiento
        norm_timestamps = (valid_timestamps - self.min_ts) / ts_range
        norm_timestamps = norm_timestamps.reshape(-1, 1)  # Reshape para scikit-learn
        
        # Crear y entrenar modelos GPR con optimizaciones mejoradas
        try:
            # Primero intentamos con optimización limitada
            self.x_model = GaussianProcessRegressor(
                kernel=self.kernel_x, 
                alpha=1e-5,
                normalize_y=True, 
                n_restarts_optimizer=1  # Reducimos a 1 para menos advertencias
            )
            
            self.y_model = GaussianProcessRegressor(
                kernel=self.kernel_y, 
                alpha=1e-5,
                normalize_y=True, 
                n_restarts_optimizer=1  # Reducimos a 1 para menos advertencias
            )
            
            # Silenciar advertencias durante el entrenamiento
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.x_model.fit(norm_timestamps, valid_positions[:, 0])
                self.y_model.fit(norm_timestamps, valid_positions[:, 1])
                
            self.is_trained = True
            return True
            
        except Exception as e:
            print(f"Error en entrenamiento GPR: {e}")
            # Fallback a modelo más simple sin optimización
            try:
                # Si falla, intentar con un modelo más simple
                from sklearn.gaussian_process.kernels import ConstantKernel
                simple_kernel = ConstantKernel(1.0) * Matern(length_scale=0.5, nu=1.5)
                
                self.x_model = GaussianProcessRegressor(
                    kernel=simple_kernel,
                    alpha=1e-4, 
                    normalize_y=True,
                    optimizer=None  # Desactivar optimización
                )
                
                self.y_model = GaussianProcessRegressor(
                    kernel=simple_kernel,
                    alpha=1e-4, 
                    normalize_y=True,
                    optimizer=None  # Desactivar optimización
                )
                
                self.x_model.fit(norm_timestamps, valid_positions[:, 0])
                self.y_model.fit(norm_timestamps, valid_positions[:, 1])
                
                self.is_trained = True
                return True
            except:
                self.is_trained = False
                return False
    
    def predict(self, target_timestamps, max_speed=5.0, court_bounds=None, last_velocity=None):
        """
        Predice posiciones para los timestamps objetivo usando los modelos entrenados.
        Aplica restricciones físicas específicas para fútbol sala.
        
        Args:
            target_timestamps: Lista de timestamps para los que predecir posiciones
            max_speed: Velocidad máxima permitida (m/s)
            court_bounds: Límites de la cancha [x_min, x_max, y_min, y_max]
            last_velocity: Vector de velocidad del último movimiento conocido
            
        Returns:
            Lista de posiciones predichas (x, y)
        """
        if not self.is_trained or self.x_model is None or self.y_model is None:
            return None
        
        if len(target_timestamps) == 0:
            return []
        
        # Normalizar timestamps objetivo
        ts_range = self.max_ts - self.min_ts
        norm_ts = (np.array(target_timestamps) - self.min_ts) / ts_range
        norm_ts = norm_ts.reshape(-1, 1)
        
        # Predicción inicial con GPR
        pred_x, std_x = self.x_model.predict(norm_ts, return_std=True)
        pred_y, std_y = self.y_model.predict(norm_ts, return_std=True)
        
        # Inicializar resultado
        predictions = []
        last_pos = None
        last_ts = None
        
        # Aplicar restricciones físicas a cada predicción
        for i in range(len(target_timestamps)):
            pos = [pred_x[i], pred_y[i]]
            ts = target_timestamps[i]
            
            # Verificar límites de la cancha si están definidos
            if court_bounds is not None:
                pos[0] = max(court_bounds[0], min(court_bounds[1], pos[0]))
                pos[1] = max(court_bounds[2], min(court_bounds[3], pos[1]))
            
            # Aplicar restricciones de velocidad/aceleración entre puntos
            if last_pos is not None and last_ts is not None:
                dt = (ts - last_ts) / 1000.0  # segundos
                if dt > 0:
                    # Calcular velocidad actual
                    dx = pos[0] - last_pos[0]
                    dy = pos[1] - last_pos[1]
                    distance = np.sqrt(dx*dx + dy*dy)
                    current_speed = distance / dt
                    
                    # Si supera velocidad máxima, limitar manteniendo dirección
                    if current_speed > max_speed:
                        scale_factor = max_speed / current_speed
                        pos[0] = last_pos[0] + dx * scale_factor
                        pos[1] = last_pos[1] + dy * scale_factor
                    
                    # Considerar aceleración si tenemos la velocidad anterior
                    if last_velocity is not None:
                        # Calcular aceleración como cambio de velocidad
                        new_velocity = [(pos[0] - last_pos[0])/dt, (pos[1] - last_pos[1])/dt]
                        accel_x = (new_velocity[0] - last_velocity[0]) / dt
                        accel_y = (new_velocity[1] - last_velocity[1]) / dt
                        accel_magnitude = np.sqrt(accel_x*accel_x + accel_y*accel_y)
                        
                        # Si aceleración es demasiado alta, limitar
                        MAX_ACCEL = 4.0  # m/s²
                        if accel_magnitude > MAX_ACCEL:
                            accel_scale = MAX_ACCEL / accel_magnitude
                            # Ajustar velocidad nueva con aceleración limitada
                            adjusted_velocity_x = last_velocity[0] + accel_x * accel_scale * dt
                            adjusted_velocity_y = last_velocity[1] + accel_y * accel_scale * dt
                            # Calcular nueva posición con velocidad ajustada
                            pos[0] = last_pos[0] + adjusted_velocity_x * dt
                            pos[1] = last_pos[1] + adjusted_velocity_y * dt
                        
                        # Actualizar last_velocity para la siguiente iteración
                        last_velocity = [(pos[0] - last_pos[0])/dt, (pos[1] - last_pos[1])/dt]
                    else:
                        # Inicializar last_velocity
                        last_velocity = [(pos[0] - last_pos[0])/dt, (pos[1] - last_pos[1])/dt]
            
            # Almacenar posición actual
            predictions.append(pos)
            last_pos = pos
            last_ts = ts
        
        return predictions

    def predict_with_context(self, frames, missing_timestamps, court_bounds=None, max_sprint_speed=7.0):
        """
        Predice trayectorias considerando el contexto de fútbol sala, incluyendo:
        - Sprints y aceleraciones repentinas
        - Cambios tácticos de dirección
        - Limitaciones físicas realistas
        
        Args:
            frames: Historial de frames con posiciones conocidas
            missing_timestamps: Timestamps donde necesitamos predecir posiciones
            court_bounds: Límites de la cancha
            max_sprint_speed: Velocidad máxima en sprint (m/s)
            
        Returns:
            Lista de posiciones predichas
        """
        if len(frames) < self.min_samples_required or len(missing_timestamps) == 0:
            return None
        
        # Encontrar los frames más recientes para el entrenamiento
        recent_frames = frames[-min(len(frames), self.history_window):]
        
        # Entrenar modelo
        if not self.train(recent_frames):
            return None
        
        # Analizar comportamiento reciente para detectar patrones
        is_sprinting = self._detect_sprint(recent_frames)
        last_velocity = self._calculate_last_velocity(recent_frames)
        avg_speed = self._calculate_average_speed(recent_frames)
        
        # Ajustar velocidad máxima según comportamiento detectado
        max_speed = max_sprint_speed if is_sprinting else avg_speed * 1.2
        
        # Realizar predicción con restricciones adaptadas
        predictions = self.predict(missing_timestamps, max_speed, court_bounds, last_velocity)
        
        return predictions
    
    def _detect_sprint(self, frames):
        """Detecta si el jugador está en sprint basado en velocidades recientes."""
        if len(frames) < 3:
            return False
        
        speeds = []
        for i in range(1, len(frames)):
            ts_diff = (frames[i]['timestamp'] - frames[i-1]['timestamp']) / 1000.0
            if ts_diff > 0:
                try:
                    pos_curr = frames[i]['position']
                    pos_prev = frames[i-1]['position']
                    if np.isnan(pos_curr[0]) or np.isnan(pos_prev[0]):
                        continue
                    
                    distance = np.sqrt((pos_curr[0] - pos_prev[0])**2 + 
                                      (pos_curr[1] - pos_prev[1])**2)
                    speeds.append(distance / ts_diff)
                except:
                    continue
        
        if not speeds:
            return False
        
        # Consideramos sprint si la velocidad promedio reciente supera el umbral
        avg_speed = np.mean(speeds)
        SPRINT_THRESHOLD = 4.0  # m/s
        
        return avg_speed > SPRINT_THRESHOLD
    
    def _calculate_last_velocity(self, frames):
        """Calcula el vector de velocidad del último movimiento."""
        if len(frames) < 2:
            return None
        
        try:
            last_frame = frames[-1]
            prev_frame = frames[-2]
            
            pos_last = last_frame['position']
            pos_prev = prev_frame['position']
            
            if np.isnan(pos_last[0]) or np.isnan(pos_prev[0]):
                return None
            
            dt = (last_frame['timestamp'] - prev_frame['timestamp']) / 1000.0
            if dt <= 0:
                return None
            
            vx = (pos_last[0] - pos_prev[0]) / dt
            vy = (pos_last[1] - pos_prev[1]) / dt
            
            return [vx, vy]
        except:
            return None
    
    def _calculate_average_speed(self, frames):
        """Calcula la velocidad promedio a partir de los frames recientes."""
        speeds = []
        
        for i in range(1, len(frames)):
            try:
                pos_curr = frames[i]['position']
                pos_prev = frames[i-1]['position']
                
                if np.isnan(pos_curr[0]) or np.isnan(pos_prev[0]):
                    continue
                
                dt = (frames[i]['timestamp'] - frames[i-1]['timestamp']) / 1000.0
                if dt <= 0:
                    continue
                
                distance = np.sqrt((pos_curr[0] - pos_prev[0])**2 + 
                                  (pos_curr[1] - pos_prev[1])**2)
                speeds.append(distance / dt)
            except:
                continue
        
        if not speeds:
            return 2.0  # Valor por defecto en m/s si no hay datos
        
        return np.mean(speeds)

if __name__ == "__main__":
    replay = TagReplay()
    replay.run()
