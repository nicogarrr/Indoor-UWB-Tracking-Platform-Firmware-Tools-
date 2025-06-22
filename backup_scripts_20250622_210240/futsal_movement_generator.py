#!/usr/bin/env python3
"""
Generador de Movimientos Realistas de Fútbol Sala
Simula datos UWB de jugadas reales con ruido y comportamientos táticos
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import math
import random

class FutsalMovementGenerator:
    """Generador de movimientos realistas para fútbol sala"""
    
    def __init__(self):
        # Dimensiones de la cancha (40x20m)
        self.court_width = 40
        self.court_height = 20
        
        # Parámetros de simulación
        self.fps = 25  # 25 Hz como los datos reales
        self.duration_seconds = 60  # 1 minuto
        self.total_frames = self.duration_seconds * self.fps
        
        # Configuración del jugador
        self.player_id = "J07"  # Jugador número 7
        
        # Velocidades realistas (m/s)
        self.walking_speed = 1.5
        self.jogging_speed = 3.0
        self.running_speed = 5.5
        self.sprint_speed = 8.0
        
        # Parámetros de ruido UWB (realista)
        self.position_noise_std = 0.15  # 15cm de error estándar
        self.occasional_outlier_prob = 0.02  # 2% probabilidad de outlier
        self.signal_loss_prob = 0.001  # 0.1% probabilidad de pérdida de señal
        
    def generate_realistic_futsal_movements(self, scenario="defensive_press"):
        """Generar movimientos realistas según el escenario táctico"""
        
        print(f"🏟️ Generando movimientos de fútbol sala: {scenario}")
        print(f"⏱️ Duración: {self.duration_seconds} segundos")
        print(f"📊 Frecuencia: {self.fps} Hz ({self.total_frames} frames)")
        
        if scenario == "defensive_press":
            return self._generate_defensive_press_sequence()
        elif scenario == "counter_attack":
            return self._generate_counter_attack_sequence()
        elif scenario == "possession_play":
            return self._generate_possession_play_sequence()
        else:
            return self._generate_mixed_game_sequence()
    
    def _generate_defensive_press_sequence(self):
        """Secuencia realista de cierre defensivo"""
        movements = []
        timestamps = []
        
        # Tiempo inicial
        start_time = datetime.now()
        
        # === FASE 1: POSICIÓN INICIAL (0-5s) ===
        print("🛡️ Fase 1: Posición defensiva inicial...")
        x, y = 15, 10  # Centro-izquierda defensivo
        
        for frame in range(0, 5 * self.fps):
            # Movimiento sutil en posición
            x += random.uniform(-0.3, 0.3)
            y += random.uniform(-0.2, 0.2)
            
            # Mantener en zona
            x = max(12, min(18, x))
            y = max(7, min(13, y))
            
            timestamp = start_time + timedelta(seconds=frame / self.fps)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        # === FASE 2: PRESIÓN INICIAL (5-15s) ===
        print("⚡ Fase 2: Inicio de presión al portador...")
        target_x, target_y = 25, 12  # Avanzar hacia el portador
        
        for frame in range(5 * self.fps, 15 * self.fps):
            # Movimiento progresivo hacia el objetivo
            progress = (frame - 5 * self.fps) / (10 * self.fps)
            speed = self.jogging_speed * (1 + 0.3 * math.sin(progress * math.pi))
            
            # Movimiento hacia objetivo con variaciones tácticas
            dx = (target_x - x) * 0.08
            dy = (target_y - y) * 0.05
            
            x += dx + random.uniform(-0.2, 0.2)
            y += dy + random.uniform(-0.3, 0.3)
            
            timestamp = start_time + timedelta(seconds=frame / self.fps)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        # === FASE 3: CIERRE INTENSO (15-35s) ===
        print("🔥 Fase 3: Cierre defensivo intenso...")
        
        for frame in range(15 * self.fps, 35 * self.fps):
            # Movimientos erráticos de presión
            phase = (frame - 15 * self.fps) / self.fps
            
            # Sprint cortos y cambios de dirección
            if phase % 3 < 1:  # Sprint cada 3 segundos
                speed = self.sprint_speed
                # Movimiento agresivo hacia la pelota
                ball_x = 28 + 3 * math.sin(phase * 0.5)
                ball_y = 10 + 2 * math.cos(phase * 0.7)
                
                dx = (ball_x - x) * 0.15
                dy = (ball_y - y) * 0.12
            else:
                speed = self.running_speed
                # Movimiento de cobertura
                dx = random.uniform(-0.4, 0.4)
                dy = random.uniform(-0.3, 0.3)
            
            x += dx
            y += dy
            
            # Mantener en zona de juego
            x = max(5, min(35, x))
            y = max(2, min(18, y))
            
            timestamp = start_time + timedelta(seconds=frame / self.fps)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        # === FASE 4: RECUPERACIÓN (35-45s) ===
        print("🏃 Fase 4: Recuperación tras recuperar el balón...")
        
        # Movimiento hacia adelante después de recuperar
        for frame in range(35 * self.fps, 45 * self.fps):
            # Avance rápido hacia campo contrario
            progress = (frame - 35 * self.fps) / (10 * self.fps)
            
            # Sprint hacia adelante
            x += self.running_speed * 0.04 * (1 + 0.5 * progress)
            y += random.uniform(-0.2, 0.2)
            
            # Mantener en cancha
            x = min(38, x)
            y = max(3, min(17, y))
            
            timestamp = start_time + timedelta(seconds=frame / self.fps)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        # === FASE 5: FINALIZACIÓN (45-60s) ===
        print("⚽ Fase 5: Movimientos de finalización...")
        
        for frame in range(45 * self.fps, self.total_frames):
            # Movimientos en área rival
            phase = (frame - 45 * self.fps) / self.fps
            
            # Simulación de jugada de finalización
            if phase < 5:  # Movimiento lateral
                y += 0.3 * math.sin(phase * 2)
                x += random.uniform(-0.1, 0.2)
            elif phase < 10:  # Aceleración hacia portería
                x += 0.2
                y += (10 - y) * 0.08
            else:  # Zona de definición
                x += random.uniform(-0.3, 0.1)
                y += random.uniform(-0.4, 0.4)
            
            # Mantener en zona ofensiva
            x = max(25, min(39, x))
            y = max(4, min(16, y))
            
            timestamp = start_time + timedelta(seconds=frame / self.fps)
            movements.append((x, y))
            timestamps.append(timestamp)
        
        return self._apply_uwb_noise(movements, timestamps)
    
    def _apply_uwb_noise(self, movements, timestamps):
        """Aplicar ruido realista de sistema UWB"""
        print("📡 Aplicando ruido realista del sistema UWB...")
        
        noisy_data = []
        
        for i, ((x, y), timestamp) in enumerate(zip(movements, timestamps)):
            # Ruido gaussiano normal
            noise_x = np.random.normal(0, self.position_noise_std)
            noise_y = np.random.normal(0, self.position_noise_std)
            
            noisy_x = x + noise_x
            noisy_y = y + noise_y
            
            # Outliers ocasionales (multipath, reflexiones)
            if random.random() < self.occasional_outlier_prob:
                outlier_factor = random.uniform(2, 5)
                noisy_x += random.uniform(-outlier_factor, outlier_factor)
                noisy_y += random.uniform(-outlier_factor, outlier_factor)
                print(f"📍 Outlier generado en frame {i}: ({noisy_x:.2f}, {noisy_y:.2f})")
            
            # Pérdida de señal ocasional
            if random.random() < self.signal_loss_prob:
                noisy_x = np.nan
                noisy_y = np.nan
                print(f"📵 Pérdida de señal en frame {i}")
            
            noisy_data.append({
                'timestamp': timestamp,
                'player_id': self.player_id,
                'x': noisy_x,
                'y': noisy_y,
                'frame': i
            })
        
        return noisy_data
    
    def save_to_csv(self, data, filename=None):
        """Guardar datos en formato CSV compatible con el sistema"""
        if filename is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/futsal_defensive_press_{timestamp_str}.csv"
        
        df = pd.DataFrame(data)
        
        # Asegurar formato correcto
        df = df[['timestamp', 'player_id', 'x', 'y', 'frame']]
        
        # Guardar CSV
        df.to_csv(filename, index=False)
        
        # Estadísticas
        valid_positions = df.dropna(subset=['x', 'y'])
        total_frames = len(df)
        valid_frames = len(valid_positions)
        outliers = len(df[(abs(df['x'] - df['x'].median()) > 3) | 
                         (abs(df['y'] - df['y'].median()) > 3)])
        
        print(f"\n✅ Archivo generado: {filename}")
        print(f"📊 Total de frames: {total_frames}")
        print(f"✅ Frames válidos: {valid_frames} ({valid_frames/total_frames*100:.1f}%)")
        print(f"⚠️ Outliers: {outliers} ({outliers/total_frames*100:.1f}%)")
        print(f"📏 Rango X: {valid_positions['x'].min():.1f} - {valid_positions['x'].max():.1f}m")
        print(f"📏 Rango Y: {valid_positions['y'].min():.1f} - {valid_positions['y'].max():.1f}m")
        
        return filename
    
    def plot_trajectory_preview(self, data, filename=None):
        """Crear vista previa de la trayectoria generada"""
        df = pd.DataFrame(data)
        
        plt.figure(figsize=(16, 10))
        
        # Dibujar cancha básica
        plt.xlim(-2, 42)
        plt.ylim(-2, 22)
        
        # Cancha
        court = plt.Rectangle((0, 0), 40, 20, linewidth=2, 
                            edgecolor='white', facecolor='#8B7355', alpha=0.8)
        plt.gca().add_patch(court)
        
        # Líneas principales
        plt.plot([20, 20], [0, 20], 'white', linewidth=2)  # Línea central
        
        # Porterías
        plt.plot([0, 0], [8.5, 11.5], 'white', linewidth=4)
        plt.plot([40, 40], [8.5, 11.5], 'white', linewidth=4)
        
        # Áreas
        from matplotlib.patches import Wedge
        penalty_left = Wedge((0, 10), 6, -90, 90, linewidth=2,
                           edgecolor='white', facecolor='none')
        penalty_right = Wedge((40, 10), 6, 90, 270, linewidth=2,
                            edgecolor='white', facecolor='none')
        plt.gca().add_patch(penalty_left)
        plt.gca().add_patch(penalty_right)
        
        # Trayectoria
        valid_data = df.dropna(subset=['x', 'y'])
        
        # Gradiente de color por tiempo
        scatter = plt.scatter(valid_data['x'], valid_data['y'], 
                            c=valid_data.index, cmap='viridis',
                            s=20, alpha=0.7, label='Trayectoria')
        
        # Línea de trayectoria
        plt.plot(valid_data['x'], valid_data['y'], 'orange', 
                linewidth=2, alpha=0.8, label='Recorrido')
        
        # Puntos especiales
        plt.plot(valid_data['x'].iloc[0], valid_data['y'].iloc[0], 
                'go', markersize=12, label='Inicio')
        plt.plot(valid_data['x'].iloc[-1], valid_data['y'].iloc[-1], 
                'ro', markersize=12, label='Final')
        
        plt.colorbar(scatter, label='Tiempo (frames)')
        plt.title('🏟️ Vista Previa - Cierre Defensivo en Fútbol Sala\n'
                 f'📊 {len(df)} frames | ⏱️ {self.duration_seconds}s | 🎯 {self.player_id}',
                 fontsize=14, fontweight='bold')
        plt.xlabel('Posición X (metros)')
        plt.ylabel('Posición Y (metros)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.gca().set_facecolor('#1a1a2e')
        
        if filename:
            plot_filename = filename.replace('.csv', '_preview.png')
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            print(f"📊 Vista previa guardada: {plot_filename}")
        
        plt.show()
        
        return filename

def main():
    """Función principal"""
    print("🏟️ GENERADOR DE MOVIMIENTOS DE FÚTBOL SALA")
    print("=" * 50)
    
    # Crear generador
    generator = FutsalMovementGenerator()
    
    # Generar movimientos de cierre defensivo
    movements_data = generator.generate_realistic_futsal_movements("defensive_press")
    
    # Guardar CSV
    csv_filename = generator.save_to_csv(movements_data)
    
    # Mostrar vista previa
    generator.plot_trajectory_preview(movements_data, csv_filename)
    
    print("\n🎯 SIGUIENTES PASOS:")
    print(f"1️⃣ Procesar datos: python csv_processor.py {csv_filename}")
    print(f"2️⃣ Ver replay: python movement_replay.py processed_data/latest_processed.csv")
    print("=" * 50)
    
    return csv_filename

if __name__ == "__main__":
    main() 