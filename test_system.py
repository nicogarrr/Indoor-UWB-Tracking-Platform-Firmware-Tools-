#!/usr/bin/env python3
"""
Script de Prueba del Sistema UWB - TFG Fútbol Sala
==================================================

Prueba rápida de todos los componentes del sistema.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
from csv_processor import UWBDataProcessor
import sys

def test_system():
    """Prueba completa del sistema UWB"""
    print("🧪 PRUEBA DEL SISTEMA UWB - TFG FÚTBOL SALA")
    print("=" * 55)
    
    # 1. Verificar estructura de directorios
    print("\n1️⃣ Verificando estructura de directorios...")
    required_dirs = ['data', 'processed_data', 'plots']
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"   ✅ {dir_name}/ - OK")
        else:
            print(f"   ❌ {dir_name}/ - FALTA")
            os.makedirs(dir_name, exist_ok=True)
            print(f"   🔧 {dir_name}/ - CREADO")
    
    # 2. Verificar dependencias
    print("\n2️⃣ Verificando dependencias Python...")
    try:
        import pandas, numpy, scipy, matplotlib, seaborn
        print("   ✅ Todas las dependencias disponibles")
    except ImportError as e:
        print(f"   ❌ Dependencia faltante: {e}")
        return False
    
    # 3. Verificar datos de ejemplo
    print("\n3️⃣ Verificando datos de ejemplo...")
    example_file = "data/uwb_data_example_20250621_150000.csv"
    if os.path.exists(example_file):
        try:
            df = pd.read_csv(example_file)
            print(f"   ✅ Archivo ejemplo: {len(df)} registros")
        except Exception as e:
            print(f"   ❌ Error leyendo ejemplo: {e}")
            return False
    else:
        print("   ❌ Archivo de ejemplo no encontrado")
        return False
    
    # 4. Probar procesador de datos
    print("\n4️⃣ Probando procesador de datos...")
    try:
        processor = UWBDataProcessor(data_dir="data")
        csv_files = processor.find_csv_files()
        if csv_files:
            print(f"   ✅ Encontrados {len(csv_files)} archivos CSV")
            
            # Procesar archivo de ejemplo
            df_processed = processor.process_single_file(csv_files[0])
            if df_processed is not None:
                print(f"   ✅ Procesamiento exitoso: {len(df_processed)} puntos")
            else:
                print("   ❌ Error en procesamiento")
                return False
        else:
            print("   ❌ No se encontraron archivos CSV")
            return False
    except Exception as e:
        print(f"   ❌ Error en procesador: {e}")
        return False
    
    # 5. Generar visualización simple
    print("\n5️⃣ Generando visualización de prueba...")
    try:
        plt.figure(figsize=(12, 8))
        
        # Subplot 1: Trayectoria
        plt.subplot(2, 2, 1)
        plt.plot(df_processed['x'], df_processed['y'], 'b-o', markersize=3)
        plt.xlim(-2, 42)
        plt.ylim(-2, 22)
        plt.grid(True, alpha=0.3)
        plt.title('Trayectoria del Tag')
        plt.xlabel('X (metros)')
        plt.ylabel('Y (metros)')
        
        # Dibujar cancha
        plt.plot([0, 40, 40, 0, 0], [0, 0, 20, 20, 0], 'k-', linewidth=2)
        plt.plot([20, 20], [0, 20], 'k--', alpha=0.5)
        
        # Subplot 2: Posición vs Tiempo
        plt.subplot(2, 2, 2)
        plt.plot(range(len(df_processed)), df_processed['x'], label='X', alpha=0.8)
        plt.plot(range(len(df_processed)), df_processed['y'], label='Y', alpha=0.8)
        plt.title('Posición vs Tiempo')
        plt.xlabel('Frame')
        plt.ylabel('Posición (metros)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Subplot 3: Velocidad
        if 'velocity' in df_processed.columns:
            plt.subplot(2, 2, 3)
            plt.plot(range(len(df_processed)), df_processed['velocity'], 'g-', alpha=0.8)
            plt.title('Velocidad')
            plt.xlabel('Frame')
            plt.ylabel('Velocidad (m/s)')
            plt.grid(True, alpha=0.3)
        
        # Subplot 4: Estadísticas
        plt.subplot(2, 2, 4)
        stats_text = f"""ESTADÍSTICAS DE PRUEBA
        
Duración: {len(df_processed)} frames
Rango X: {df_processed['x'].min():.1f} - {df_processed['x'].max():.1f}m  
Rango Y: {df_processed['y'].min():.1f} - {df_processed['y'].max():.1f}m
Centro: ({df_processed['x'].mean():.1f}, {df_processed['y'].mean():.1f})

✅ Sistema UWB Funcionando"""
        
        plt.text(0.1, 0.5, stats_text, fontsize=10, verticalalignment='center',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.8))
        plt.xlim(0, 1)
        plt.ylim(0, 1)
        plt.axis('off')
        
        plt.tight_layout()
        
        # Guardar gráfico
        output_file = "plots/sistema_test.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"   ✅ Visualización guardada: {output_file}")
        
        # Mostrar gráfico
        plt.show()
        
    except Exception as e:
        print(f"   ❌ Error en visualización: {e}")
        return False
    
    # 6. Resumen final
    print("\n🎉 PRUEBA COMPLETADA")
    print("=" * 55)
    print("✅ Todos los componentes funcionando correctamente")
    print("📊 Archivos generados:")
    print("   - processed_data/uwb_data_example_20250621_150000_processed.csv")
    print("   - plots/sistema_test.png")
    print("\n🚀 ¡Tu sistema UWB está listo para usar!")
    
    return True

def show_next_steps():
    """Muestra los siguientes pasos para el usuario"""
    print("\n📋 SIGUIENTES PASOS:")
    print("=" * 40)
    print("1️⃣ HARDWARE:")
    print("   - Programar ESP32s con Arduino IDE")
    print("   - Configurar WiFi en common/secrets.h")
    print("   - Colocar anclas en posiciones optimizadas")
    print()
    print("2️⃣ CAPTURA REAL:")
    print("   - python mqtt_to_csv_collector.py")
    print("   - Realizar pruebas con el tag")
    print()
    print("3️⃣ ANÁLISIS:")
    print("   - python csv_processor.py")
    print("   - python movement_replay.py --data-dir processed_data")
    print()
    print("📖 Consulta GUIA_RAPIDA.md para más detalles")

if __name__ == "__main__":
    success = test_system()
    
    if success:
        show_next_steps()
    else:
        print("\n❌ La prueba falló. Verifica:")
        print("   1. pip install -r requirements.txt")
        print("   2. Archivos de ejemplo en data/")
        print("   3. Permisos de escritura en directorios")
        sys.exit(1) 