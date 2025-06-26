#!/usr/bin/env python3
"""
TFG UWB - Procesador de Trayectorias 3D
=====================================

Procesa datos CSV de UWB para generar trayectorias 3D exportables a Unity.
Estima altura del jugador basada en velocidad y patrones de movimiento.

Autor: TFG UWB Analytics System
Versión: 1.0
"""

import pandas as pd
import numpy as np
import json
import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
import argparse

class Trajectory3DProcessor:
    def __init__(self, field_type='futsal'):
        """
        Inicializar el procesador de trayectorias 3D
        
        Args:
            field_type (str): 'futsal' o 'indoor'
        """
        self.field_type = field_type
        
        # Configuraciones según tipo de campo
        if field_type == 'futsal':
            self.field_length = 40.0  # metros
            self.field_width = 20.0   # metros
            self.anchor_positions = {
                10: (-2.0, -1.0, 2.5),
                20: (-2.0, 21.0, 2.5), 
                30: (42.0, -1.0, 2.5),
                40: (42.0, 21.0, 2.5),
                50: (20.0, -1.0, 2.5)
            }
        else:  # indoor
            self.field_length = 8.0
            self.field_width = 6.0
            self.anchor_positions = {
                10: (-0.5, -0.5, 2.0),
                20: (-0.5, 6.5, 2.0),
                30: (8.5, -0.5, 2.0), 
                40: (8.5, 6.5, 2.0),
                50: (4.0, -0.5, 2.0)
            }
            
        # Configuración de altura del jugador
        self.base_height = 1.0  # Altura base del tag (pecho/cintura)
        self.max_jump_height = 0.8  # Altura máxima de salto
        self.crouch_height = -0.3  # Reducción al agacharse
        
        print(f"🏟️ Procesador 3D inicializado para campo: {field_type}")
        print(f"   Dimensiones: {self.field_length}x{self.field_width}m")
        
    def load_csv_data(self, csv_path):
        """Cargar datos CSV de UWB"""
        print(f"📂 Cargando datos desde: {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
            print(f"✅ Datos cargados: {len(df)} puntos")
            print(f"   Columnas: {list(df.columns)}")
            return df
        except Exception as e:
            print(f"❌ Error cargando CSV: {e}")
            return None
            
    def calculate_velocity_acceleration(self, df):
        """Calcular velocidad y aceleración desde posiciones"""
        print("⚡ Calculando velocidades y aceleraciones...")
        
        # Convertir timestamp a datetime si es string
        if df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calcular diferencias de tiempo en segundos
        time_diff = df['timestamp'].diff().dt.total_seconds()
        
        # Calcular velocidades
        df['vx'] = df['x'].diff() / time_diff
        df['vy'] = df['y'].diff() / time_diff
        df['speed'] = np.sqrt(df['vx']**2 + df['vy']**2)
        
        # Calcular aceleraciones
        df['ax'] = df['vx'].diff() / time_diff
        df['ay'] = df['vy'].diff() / time_diff
        df['acceleration'] = np.sqrt(df['ax']**2 + df['ay']**2)
        
        # Limpiar NaN y valores extremos
        df['vx'].fillna(0, inplace=True)
        df['vy'].fillna(0, inplace=True)
        df['speed'].fillna(0, inplace=True)
        df['ax'].fillna(0, inplace=True)
        df['ay'].fillna(0, inplace=True)
        df['acceleration'].fillna(0, inplace=True)
        
        # Filtrar velocidades extremas (> 15 m/s)
        speed_mask = df['speed'] <= 15.0
        df.loc[~speed_mask, ['vx', 'vy', 'speed']] = 0
        
        # Filtrar aceleraciones extremas (> 20 m/s²)
        accel_mask = df['acceleration'] <= 20.0
        df.loc[~accel_mask, ['ax', 'ay', 'acceleration']] = 0
        
        print(f"   Velocidad máxima: {df['speed'].max():.2f} m/s")
        print(f"   Aceleración máxima: {df['acceleration'].max():.2f} m/s²")
        
        return df
        
    def estimate_height(self, df):
        """
        Estimar altura del jugador basada en patrones de movimiento
        """
        print("📏 Estimando altura del jugador...")
        
        heights = []
        
        for i, row in df.iterrows():
            speed = row['speed']
            accel = row['acceleration']
            base_height = self.base_height
            
            # Estimar altura dinámica basada en patrones
            if speed > 8.0 and accel > 3.0:
                # Sprint + salto/aceleración fuerte
                dynamic_height = min(self.max_jump_height, 
                                   speed * 0.05 + accel * 0.08)
                
            elif speed > 5.0 and accel > 2.0:
                # Carrera rápida
                dynamic_height = min(0.4, speed * 0.03 + accel * 0.05)
                
            elif speed < 1.0 and accel > 1.5:
                # Movimiento lento con alta aceleración = agacharse/levantarse
                dynamic_height = self.crouch_height * 0.7
                
            elif speed < 0.5:
                # Parado - oscilación natural
                time_factor = i * 0.1  # Simular tiempo
                dynamic_height = np.sin(time_factor * 0.5) * 0.05
                
            else:
                # Movimiento normal - oscilación al caminar/correr
                time_factor = i * 0.1
                frequency = max(1.0, speed * 0.5)  # Frecuencia basada en velocidad
                amplitude = 0.08 if speed > 2.0 else 0.04
                dynamic_height = np.sin(time_factor * frequency) * amplitude
                
            # Aplicar suavizado temporal
            if i > 0:
                prev_height = heights[-1] - base_height
                dynamic_height = 0.7 * dynamic_height + 0.3 * prev_height
                
            final_height = base_height + dynamic_height
            
            # Asegurar límites físicos
            final_height = max(0.5, min(final_height, base_height + self.max_jump_height))
            heights.append(final_height)
            
        df['z'] = heights
        
        print(f"   Altura mínima: {min(heights):.2f}m")
        print(f"   Altura máxima: {max(heights):.2f}m")
        print(f"   Altura promedio: {np.mean(heights):.2f}m")
        
        return df
        
    def smooth_trajectory(self, df, window_size=5):
        """Suavizar trayectoria para eliminar ruido"""
        print(f"🔧 Suavizando trayectoria (ventana: {window_size})...")
        
        if len(df) > window_size:
            df['x_smooth'] = savgol_filter(df['x'], window_size, 3)
            df['y_smooth'] = savgol_filter(df['y'], window_size, 3)
            df['z_smooth'] = savgol_filter(df['z'], window_size, 3)
        else:
            df['x_smooth'] = df['x']
            df['y_smooth'] = df['y'] 
            df['z_smooth'] = df['z']
            
        return df
        
    def export_for_unity(self, df, output_path):
        """
        Exportar datos en formato compatible con Unity
        """
        print(f"🎮 Exportando para Unity: {output_path}")
        
        # Estructura de datos para Unity
        unity_data = {
            "metadata": {
                "version": "1.0",
                "field_type": self.field_type,
                "field_dimensions": {
                    "length": self.field_length,
                    "width": self.field_width
                },
                "anchor_positions": self.anchor_positions,
                "total_points": len(df),
                "duration_seconds": (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds(),
                "max_speed": float(df['speed'].max()),
                "avg_speed": float(df['speed'].mean()),
                "export_timestamp": datetime.now().isoformat()
            },
            "trajectory": []
        }
        
        # Convertir datos punto por punto
        for i, row in df.iterrows():
            point = {
                "timestamp": row['timestamp'].isoformat(),
                "time_offset": (row['timestamp'] - df['timestamp'].iloc[0]).total_seconds(),
                "position": {
                    "x": float(row['x_smooth']),
                    "y": float(row['z_smooth']),  # Unity usa Y como altura
                    "z": float(row['y_smooth'])   # Unity usa Z como profundidad
                },
                "velocity": {
                    "x": float(row['vx']),
                    "y": 0.0,  # Velocidad vertical estimada
                    "z": float(row['vy'])
                },
                "speed": float(row['speed']),
                "acceleration": float(row['acceleration']),
                "raw_position": {
                    "x": float(row['x']),
                    "y": float(row['z']),
                    "z": float(row['y'])
                }
            }
            unity_data["trajectory"].append(point)
            
        # Guardar JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unity_data, f, indent=2, ensure_ascii=False)
            
        print(f"✅ Archivo Unity guardado: {output_path}")
        print(f"   Puntos exportados: {len(unity_data['trajectory'])}")
        
        return unity_data
        
    def export_csv_3d(self, df, output_path):
        """Exportar CSV con datos 3D procesados"""
        print(f"📊 Exportando CSV 3D: {output_path}")
        
        # Seleccionar columnas relevantes
        export_df = df[[
            'timestamp', 'tag_id', 
            'x', 'y', 'z',
            'x_smooth', 'y_smooth', 'z_smooth',
            'vx', 'vy', 'speed',
            'ax', 'ay', 'acceleration'
        ]].copy()
        
        # Redondear valores
        numeric_cols = ['x', 'y', 'z', 'x_smooth', 'y_smooth', 'z_smooth',
                       'vx', 'vy', 'speed', 'ax', 'ay', 'acceleration']
        export_df[numeric_cols] = export_df[numeric_cols].round(3)
        
        export_df.to_csv(output_path, index=False)
        print(f"✅ CSV 3D guardado: {output_path}")
        
    def create_3d_visualization(self, df, output_path):
        """Crear visualización 3D de la trayectoria"""
        print(f"📈 Generando visualización 3D: {output_path}")
        
        fig = plt.figure(figsize=(15, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Crear trayectoria coloreada por velocidad
        speeds = df['speed'].values
        scatter = ax.scatter(df['x_smooth'], df['y_smooth'], df['z_smooth'], 
                           c=speeds, cmap='viridis', s=20, alpha=0.7)
        
        # Dibujar campo
        self._draw_field_3d(ax)
        
        # Configurar ejes
        ax.set_xlabel('X (metros)')
        ax.set_ylabel('Y (metros)')
        ax.set_zlabel('Altura (metros)')
        ax.set_title(f'Trayectoria 3D del Jugador - Campo {self.field_type.title()}')
        
        # Colorbar para velocidad
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.5)
        cbar.set_label('Velocidad (m/s)')
        
        # Ajustar límites
        ax.set_xlim(-2, self.field_length + 2)
        ax.set_ylim(-2, self.field_width + 2)
        ax.set_zlim(0, self.base_height + self.max_jump_height + 0.5)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Visualización guardada: {output_path}")
        
    def _draw_field_3d(self, ax):
        """Dibujar campo y anclas en 3D"""
        # Dibujar perímetro del campo
        corners = np.array([
            [0, 0, 0], [self.field_length, 0, 0],
            [self.field_length, self.field_width, 0], [0, self.field_width, 0],
            [0, 0, 0]
        ])
        ax.plot(corners[:, 0], corners[:, 1], corners[:, 2], 'k-', linewidth=2)
        
        # Dibujar anclas
        for anchor_id, (x, y, z) in self.anchor_positions.items():
            ax.scatter([x], [y], [z], c='red', s=100, marker='^')
            ax.text(x, y, z + 0.3, f'A{anchor_id}', fontsize=8)
            
    def process_file(self, input_csv, output_dir=None):
        """Procesar un archivo CSV completo"""
        if output_dir is None:
            output_dir = "outputs/trajectory_3d"
            
        os.makedirs(output_dir, exist_ok=True)
        
        # Generar nombres de archivo
        base_name = os.path.splitext(os.path.basename(input_csv))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        unity_output = os.path.join(output_dir, f"{base_name}_unity_{timestamp}.json")
        csv_output = os.path.join(output_dir, f"{base_name}_3d_{timestamp}.csv")
        viz_output = os.path.join(output_dir, f"{base_name}_visualization_{timestamp}.png")
        
        print(f"\n🚀 Procesando archivo: {input_csv}")
        print(f"📁 Directorio de salida: {output_dir}")
        
        # Cargar y procesar datos
        df = self.load_csv_data(input_csv)
        if df is None:
            return False
            
        # Pipeline de procesamiento
        df = self.calculate_velocity_acceleration(df)
        df = self.estimate_height(df)
        df = self.smooth_trajectory(df)
        
        # Exportar resultados
        unity_data = self.export_for_unity(df, unity_output)
        self.export_csv_3d(df, csv_output)
        self.create_3d_visualization(df, viz_output)
        
        # Resumen final
        print(f"\n📋 RESUMEN DE PROCESAMIENTO")
        print(f"   📊 Puntos procesados: {len(df)}")
        print(f"   ⏱️ Duración: {unity_data['metadata']['duration_seconds']:.1f}s")
        print(f"   🏃 Velocidad máxima: {unity_data['metadata']['max_speed']:.1f} m/s")
        print(f"   📈 Velocidad promedio: {unity_data['metadata']['avg_speed']:.1f} m/s")
        print(f"   📁 Archivos generados:")
        print(f"      🎮 Unity JSON: {unity_output}")
        print(f"      📊 CSV 3D: {csv_output}")
        print(f"      📈 Visualización: {viz_output}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Procesador de Trayectorias 3D para TFG UWB')
    parser.add_argument('input_csv', help='Archivo CSV de entrada')
    parser.add_argument('--field-type', choices=['futsal', 'indoor'], default='futsal', 
                       help='Tipo de campo (futsal o indoor)')
    parser.add_argument('--output-dir', help='Directorio de salida (opcional)')
    
    args = parser.parse_args()
    
    print("🎯 TFG UWB - Procesador de Trayectorias 3D")
    print("=" * 50)
    
    # Crear procesador
    processor = Trajectory3DProcessor(field_type=args.field_type)
    
    # Procesar archivo
    success = processor.process_file(args.input_csv, args.output_dir)
    
    if success:
        print("\n✅ Procesamiento completado exitosamente!")
        print("\n💡 Para Unity:")
        print("   1. Importa el archivo JSON generado")
        print("   2. Usa las coordenadas 'position' para animar el jugador")
        print("   3. La velocidad está en 'speed' para efectos visuales")
        print("   4. Las posiciones de anclas están en 'metadata.anchor_positions'")
    else:
        print("\n❌ Error en el procesamiento")

if __name__ == "__main__":
    main() 