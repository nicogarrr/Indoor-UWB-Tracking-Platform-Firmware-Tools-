#!/usr/bin/env python3
"""
Comparador de Sesiones de Entrenamiento - TFG Fútbol Sala
=========================================================

Sistema para comparar múltiples sesiones de entrenamiento y detectar
mejoras o deterioros en el rendimiento deportivo.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
from datetime import datetime
import argparse

class SessionComparator:
    """Comparador profesional de sesiones de entrenamiento"""
    
    def __init__(self):
        self.sessions = {}
        self.comparison_metrics = [
            'total_distance', 'avg_speed', 'max_speed',
            'sprint_count', 'avg_sprint_speed', 'high_intensity_time'
        ]
    
    def load_session(self, csv_file, session_name=None):
        """Cargar una sesión de entrenamiento"""
        if session_name is None:
            session_name = os.path.basename(csv_file).replace('.csv', '')
        
        df = pd.read_csv(csv_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calcular métricas básicas
        metrics = self._calculate_session_metrics(df)
        
        self.sessions[session_name] = {
            'data': df,
            'metrics': metrics,
            'file': csv_file
        }
        
        print(f"✅ Sesión cargada: {session_name}")
    
    def _calculate_session_metrics(self, df):
        """Calcular métricas para una sesión"""
        # Calcular velocidades
        df['dt'] = df['timestamp'].diff().dt.total_seconds()
        df['dx'] = df['x'].diff()
        df['dy'] = df['y'].diff()
        df['distance'] = np.sqrt(df['dx']**2 + df['dy']**2)
        df['velocity'] = df['distance'] / df['dt']
        
        # Métricas básicas
        total_time = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).total_seconds()
        total_distance = df['distance'].sum()
        avg_speed = df['velocity'].mean()
        max_speed = df['velocity'].max()
        
        # Sprints (>4 m/s)
        sprints = df[df['velocity'] > 4.0]
        sprint_count = len(sprints)
        avg_sprint_speed = sprints['velocity'].mean() if len(sprints) > 0 else 0
        
        # Tiempo de alta intensidad (>3 m/s)
        high_intensity_time = len(df[df['velocity'] > 3.0]) * df['dt'].mean()
        
        return {
            'total_time': total_time,
            'total_distance': total_distance,
            'avg_speed': avg_speed,
            'max_speed': max_speed,
            'sprint_count': sprint_count,
            'avg_sprint_speed': avg_sprint_speed,
            'high_intensity_time': high_intensity_time
        }
    
    def compare_sessions(self):
        """Generar comparación entre todas las sesiones"""
        if len(self.sessions) < 2:
            print("❌ Se necesitan al menos 2 sesiones para comparar")
            return
        
        print("\n🔍 COMPARACIÓN DE SESIONES DE ENTRENAMIENTO")
        print("=" * 60)
        
        # Crear DataFrame de métricas
        metrics_df = pd.DataFrame()
        for session_name, session_data in self.sessions.items():
            metrics_series = pd.Series(session_data['metrics'])
            metrics_df[session_name] = metrics_series
        
        # Mostrar tabla comparativa
        print("\n📊 TABLA COMPARATIVA:")
        print(metrics_df.round(2).to_string())
        
        # Calcular mejoras/deterioros
        print("\n📈 ANÁLISIS DE TENDENCIAS:")
        session_names = list(self.sessions.keys())
        for i in range(1, len(session_names)):
            current = session_names[i]
            previous = session_names[i-1]
            
            print(f"\n🔄 {previous} → {current}:")
            for metric in self.comparison_metrics:
                if metric in metrics_df.index:
                    prev_val = metrics_df[previous][metric]
                    curr_val = metrics_df[current][metric]
                    
                    if prev_val > 0:
                        change_pct = ((curr_val - prev_val) / prev_val) * 100
                        trend = "📈" if change_pct > 0 else "📉"
                        print(f"   {metric}: {prev_val:.2f} → {curr_val:.2f} "
                              f"({trend} {change_pct:+.1f}%)")
        
        return metrics_df
    
    def create_comparison_visualizations(self, output_dir="comparisons"):
        """Crear visualizaciones comparativas"""
        if len(self.sessions) < 2:
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Preparar datos
        metrics_df = pd.DataFrame()
        for session_name, session_data in self.sessions.items():
            metrics_series = pd.Series(session_data['metrics'])
            metrics_df[session_name] = metrics_series
        
        # Crear dashboard comparativo
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle('COMPARACIÓN DE SESIONES DE ENTRENAMIENTO', 
                    fontsize=16, fontweight='bold')
        
        # Gráfico 1: Distancia total
        ax1 = axes[0, 0]
        metrics_df.loc['total_distance'].plot(kind='bar', ax=ax1, color='skyblue')
        ax1.set_title('Distancia Total (m)')
        ax1.set_ylabel('Metros')
        ax1.tick_params(axis='x', rotation=45)
        
        # Gráfico 2: Velocidad promedio
        ax2 = axes[0, 1]
        metrics_df.loc['avg_speed'].plot(kind='bar', ax=ax2, color='orange')
        ax2.set_title('Velocidad Promedio (m/s)')
        ax2.set_ylabel('m/s')
        ax2.tick_params(axis='x', rotation=45)
        
        # Gráfico 3: Velocidad máxima
        ax3 = axes[0, 2]
        metrics_df.loc['max_speed'].plot(kind='bar', ax=ax3, color='red')
        ax3.set_title('Velocidad Máxima (m/s)')
        ax3.set_ylabel('m/s')
        ax3.tick_params(axis='x', rotation=45)
        
        # Gráfico 4: Número de sprints
        ax4 = axes[1, 0]
        if 'sprint_count' in metrics_df.index:
            metrics_df.loc['sprint_count'].plot(kind='bar', ax=ax4, color='green')
        ax4.set_title('Número de Sprints')
        ax4.set_ylabel('Cantidad')
        ax4.tick_params(axis='x', rotation=45)
        
        # Gráfico 5: Tiempo alta intensidad
        ax5 = axes[1, 1]
        if 'high_intensity_time' in metrics_df.index:
            metrics_df.loc['high_intensity_time'].plot(kind='bar', ax=ax5, color='purple')
        ax5.set_title('Tiempo Alta Intensidad (s)')
        ax5.set_ylabel('Segundos')
        ax5.tick_params(axis='x', rotation=45)
        
        # Gráfico 6: Evolución temporal (si hay más de 2 sesiones)
        ax6 = axes[1, 2]
        if len(self.sessions) > 2:
            metrics_df.loc[['avg_speed', 'max_speed']].T.plot(ax=ax6)
            ax6.set_title('Evolución Velocidades')
            ax6.set_ylabel('m/s')
            ax6.legend()
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"session_comparison_{timestamp}.png")
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Comparación guardada: {output_file}")
        
        plt.show()

def load_multiple_sessions(data_dir="processed_data"):
    """Cargar automáticamente múltiples sesiones"""
    comparator = SessionComparator()
    
    # Buscar archivos procesados
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        print(f"❌ No se encontraron archivos en {data_dir}")
        return None
    
    print(f"📁 Encontrados {len(csv_files)} archivos:")
    for file in csv_files:
        print(f"   - {os.path.basename(file)}")
    
    # Cargar todas las sesiones
    for csv_file in csv_files:
        session_name = os.path.basename(csv_file).replace('.csv', '').replace('_processed', '')
        comparator.load_session(csv_file, session_name)
    
    return comparator

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Comparador de Sesiones de Entrenamiento')
    parser.add_argument('--data-dir', default='processed_data',
                       help='Directorio con archivos CSV procesados')
    parser.add_argument('--output-dir', default='comparisons',
                       help='Directorio de salida')
    
    args = parser.parse_args()
    
    print("🔍 COMPARADOR DE SESIONES DE ENTRENAMIENTO")
    print("=" * 45)
    
    # Cargar sesiones automáticamente
    comparator = load_multiple_sessions(args.data_dir)
    
    if comparator is None or len(comparator.sessions) == 0:
        print("❌ No se pudieron cargar sesiones")
        return
    
    # Realizar comparación
    metrics_df = comparator.compare_sessions()
    
    # Crear visualizaciones
    comparator.create_comparison_visualizations(args.output_dir)
    
    print(f"\n✅ Comparación completada. Archivos en: {args.output_dir}")

if __name__ == "__main__":
    main() 