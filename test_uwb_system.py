#!/usr/bin/env python3
"""
Tests del Sistema UWB usando pytest - Verificación de funcionalidad crítica
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import sys
import logging
from datetime import datetime, timedelta

# Configurar matplotlib para modo headless (CI/testing)
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI para tests

# Importar el sistema principal
from movement_replay import KalmanPositionFilter, TrajectoryPredictor, FutsalReplaySystem, generate_movement_report

# Configurar logging para tests (WARNING para CI, INFO para desarrollo)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba reutilizables con timestamps fijos"""
    # Usar timestamp fijo para reproducibilidad
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    timestamps = [base_time + timedelta(milliseconds=i*50) for i in range(50)]  # 50ms gap
    
    # Crear datos determinísticos pero con ruido controlado
    np.random.seed(42)  # Seed fijo para reproducibilidad
    df = pd.DataFrame({
        'timestamp': timestamps,
        'x': np.linspace(0, 40, 50) + np.random.normal(0, 0.1, 50),  # Movimiento con ruido
        'y': np.ones(50) * 10 + np.random.normal(0, 0.05, 50),  # Y constante con ruido
        'tag_id': [1] * 50
    })
    
    # Agregar algunos NaNs para probar filtrado
    df.loc[10:12, 'x'] = np.nan
    df.loc[10:12, 'y'] = np.nan
    
    return df

