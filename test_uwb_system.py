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
from datetime import datetime, timedelta

# Importar el sistema principal
from movement_replay import KalmanPositionFilter, TrajectoryPredictor, FutsalReplaySystem, generate_movement_report

@pytest.fixture
def test_data():
    """Fixture para crear datos de prueba reutilizables"""
    # Crear dataset de prueba con gaps para forzar interpolación
    timestamps = [datetime.now() + timedelta(milliseconds=i*50) for i in range(50)]  # 50ms gap
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

def test_kalman_filter_handles_nans(test_data):
    """Test: Filtrado Kalman maneja NaNs correctamente"""
    print("\n[TEST 1] Filtrado Kalman con NaNs...")
    
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
    
    print(f"   NaNs en entrada: {test_data[['x', 'y']].isna().sum().sum()}")
    print(f"   NaNs en salida: {nan_count}")
    
    assert nan_count == 0, "El filtro Kalman no debe generar NaNs"
    print("   ✓ Test Kalman con NaNs: PASADO")

def test_interpolation_creates_more_points(temp_csv_file):
    """Test: La interpolación inteligente crea más puntos sin NaNs"""
    print("\n[TEST 2] Interpolación inteligente sin NaNs...")
    
    # Crear sistema con optimización para acelerar test
    system = FutsalReplaySystem(temp_csv_file, optimize_memory=True, skip_trail=True, verbose_debug=False)
    
    # Verificar que no hay NaNs en resultado final
    assert system.df is not None, "sistema.df no debe ser None"
    
    nan_count = system.df[['x', 'y']].isna().sum().sum()
    total_points = len(system.df)
    
    print(f"   Puntos interpolados: {total_points}")
    print(f"   NaNs en resultado: {nan_count}")
    
    assert nan_count == 0, "La interpolación no debe crear NaNs"
    assert total_points >= 50, "Debe haber al menos los puntos originales"
    print("   ✓ Test interpolación sin NaNs: PASADO")

def test_generate_report_works(temp_csv_file):
    """Test: generate_movement_report funciona sin errores"""
    print("\n[TEST 3] Generación de reporte...")
    
    # Ejecutar reporte sin excepción
    try:
        generate_movement_report(temp_csv_file)
        print("   ✓ generate_movement_report ejecutado sin errores")
        print("   ✓ Test generación reporte: PASADO")
    except Exception as e:
        pytest.fail(f"Error en generate_movement_report: {e}")

def test_memory_optimization_flags(temp_csv_file):
    """Test: Los flags de optimización de memoria funcionan correctamente"""
    print("\n[TEST 4] Flags de optimización de memoria...")
    
    # Test con optimización activada
    system1 = FutsalReplaySystem(temp_csv_file, optimize_memory=True, skip_trail=True, verbose_debug=False)
    
    # Test sin optimización 
    system2 = FutsalReplaySystem(temp_csv_file, optimize_memory=False, skip_trail=False, verbose_debug=False)
    
    # Verificar que las configuraciones se aplicaron
    assert system1.optimize_memory == True, "optimize_memory debe estar activado"
    assert system1.skip_trail == True, "skip_trail debe estar activado"
    assert system2.optimize_memory == False, "optimize_memory debe estar desactivado"
    assert system2.skip_trail == False, "skip_trail debe estar desactivado"
    
    # Verificar que trail_length es coherente
    assert system1.trail_length <= 20, "trail_length debe ser ≤20 con skip_trail"
    
    print(f"   Sistema 1 (optimizado): trail_length={system1.trail_length}")
    print(f"   Sistema 2 (normal): trail_length={system2.trail_length}")
    print("   ✓ Test flags optimización: PASADO")

def test_trajectory_predictor_basic():
    """Test: TrajectoryPredictor funciona con datos básicos"""
    print("\n[TEST 5] Predictor de trayectorias...")
    
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
    
    print(f"   Entrenamiento exitoso: {trained}")
    print(f"   Predicciones generadas: {len(predictions)}")
    print("   ✓ Test predictor: PASADO")

@pytest.mark.parametrize("optimize,skip_trail,expected_trail", [
    (True, True, 20),      # Máxima optimización
    (True, False, 50),     # Solo optimize_memory  
    (False, False, 100),   # Sin optimización
])
def test_trail_length_combinations(temp_csv_file, optimize, skip_trail, expected_trail):
    """Test parametrizado: Diferentes combinaciones de optimización"""
    system = FutsalReplaySystem(temp_csv_file, optimize_memory=optimize, skip_trail=skip_trail, verbose_debug=False)
    
    if skip_trail:
        assert system.trail_length <= expected_trail
    else:
        assert system.trail_length == expected_trail

if __name__ == "__main__":
    print("="*60)
    print("🧪 EJECUTANDO TESTS DEL SISTEMA UWB CON PYTEST")
    print("="*60)
    
    # Ejecutar tests con pytest
    pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n" + "="*60)
    print("✅ TESTS COMPLETADOS")
    print("="*60) 