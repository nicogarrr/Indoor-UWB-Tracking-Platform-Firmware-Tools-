#!/usr/bin/env python3
"""
🏟️ Generador de Datos Realistas de Fútbol Sala
Simula comportamientos naturales de un jugador profesional
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import argparse

class FutsalPlayerSimulator:
    """
    Simulador de comportamiento realista de jugador de fútbol sala
    """
    def __init__(self, field_width=40, field_height=20):
        self.field_width = field_width
        self.field_height = field_height
        
        # Parámetros de movimiento realista
        self.base_speed = 1.5  # m/s - velocidad de trote normal
        self.max_speed = 6.5   # m/s - sprint máximo
        self.acceleration = 3.0  # m/s² - aceleración realista
        
        # Estados del jugador
        self.movement_states = {
            'walking': {'speed_range': (0.5, 1.5), 'probability': 0.3},
            'jogging': {'speed_range': (1.5, 3.0), 'probability': 0.4},
            'running': {'speed_range': (3.0, 4.5), 'probability': 0.2},
            'sprinting': {'speed_range': (4.5, 6.5), 'probability': 0.1}
        }
        
        # Zonas de juego típicas
        self.zones = {
            'defensive': {'x_range': (0, 13), 'y_range': (0, 20)},
            'midfield': {'x_range': (13, 27), 'y_range': (0, 20)},
            'offensive': {'x_range': (27, 40), 'y_range': (0, 20)},
            'penalty_area_own': {'x_range': (0, 6), 'y_range': (7, 13)},
            'penalty_area_opp': {'x_range': (34, 40), 'y_range': (7, 13)}
        }
        
    def get_zone_center(self, zone_name):
        """Obtener centro de una zona"""
        zone = self.zones[zone_name]
        center_x = (zone['x_range'][0] + zone['x_range'][1]) / 2
        center_y = (zone['y_range'][0] + zone['y_range'][1]) / 2
        return center_x, center_y
    
    def determine_current_zone(self, x, y):
        """Determinar en qué zona está el jugador"""
        for zone_name, zone in self.zones.items():
            if (zone['x_range'][0] <= x <= zone['x_range'][1] and 
                zone['y_range'][0] <= y <= zone['y_range'][1]):
                return zone_name
        return 'midfield'  # Default
    
    def generate_ball_trajectory(self, duration_seconds, fps=25):
        """Generar una trayectoria de balón realista"""
        frames = int(duration_seconds * fps)
        ball_positions = []
        
        # Inicio del balón (zona central)
        ball_x, ball_y = 20, 10
        
        for i in range(frames):
            t = i / fps
            
            # Movimiento del balón con física realista
            if t < 5:  # Primeros 5s: pase lateral
                ball_x = 20 + np.sin(t * 0.5) * 8
                ball_y = 10 + np.cos(t * 0.3) * 3
            elif t < 15:  # 5-15s: jugada ofensiva
                progress = (t - 5) / 10
                ball_x = 20 + progress * 15 + np.sin(t * 2) * 2
                ball_y = 10 + np.sin(progress * np.pi) * 4
            elif t < 25:  # 15-25s: contraataque
                progress = (t - 15) / 10
                ball_x = 35 - progress * 20 + np.random.normal(0, 0.5)
                ball_y = 10 + np.sin(progress * np.pi * 2) * 6
            else:  # Resto: juego posicional
                ball_x = 20 + np.sin(t * 0.2) * 10
                ball_y = 10 + np.cos(t * 0.15) * 5
            
            # Mantener el balón en el campo
            ball_x = np.clip(ball_x, 1, 39)
            ball_y = np.clip(ball_y, 1, 19)
            
            ball_positions.append((ball_x, ball_y))
        
        return ball_positions
    
    def calculate_player_response_to_ball(self, player_pos, ball_pos, role="midfielder"):
        """Calcular cómo responde el jugador al balón según su rol"""
        px, py = player_pos
        bx, by = ball_pos
        
        distance_to_ball = np.sqrt((px - bx)**2 + (py - by)**2)
        
        # Diferentes comportamientos según la distancia al balón
        if distance_to_ball < 3:  # Muy cerca del balón
            # Movimiento directo hacia el balón
            target_x = bx + np.random.normal(0, 0.5)
            target_y = by + np.random.normal(0, 0.5)
            urgency = 0.9
            
        elif distance_to_ball < 8:  # Cerca del balón
            # Posicionamiento táctico cerca del balón
            if role == "midfielder":
                target_x = bx + np.random.normal(0, 2)
                target_y = by + np.random.normal(0, 2)
            elif role == "defender":
                # Posición defensiva
                target_x = min(bx - 2, px + 1)
                target_y = by + np.random.normal(0, 1)
            else:  # attacker
                # Buscar espacio ofensivo
                target_x = bx + 3 + np.random.normal(0, 1)
                target_y = by + np.random.normal(0, 2)
            urgency = 0.6
            
        else:  # Lejos del balón
            # Movimiento posicional según rol
            if role == "midfielder":
                target_x = px + np.random.normal(0, 1)
                target_y = py + np.random.normal(0, 1)
            elif role == "defender":
                # Volver a zona defensiva
                target_x = min(px, 15)
                target_y = 10 + np.random.normal(0, 3)
            else:  # attacker
                # Buscar posición ofensiva
                target_x = max(px, 25)
                target_y = py + np.random.normal(0, 2)
            urgency = 0.3
        
        # Mantener en el campo
        target_x = np.clip(target_x, 1, 39)
        target_y = np.clip(target_y, 1, 19)
        
        return (target_x, target_y), urgency
    
    def smooth_movement(self, current_pos, target_pos, current_velocity, dt, urgency=0.5):
        """Movimiento suave y realista hacia un objetivo"""
        cx, cy = current_pos
        tx, ty = target_pos
        vx, vy = current_velocity
        
        # Vector hacia el objetivo
        dx = tx - cx
        dy = ty - cy
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance < 0.1:  # Ya está en el objetivo
            return current_pos, (current_velocity[0] * 0.9, current_velocity[1] * 0.9)  # Desacelerar
        
        # Velocidad deseada según urgencia y distancia
        desired_speed = self.base_speed * (1 + urgency)
        if distance > 5:
            desired_speed *= 1.5  # Acelerar si está lejos
        
        desired_speed = min(desired_speed, self.max_speed)
        
        # Dirección hacia el objetivo
        dir_x = dx / distance
        dir_y = dy / distance
        
        # Velocidad deseada
        desired_vx = dir_x * desired_speed
        desired_vy = dir_y * desired_speed
        
        # Suavizar cambios de velocidad (aceleración limitada)
        max_acceleration = self.acceleration * dt
        
        dvx = desired_vx - vx
        dvy = desired_vy - vy
        
        if abs(dvx) > max_acceleration:
            dvx = max_acceleration * np.sign(dvx)
        if abs(dvy) > max_acceleration:
            dvy = max_acceleration * np.sign(dvy)
        
        # Nueva velocidad
        new_vx = vx + dvx
        new_vy = vy + dvy
        
        # Aplicar ruido realista (pequeñas variaciones)
        noise_factor = 0.1
        new_vx += np.random.normal(0, noise_factor)
        new_vy += np.random.normal(0, noise_factor)
        
        # Nueva posición
        new_x = cx + new_vx * dt
        new_y = cy + new_vy * dt
        
        # Mantener en el campo con rebote suave
        if new_x < 0.5:
            new_x = 0.5
            new_vx = abs(new_vx) * 0.3
        elif new_x > 39.5:
            new_x = 39.5
            new_vx = -abs(new_vx) * 0.3
            
        if new_y < 0.5:
            new_y = 0.5
            new_vy = abs(new_vy) * 0.3
        elif new_y > 19.5:
            new_y = 19.5
            new_vy = -abs(new_vy) * 0.3
        
        return (new_x, new_y), (new_vx, new_vy)
    
    def generate_realistic_session(self, duration_minutes=5, fps=25, player_role="midfielder"):
        """
        Generar una sesión completa de movimiento realista
        """
        print(f"🏟️ Generando sesión de fútbol sala realista...")
        print(f"   ⏱️ Duración: {duration_minutes} minutos")
        print(f"   🎯 Role: {player_role}")
        print(f"   📊 FPS: {fps}")
        
        total_seconds = duration_minutes * 60
        total_frames = int(total_seconds * fps)
        dt = 1.0 / fps
        
        # Generar trayectoria del balón
        ball_positions = self.generate_ball_trajectory(total_seconds, fps)
        
        # Inicializar jugador
        player_x, player_y = self.get_zone_center('midfield')
        player_vx, player_vy = 0.0, 0.0
        
        # Arrays para almacenar datos
        timestamps = []
        positions_x = []
        positions_y = []
        velocities = []
        distances = []
        zones = []
        
        start_time = datetime.now()
        
        print("   🚀 Simulando movimiento...")
        
        for frame in range(total_frames):
            current_time = start_time + timedelta(seconds=frame * dt)
            
            # Posición actual del balón
            ball_x, ball_y = ball_positions[frame]
            
            # Calcular respuesta del jugador al balón
            target_pos, urgency = self.calculate_player_response_to_ball(
                (player_x, player_y), (ball_x, ball_y), player_role
            )
            
            # Movimiento suave hacia el objetivo
            (player_x, player_y), (player_vx, player_vy) = self.smooth_movement(
                (player_x, player_y), target_pos, (player_vx, player_vy), dt, urgency
            )
            
            # Calcular métricas
            speed = np.sqrt(player_vx**2 + player_vy**2)
            
            if frame > 0:
                dx = player_x - positions_x[-1]
                dy = player_y - positions_y[-1]
                distance_step = np.sqrt(dx**2 + dy**2)
            else:
                distance_step = 0
            
            current_zone = self.determine_current_zone(player_x, player_y)
            
            # Almacenar datos
            timestamps.append(current_time)
            positions_x.append(player_x)
            positions_y.append(player_y)
            velocities.append(speed)
            distances.append(distance_step)
            zones.append(current_zone)
            
            # Progreso
            if frame % (total_frames // 20) == 0:
                progress = (frame / total_frames) * 100
                print(f"      📊 Progreso: {progress:.0f}% - Pos: ({player_x:.1f}, {player_y:.1f}) - Velocidad: {speed:.1f} m/s")
        
        # Crear DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'x': positions_x,
            'y': positions_y,
            'tag_id': ['player_01'] * len(timestamps),
            'speed': velocities,
            'distance_step': distances,
            'zone': zones,
            'ball_x': [pos[0] for pos in ball_positions],
            'ball_y': [pos[1] for pos in ball_positions]
        })
        
        # Estadísticas finales
        total_distance = sum(distances)
        avg_speed = np.mean(velocities)
        max_speed = max(velocities)
        
        print(f"\n✅ Sesión generada exitosamente:")
        print(f"   📊 Total frames: {len(df):,}")
        print(f"   📏 Distancia total: {total_distance:.1f} metros")
        print(f"   🏃 Velocidad promedio: {avg_speed:.2f} m/s")
        print(f"   ⚡ Velocidad máxima: {max_speed:.2f} m/s")
        print(f"   🎯 Zonas visitadas: {len(set(zones))} diferentes")
        
        return df
    
    def save_and_visualize(self, df, filename_prefix="realistic_futsal"):
        """Guardar CSV y generar visualización"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Guardar CSV
        os.makedirs("data", exist_ok=True)
        csv_filename = f"data/{filename_prefix}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False)
        
        print(f"\n📁 Archivo guardado: {csv_filename}")
        
        # Crear visualización
        plt.figure(figsize=(16, 10))
        
        # Subplot 1: Trayectoria en el campo
        plt.subplot(2, 2, 1)
        self.draw_futsal_field()
        
        # Colorear trayectoria por velocidad
        velocities = df['speed'].values
        scatter = plt.scatter(df['x'], df['y'], c=velocities, cmap='RdYlBu_r', 
                            s=20, alpha=0.7, edgecolors='black', linewidth=0.3)
        plt.colorbar(scatter, label='Velocidad (m/s)')
        plt.title('🏟️ Trayectoria del Jugador (coloreada por velocidad)')
        plt.xlabel('X (metros)')
        plt.ylabel('Y (metros)')
        
        # Subplot 2: Velocidad en el tiempo
        plt.subplot(2, 2, 2)
        time_seconds = [(t - df['timestamp'].iloc[0]).total_seconds() for t in df['timestamp']]
        plt.plot(time_seconds, df['speed'], color='blue', alpha=0.7, linewidth=1)
        plt.fill_between(time_seconds, df['speed'], alpha=0.3, color='lightblue')
        plt.title('⚡ Velocidad vs Tiempo')
        plt.xlabel('Tiempo (segundos)')
        plt.ylabel('Velocidad (m/s)')
        plt.grid(True, alpha=0.3)
        
        # Subplot 3: Distribución de velocidades
        plt.subplot(2, 2, 3)
        plt.hist(df['speed'], bins=50, alpha=0.7, color='green', edgecolor='black')
        plt.axvline(df['speed'].mean(), color='red', linestyle='--', 
                   label=f'Promedio: {df["speed"].mean():.2f} m/s')
        plt.title('📊 Distribución de Velocidades')
        plt.xlabel('Velocidad (m/s)')
        plt.ylabel('Frecuencia')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Subplot 4: Mapa de calor de posiciones
        plt.subplot(2, 2, 4)
        self.draw_futsal_field()
        plt.hist2d(df['x'], df['y'], bins=20, cmap='Reds', alpha=0.7)
        plt.colorbar(label='Tiempo en zona')
        plt.title('🔥 Mapa de Calor - Posiciones Frecuentes')
        plt.xlabel('X (metros)')
        plt.ylabel('Y (metros)')
        
        plt.tight_layout()
        
        # Guardar gráfico
        os.makedirs("outputs", exist_ok=True)
        plot_filename = f"outputs/{filename_prefix}_analysis_{timestamp}.png"
        plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
        plt.show()
        
        print(f"📊 Visualización guardada: {plot_filename}")
        
        return csv_filename, plot_filename
    
    def draw_futsal_field(self):
        """Dibujar campo de fútbol sala básico"""
        # Campo principal
        plt.gca().add_patch(plt.Rectangle((0, 0), 40, 20, fill=False, 
                                        edgecolor='black', linewidth=2))
        
        # Línea central
        plt.plot([20, 20], [0, 20], 'k-', linewidth=2)
        
        # Círculo central
        circle = plt.Circle((20, 10), 3, fill=False, edgecolor='black', linewidth=2)
        plt.gca().add_patch(circle)
        
        # Áreas de portería
        plt.gca().add_patch(plt.Rectangle((0, 7), 6, 6, fill=False, 
                                        edgecolor='black', linewidth=2))
        plt.gca().add_patch(plt.Rectangle((34, 7), 6, 6, fill=False, 
                                        edgecolor='black', linewidth=2))
        
        # Porterías
        plt.plot([0, 0], [8.5, 11.5], 'k-', linewidth=4)
        plt.plot([40, 40], [8.5, 11.5], 'k-', linewidth=4)
        
        plt.xlim(-1, 41)
        plt.ylim(-1, 21)
        plt.gca().set_aspect('equal')

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='🏟️ Generador de Datos Realistas de Fútbol Sala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python generate_realistic_futsal_data.py                           # Sesión estándar 5 minutos
  python generate_realistic_futsal_data.py --duration 10 --role defender    # 10 min como defensa
  python generate_realistic_futsal_data.py --duration 3 --fps 50 --role attacker  # 3 min alta frecuencia como delantero
        """
    )
    
    parser.add_argument('--duration', type=int, default=5,
                       help='Duración en minutos (default: 5)')
    parser.add_argument('--fps', type=int, default=25,
                       help='Frames por segundo (default: 25)')
    parser.add_argument('--role', choices=['midfielder', 'defender', 'attacker'], 
                       default='midfielder',
                       help='Rol del jugador (default: midfielder)')
    parser.add_argument('--prefix', default='realistic_futsal',
                       help='Prefijo para nombres de archivo (default: realistic_futsal)')
    
    args = parser.parse_args()
    
    print("🏟️ GENERADOR DE DATOS REALISTAS DE FÚTBOL SALA")
    print("=" * 60)
    
    # Crear simulador
    simulator = FutsalPlayerSimulator()
    
    # Generar sesión
    df = simulator.generate_realistic_session(
        duration_minutes=args.duration,
        fps=args.fps,
        player_role=args.role
    )
    
    # Guardar y visualizar
    csv_file, plot_file = simulator.save_and_visualize(df, args.prefix)
    
    print(f"\n🎯 ARCHIVOS GENERADOS:")
    print(f"   📄 CSV: {csv_file}")
    print(f"   📊 Gráfico: {plot_file}")
    print(f"\n💡 SIGUIENTE PASO:")
    print(f"   python movement_replay.py {csv_file}")
    print("=" * 60)

if __name__ == "__main__":
    main() 