@pytest.fixture
def temp_csv_file(test_data):
    """Fixture para crear archivo CSV temporal"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        test_data.to_csv(f.name, index=False)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)

@pytest.mark.unit
def test_kalman_filter_handles_nans(test_data):
    """Test: Filtrado Kalman maneja NaNs correctamente"""
    logger.info("Test Kalman: Verificando manejo de NaNs")
    
    kalman = KalmanPositionFilter(initial_pos=[0, 0])
    
    # Procesar datos con NaNs
    filtered_positions = []
    for _, row in test_data.iterrows():
        pos = [row['x'], row['y']]
        filtered_pos = kalman.process(pos, dt=0.02)
        filtered_positions.append(filtered_pos)
    
    # Verificar que no hay NaNs en salida
    filtered_array = np.array(filtered_positions)
    nan_count = np.isnan(filtered_array).sum()
    
    nans_input = test_data[['x', 'y']].isna().sum().sum()
    logger.info(f"NaNs entrada: {nans_input}, NaNs salida: {nan_count}")
    
    assert nan_count == 0, "El filtro Kalman no debe generar NaNs"
    assert nans_input > 0, "Debería haber NaNs en los datos de entrada para probar el filtro"

@pytest.mark.integration
def test_interpolation_creates_more_points(temp_csv_file):
    """Test: La interpolación inteligente crea más puntos sin NaNs"""
    logger.info("Test Interpolación: Verificando creación de puntos sin NaNs")
    
    # Crear sistema con optimización para acelerar test
    system = FutsalReplaySystem(temp_csv_file, optimize_memory=True, skip_trail=True, verbose_debug=False)
    
    # Verificar que no hay NaNs en resultado final
    assert system.df is not None, "sistema.df no debe ser None"
    
    nan_count = system.df[['x', 'y']].isna().sum().sum()
    total_points = len(system.df)
    
    logger.info(f"Puntos interpolados: {total_points}, NaNs: {nan_count}")
    
    assert nan_count == 0, "La interpolación no debe crear NaNs"
    assert total_points >= 50, "Debe haber al menos los puntos originales"

@pytest.mark.unit
def test_generate_report_works(temp_csv_file, capfd):
    """Test: generate_movement_report funciona sin errores y produce output"""
    logger.info("Test Reporte: Verificando generación sin errores")
    
    # Ejecutar reporte y capturar output
    try:
        generate_movement_report(temp_csv_file)
        captured = capfd.readouterr()
        
        # Verificar que se generó output
        assert len(captured.out) > 0, "El reporte debe generar output en stdout"
        assert "REPORTE DE ANÁLISIS" in captured.out, "Debe contener título del reporte"
        assert "Distancia recorrida" in captured.out, "Debe calcular distancia"
        
        logger.info("Reporte generado exitosamente")
        
    except Exception as e:
        pytest.fail(f"Error en generate_movement_report: {e}")

@pytest.mark.integration
def test_memory_optimization_flags(temp_csv_file):
    """Test: Los flags de optimización de memoria funcionan correctamente"""
    logger.info("Test Optimización: Verificando flags de memoria")
    
    # Test con optimización activada
    system1 = FutsalReplaySystem(temp_csv_file, optimize_memory=True, skip_trail=True, verbose_debug=False)
    
    # Test sin optimización 
    system2 = FutsalReplaySystem(temp_csv_file, optimize_memory=False, skip_trail=False, verbose_debug=False)
    
    # Verificar que las configuraciones se aplicaron
    assert system1.optimize_memory == True, "optimize_memory debe estar activado"
    assert system1.skip_trail == True, "skip_trail debe estar activado"
    assert system2.optimize_memory == False, "optimize_memory debe estar desactivado"
    assert system2.skip_trail == False, "skip_trail debe estar desactivado"
    
    # Verificar lógica de trail_length según el código actual
    # optimize_memory=True -> trail_length=50, luego skip_trail=True -> min(50,20)=20
    assert system1.trail_length == 20, "trail_length debe ser 20 con skip_trail=True"
    assert system2.trail_length == 100, "trail_length debe ser 100 sin optimización"
    
    logger.info(f"Sistema optimizado: trail_length={system1.trail_length}")
    logger.info(f"Sistema normal: trail_length={system2.trail_length}")

@pytest.mark.unit
def test_trajectory_predictor_basic():
    """Test: TrajectoryPredictor funciona con datos básicos"""
    logger.info("Test Predictor: Verificando entrenamiento y predicción básica")
    
    predictor = TrajectoryPredictor("futsal")
    
    # Crear datos sintéticos para entrenamiento
    timestamps = np.array([0, 20, 40, 60, 80, 100])  # 6 puntos
    positions = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [5, 0]])  # Línea recta
    
    # Entrenar predictor
    trained = predictor.train(timestamps, positions)
    assert trained == True, "El predictor debe entrenar exitosamente con 6 puntos"
    
    # Hacer predicción
    predictions = predictor.predict([120, 140], max_speed=7.0)
    assert predictions is not None, "Las predicciones no deben ser None"
    assert len(predictions) == 2, "Debe retornar 2 predicciones"
    
    logger.info(f"Entrenamiento: {trained}, Predicciones: {len(predictions)}")

@pytest.mark.unit
def test_trajectory_predictor_speed_limit():
    """Test: TrajectoryPredictor respeta límites de velocidad"""
    logger.info("Test Predictor: Verificando límites de velocidad")
    
    predictor = TrajectoryPredictor("futsal")
    
    # Crear datos que implicarían alta velocidad
    timestamps = np.array([0, 100, 200, 300, 400, 500])  # 100ms entre puntos
    # Posiciones que implicarían 50 m/s sin límite (500m en 10s)
    positions = np.array([[0, 0], [5, 0], [10, 0], [15, 0], [20, 0], [25, 0]])
    
    trained = predictor.train(timestamps, positions)
    assert trained == True, "Debe entrenar con datos de alta velocidad"
    
    # Predecir con límite de velocidad estricto
    max_speed = 7.0  # m/s (límite fútbol sala)
    predictions = predictor.predict([600, 700], max_speed=max_speed)
    
    assert predictions is not None, "Debe generar predicciones"
    assert len(predictions) == 2, "Debe retornar 2 predicciones"
    
    # Verificar que la velocidad está limitada
    if len(predictions) >= 2:
        dx = predictions[1][0] - predictions[0][0]
        dy = predictions[1][1] - predictions[0][1]
        distance = np.sqrt(dx*dx + dy*dy)
        dt = 0.1  # 100ms entre predicciones
        implied_speed = distance / dt
        
        assert implied_speed <= max_speed * 1.1, f"Velocidad {implied_speed:.1f} excede límite {max_speed}"
        logger.info(f"Velocidad predicha: {implied_speed:.2f} m/s (límite: {max_speed} m/s)")

@pytest.mark.integration
@pytest.mark.parametrize("optimize,skip_trail,expected_trail", [
    (True, True, 20),      # optimize_memory=True -> 50, luego skip_trail=True -> min(50,20)=20
    (True, False, 50),     # optimize_memory=True -> 50, skip_trail=False -> 50
    (False, False, 100),   # Sin optimización -> 100
])
def test_trail_length_combinations(temp_csv_file, optimize, skip_trail, expected_trail):
    """Test parametrizado: Diferentes combinaciones de optimización"""
    logger.info(f"Test Parametrizado: optimize={optimize}, skip_trail={skip_trail}")
    
    system = FutsalReplaySystem(temp_csv_file, optimize_memory=optimize, skip_trail=skip_trail, verbose_debug=False)
    
    assert system.trail_length == expected_trail, \
        f"trail_length esperado {expected_trail}, obtenido {system.trail_length}"

@pytest.mark.integration
def test_system_initialization_minimal():
    """Test: Sistema se inicializa correctamente con datos mínimos"""
    logger.info("Test Inicialización: Verificando datos mínimos")
    
    # Crear dataset mínimo válido
    min_data = pd.DataFrame({
        'timestamp': [datetime(2024, 1, 1) + timedelta(seconds=i) for i in range(3)],
        'x': [0.0, 1.0, 2.0],
        'y': [0.0, 0.0, 0.0],
        'tag_id': [1, 1, 1]
    })
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        min_data.to_csv(f.name, index=False)
        temp_file = f.name
    
    try:
        # Sistema debe manejar datos mínimos sin fallar
        system = FutsalReplaySystem(temp_file, optimize_memory=True, verbose_debug=False)
        
        assert system.df is not None, "Debe procesar datos mínimos"
        assert len(system.df) >= 3, "Debe mantener al menos los datos originales"
        assert system.total_frames > 0, "Debe tener frames para reproducir"
        
        logger.info(f"Sistema inicializado con {system.total_frames} frames")
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)

@pytest.mark.unit
def test_system_error_missing_columns():
    """Test: Sistema maneja correctamente archivos con columnas faltantes"""
    logger.info("Test Error: Verificando manejo de columnas faltantes")
    
    # Crear dataset con columnas faltantes
    invalid_data = pd.DataFrame({
        'timestamp': [datetime(2024, 1, 1) + timedelta(seconds=i) for i in range(3)],
        'x': [0.0, 1.0, 2.0],
        # 'y' faltante - esto debe causar error
        'tag_id': [1, 1, 1]
    })
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        invalid_data.to_csv(f.name, index=False)
        temp_file = f.name
    
    try:
        # Sistema debe fallar con SystemExit debido a columnas faltantes
        with pytest.raises(SystemExit):
            FutsalReplaySystem(temp_file, optimize_memory=True, verbose_debug=False)
        
        logger.info("Sistema correctamente rechazó archivo con columnas faltantes")
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)

@pytest.mark.unit
def test_memory_optimization_dtypes():
    """Test: Optimización de memoria mantiene tipos float32/int32"""
    logger.info("Test Memoria: Verificando tipos de datos optimizados")
    
    # Crear datos test
    test_data = pd.DataFrame({
        'timestamp': [datetime(2024, 1, 1) + timedelta(milliseconds=i*50) for i in range(10)],
        'x': [float(i) for i in range(10)],
        'y': [float(i) for i in range(10)],
        'tag_id': [1] * 10
    })
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        test_data.to_csv(f.name, index=False)
        temp_file = f.name
    
    try:
        # Sistema con optimización activada
        system = FutsalReplaySystem(temp_file, optimize_memory=True, verbose_debug=False)
        
        # Verificar que los tipos se mantienen optimizados
        assert system.df['x'].dtype == 'float32', f"x debe ser float32, es {system.df['x'].dtype}"
        assert system.df['y'].dtype == 'float32', f"y debe ser float32, es {system.df['y'].dtype}" 
        assert system.df['tag_id'].dtype == 'int32', f"tag_id debe ser int32, es {system.df['tag_id'].dtype}"
        
        if 'step_dist' in system.df.columns:
            assert system.df['step_dist'].dtype == 'float32', f"step_dist debe ser float32, es {system.df['step_dist'].dtype}"
        if 'cum_dist' in system.df.columns:
            assert system.df['cum_dist'].dtype == 'float32', f"cum_dist debe ser float32, es {system.df['cum_dist'].dtype}"
        
        logger.info(f"Tipos optimizados: x={system.df['x'].dtype}, y={system.df['y'].dtype}, tag_id={system.df['tag_id'].dtype}")
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == "__main__":
    print("="*60)
    print("TESTS DEL SISTEMA UWB CON PYTEST")
    print("="*60)
    print("Para ejecutar los tests usa:")
    print("  python -m pytest test_uwb_system.py -v")
    print("  python -m pytest test_uwb_system.py::test_kalman_filter_handles_nans -v")
    print("="*60) 