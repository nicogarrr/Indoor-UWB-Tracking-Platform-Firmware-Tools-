#!/usr/bin/env python3
"""
Generador de Mapas de Calor para Sistema UWB Fútbol Sala
Crea visualizaciones avanzadas de densidad de movimiento y zonas de actividad
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle, Wedge, Circle
from matplotlib.colors import LinearSegmentedColormap
import argparse
import os
from datetime import datetime
from scipy.stats import gaussian_kde
from scipy.ndimage import gaussian_filter

class FutsalHeatmapGenerator:
    """Generador profesional de mapas de calor para fútbol sala"""
    
    def __init__(self):
        # Dimensiones de la cancha (40x20m)
        self.court_width = 40
        self.court_height = 20
        
        # Configuración de resolución del mapa de calor
        self.resolution = 100  # 100x50 grid points
        self.x_grid = np.linspace(0, self.court_width, self.resolution)
        self.y_grid = np.linspace(0, self.court_height, self.resolution//2)
        
        # Configuración de colores
        self.setup_color_schemes()
        
        # Zonas tácticas predefinidas
        self.tactical_zones = {
            'area_local': {'x': [0, 6], 'y': [4, 16], 'name': 'Área Local'},
            'zona_defensiva': {'x': [0, 13.33], 'y': [0, 20], 'name': 'Zona Defensiva'},
            'zona_media': {'x': [13.33, 26.67], 'y': [0, 20], 'name': 'Zona Media'},
            'zona_ofensiva': {'x': [26.67, 40], 'y': [0, 20], 'name': 'Zona Ofensiva'},
            'area_visitante': {'x': [34, 40], 'y': [4, 16], 'name': 'Área Visitante'},
            'circulo_central': {'x': [17, 23], 'y': [7, 13], 'name': 'Círculo Central'}
        }
    
    def setup_color_schemes(self):
        """Configurar esquemas de colores profesionales"""
        # Esquema de calor clásico (azul → rojo)
        self.heat_colors = ['#000033', '#000055', '#000077', '#003399', 
                           '#0066CC', '#3399FF', '#66CCFF', '#99FFCC',
                           '#CCFF99', '#FFFF66', '#FFCC33', '#FF9900',
                           '#FF6600', '#FF3300', '#CC0000']
        
        # Esquema fútbol sala (verde → amarillo → rojo)
        self.futsal_colors = ['#001a00', '#003300', '#006600', '#009900',
                             '#00CC00', '#33FF33', '#66FF66', '#99FF99',
                             '#CCFF99', '#FFFF66', '#FFCC00', '#FF9900',
                             '#FF6600', '#FF3300', '#CC0000']
        
        # Esquema profesional (violeta → azul → verde → amarillo → rojo)
        self.pro_colors = ['#1a0033', '#330066', '#4d0099', '#6600CC',
                          '#0033FF', '#0066FF', '#0099FF', '#00CCFF',
                          '#00FF99', '#33FF66', '#66FF33', '#99FF00',
                          '#CCFF00', '#FFCC00', '#FF6600', '#FF0000']
    
    def load_processed_data(self, csv_file):
        """Cargar datos procesados desde CSV"""
        try:
            print(f"Cargando datos: {os.path.basename(csv_file)}")
            df = pd.read_csv(csv_file)
            
            # Verificar columnas requeridas
            required_cols = ['x', 'y', 'timestamp']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"Error - Columnas faltantes: {missing_cols}")
                return None
            
            # Convertir timestamp si es necesario
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filtrar datos válidos
            df = df.dropna(subset=['x', 'y'])
            df = df[(df['x'] >= 0) & (df['x'] <= 40) & 
                   (df['y'] >= 0) & (df['y'] <= 20)]
            
            print(f"Datos cargados: {len(df)} posiciones válidas")
            print(f"Rango X: {df['x'].min():.1f} - {df['x'].max():.1f}m")
            print(f"Rango Y: {df['y'].min():.1f} - {df['y'].max():.1f}m")
            
            return df
            
        except Exception as e:
            print(f"❌ Error cargando {csv_file}: {str(e)}")
            return None
    
    def calculate_density_grid(self, df, method='gaussian'):
        """Calcular grid de densidad usando diferentes métodos"""
        if method == 'gaussian':
            return self._gaussian_density(df)
        elif method == 'histogram':
            return self._histogram_density(df)
        elif method == 'kde':
            return self._kde_density(df)
        else:
            return self._gaussian_density(df)
    
    def _gaussian_density(self, df):
        """Densidad usando filtro gaussiano"""
        # Crear histograma 2D
        hist, x_edges, y_edges = np.histogram2d(
            df['x'], df['y'], 
            bins=[self.resolution, self.resolution//2],
            range=[[0, self.court_width], [0, self.court_height]]
        )
        
        # Aplicar suavizado gaussiano
        density = gaussian_filter(hist, sigma=2.0)
        
        return density.T  # Transponer para orientación correcta
    
    def _histogram_density(self, df):
        """Densidad usando histograma simple"""
        hist, x_edges, y_edges = np.histogram2d(
            df['x'], df['y'],
            bins=[self.resolution, self.resolution//2],
            range=[[0, self.court_width], [0, self.court_height]]
        )
        return hist.T
    
    def _kde_density(self, df):
        """Densidad usando Kernel Density Estimation"""
        if len(df) < 10:
            return self._histogram_density(df)
        
        # Submuestrear si hay muchos puntos (para rendimiento)
        if len(df) > 5000:
            df_sample = df.sample(n=5000, random_state=42)
        else:
            df_sample = df
        
        # Crear KDE
        kde = gaussian_kde([df_sample['x'], df_sample['y']])
        
        # Evaluar en grid
        X, Y = np.meshgrid(self.x_grid, self.y_grid)
        positions = np.vstack([X.ravel(), Y.ravel()])
        density = kde(positions).reshape(X.shape)
        
        return density
    
    def draw_futsal_court_background(self, ax):
        """Dibujar cancha de fútbol sala como fondo"""
        # Fondo de la cancha
        court = Rectangle((0, 0), 40, 20, linewidth=3,
                         edgecolor='white', facecolor='none', alpha=0.8)
        ax.add_patch(court)
        
        # Línea central
        ax.plot([20, 20], [0, 20], 'white', linewidth=2, alpha=0.8)
        
        # Círculo central
        center_circle = Circle((20, 10), 3, linewidth=2,
                             edgecolor='white', facecolor='none', alpha=0.8)
        ax.add_patch(center_circle)
        
        # Áreas de portería
        penalty_left = Wedge((0, 10), 6, -90, 90, linewidth=2,
                           edgecolor='white', facecolor='none', alpha=0.8)
        penalty_right = Wedge((40, 10), 6, 90, 270, linewidth=2,
                            edgecolor='white', facecolor='none', alpha=0.8)
        ax.add_patch(penalty_left)
        ax.add_patch(penalty_right)
        
        # Porterías
        ax.plot([0, 0], [8.5, 11.5], 'white', linewidth=4, alpha=0.9)
        ax.plot([40, 40], [8.5, 11.5], 'white', linewidth=4, alpha=0.9)
        
        # Puntos de penalti
        ax.plot(6, 10, 'wo', markersize=8, alpha=0.8)
        ax.plot(34, 10, 'wo', markersize=8, alpha=0.8)
        ax.plot(10, 10, 'wo', markersize=6, alpha=0.8)
        ax.plot(30, 10, 'wo', markersize=6, alpha=0.8)
        
        # Esquinas
        corners = [(0, 0), (0, 20), (40, 0), (40, 20)]
        for x, y in corners:
            if x == 0 and y == 0:
                corner = Wedge((x, y), 0.25, 0, 90, linewidth=1.5,
                             edgecolor='white', facecolor='none', alpha=0.8)
            elif x == 0 and y == 20:
                corner = Wedge((x, y), 0.25, 270, 360, linewidth=1.5,
                             edgecolor='white', facecolor='none', alpha=0.8)
            elif x == 40 and y == 0:
                corner = Wedge((x, y), 0.25, 90, 180, linewidth=1.5,
                             edgecolor='white', facecolor='none', alpha=0.8)
            else:
                corner = Wedge((x, y), 0.25, 180, 270, linewidth=1.5,
                             edgecolor='white', facecolor='none', alpha=0.8)
            ax.add_patch(corner)
    
    def create_heatmap(self, df, style='professional', method='gaussian', 
                      show_trajectory=True, show_zones=False):
        """Crear mapa de calor profesional"""
        print(f"🔥 Generando mapa de calor estilo '{style}' con método '{method}'...")
        
        # Calcular densidad
        density = self.calculate_density_grid(df, method)
        
        # Configurar figura
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Seleccionar esquema de colores
        if style == 'heat':
            colors = self.heat_colors
            cmap_name = 'Calor Clásico'
        elif style == 'futsal':
            colors = self.futsal_colors
            cmap_name = 'Fútbol Sala'
        else:  # professional
            colors = self.pro_colors
            cmap_name = 'Profesional'
        
        # Crear colormap personalizado
        custom_cmap = LinearSegmentedColormap.from_list(
            'custom', colors, N=256
        )
        
        # Dibujar mapa de calor
        extent = (0, self.court_width, 0, self.court_height)
        heatmap = ax.imshow(density, extent=extent, origin='lower',
                          cmap=custom_cmap, alpha=0.85, interpolation='bilinear')
        
        # Dibujar cancha encima
        self.draw_futsal_court_background(ax)
        
        # Agregar trayectoria si se solicita
        if show_trajectory and len(df) > 1:
            # Submuestrear trayectoria para mejor visualización
            if len(df) > 1000:
                step = len(df) // 1000
                traj_df = df.iloc[::step]
            else:
                traj_df = df
                
            ax.plot(traj_df['x'], traj_df['y'], 'cyan', 
                   linewidth=1.5, alpha=0.7, label='Trayectoria')
            ax.plot(df['x'].iloc[0], df['y'].iloc[0], 'go', 
                   markersize=10, label='Inicio', markeredgecolor='white')
            ax.plot(df['x'].iloc[-1], df['y'].iloc[-1], 'ro', 
                   markersize=10, label='Final', markeredgecolor='white')
        
        # Mostrar zonas tácticas si se solicita
        if show_zones:
            self.draw_tactical_zones(ax)
        
        # Configurar ejes y título
        ax.set_xlim(0, 40)
        ax.set_ylim(0, 20)
        ax.set_xlabel('Posición X (metros)', fontsize=12, color='white')
        ax.set_ylabel('Posición Y (metros)', fontsize=12, color='white')
        
        # Título dinámico
        duration = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
        total_distance = self.calculate_total_distance(df)
        
        title = (f'MAPA DE CALOR - CIERRE DEFENSIVO FUTBOL SALA\n'
                f'{len(df)} posiciones | {duration:.1f}s | '
                f'{total_distance:.1f}m | {cmap_name}')
        
        ax.set_title(title, fontsize=14, fontweight='bold', 
                    color='white', pad=20)
        
        # Colorbar con estilo
        cbar = plt.colorbar(heatmap, ax=ax, shrink=0.8, aspect=30, pad=0.02)
        cbar.set_label('Densidad de Actividad', rotation=270, 
                      labelpad=20, fontsize=11, color='white')
        cbar.ax.tick_params(colors='white')
        
        # Leyenda si hay trayectoria
        if show_trajectory:
            ax.legend(loc='upper left', fontsize=10, 
                     facecolor='black', edgecolor='white', framealpha=0.8)
        
        # Grid sutil
        ax.grid(True, alpha=0.2, color='white', linewidth=0.5)
        ax.set_facecolor('#0a0a0a')
        
        return fig, ax, density
    
    def draw_tactical_zones(self, ax):
        """Dibujar zonas tácticas en el mapa"""
        zone_colors = ['red', 'blue', 'green', 'orange', 'purple', 'yellow']
        
        for i, (zone_name, zone_data) in enumerate(self.tactical_zones.items()):
            x_range = zone_data['x']
            y_range = zone_data['y']
            color = zone_colors[i % len(zone_colors)]
            
            # Rectángulo de zona
            zone_rect = Rectangle(
                (x_range[0], y_range[0]), 
                x_range[1] - x_range[0], 
                y_range[1] - y_range[0],
                linewidth=2, edgecolor=color, facecolor='none',
                alpha=0.6, linestyle='--'
            )
            ax.add_patch(zone_rect)
            
            # Etiqueta de zona
            center_x = (x_range[0] + x_range[1]) / 2
            center_y = (y_range[0] + y_range[1]) / 2
            ax.text(center_x, center_y, zone_data['name'], 
                   ha='center', va='center', fontsize=8, color=color,
                   fontweight='bold', alpha=0.8)
    
    def calculate_total_distance(self, df):
        """Calcular distancia total recorrida"""
        if len(df) < 2:
            return 0.0
        
        distances = []
        for i in range(1, len(df)):
            dx = df['x'].iloc[i] - df['x'].iloc[i-1]
            dy = df['y'].iloc[i] - df['y'].iloc[i-1]
            distances.append(np.sqrt(dx**2 + dy**2))
        
        return sum(distances)
    
    def analyze_zone_activity(self, df):
        """Analizar actividad por zonas tácticas"""
        print("\n📍 ANÁLISIS POR ZONAS TÁCTICAS:")
        print("=" * 50)
        
        zone_stats = {}
        
        for zone_name, zone_data in self.tactical_zones.items():
            x_range = zone_data['x']
            y_range = zone_data['y']
            
            # Filtrar posiciones en esta zona
            in_zone = df[
                (df['x'] >= x_range[0]) & (df['x'] <= x_range[1]) &
                (df['y'] >= y_range[0]) & (df['y'] <= y_range[1])
            ]
            
            count = len(in_zone)
            percentage = (count / len(df)) * 100 if len(df) > 0 else 0
            
            zone_stats[zone_name] = {
                'count': count,
                'percentage': percentage,
                'name': zone_data['name']
            }
            
            print(f"🏃 {zone_data['name']:20} | "
                  f"{count:4d} pos ({percentage:5.1f}%)")
        
        # Zona más activa
        most_active = max(zone_stats.items(), 
                         key=lambda x: x[1]['percentage'])
        print(f"\n⚡ Zona más activa: {most_active[1]['name']} "
              f"({most_active[1]['percentage']:.1f}%)")
        
        return zone_stats
    
    def create_comparison_heatmaps(self, df, output_file=None):
        """Crear comparación de diferentes estilos de mapas de calor"""
        print("🎨 Generando comparación de estilos...")
        
        fig, axes = plt.subplots(2, 2, figsize=(20, 12))
        fig.suptitle('COMPARACION DE MAPAS DE CALOR - FUTBOL SALA', 
                    fontsize=16, fontweight='bold', color='white')
        
        styles = [
            ('professional', 'Profesional'),
            ('heat', 'Calor Clásico'),
            ('futsal', 'Fútbol Sala'),
            ('professional', 'Con Zonas Tácticas')
        ]
        
        methods = ['gaussian', 'gaussian', 'gaussian', 'gaussian']
        show_zones = [False, False, False, True]
        
        plt.style.use('dark_background')
        
        for i, ((style, title), method, zones) in enumerate(zip(styles, methods, show_zones)):
            ax = axes[i//2, i%2]
            
            # Calcular densidad
            density = self.calculate_density_grid(df, method)
            
            # Seleccionar colores
            if style == 'heat':
                colors = self.heat_colors
            elif style == 'futsal':
                colors = self.futsal_colors
            else:
                colors = self.pro_colors
            
            custom_cmap = LinearSegmentedColormap.from_list(
                'custom', colors, N=256
            )
            
            # Dibujar mapa
            extent = (0, self.court_width, 0, self.court_height)
            heatmap = ax.imshow(density, extent=extent, origin='lower',
                              cmap=custom_cmap, alpha=0.85, 
                              interpolation='bilinear')
            
            # Cancha
            self.draw_futsal_court_background(ax)
            
            # Zonas si corresponde
            if zones:
                self.draw_tactical_zones(ax)
            
            # Trayectoria
            if len(df) > 1000:
                step = len(df) // 500
                traj_df = df.iloc[::step]
            else:
                traj_df = df
            
            ax.plot(traj_df['x'], traj_df['y'], 'cyan', 
                   linewidth=1, alpha=0.6)
            
            # Configuración
            ax.set_xlim(0, 40)
            ax.set_ylim(0, 20)
            ax.set_title(f'{title}', fontsize=12, fontweight='bold', 
                        color='white')
            ax.set_xlabel('X (m)', fontsize=10, color='white')
            ax.set_ylabel('Y (m)', fontsize=10, color='white')
            ax.set_facecolor('#0a0a0a')
            ax.grid(True, alpha=0.2, color='white', linewidth=0.5)
            
            # Mini colorbar
            cbar = plt.colorbar(heatmap, ax=ax, shrink=0.7, aspect=20)
            cbar.ax.tick_params(colors='white', labelsize=8)
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight',
                       facecolor='black', edgecolor='white')
            print(f"💾 Comparación guardada: {output_file}")
        
        return fig
    
    def save_heatmap(self, fig, df, style='professional', output_dir='plots'):
        """Guardar mapa de calor con nombre descriptivo"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        duration = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
        
        filename = f"heatmap_{style}_{len(df)}pts_{duration:.0f}s_{timestamp}.png"
        output_path = os.path.join(output_dir, filename)
        
        # Guardar con alta calidad
        fig.savefig(output_path, dpi=300, bbox_inches='tight',
                   facecolor='black', edgecolor='white')
        
        print(f"💾 Mapa de calor guardado: {output_path}")
        return output_path

def select_heatmap_file_interactive():
    """
    Selección interactiva de archivos para mapas de calor
    """
    import os
    import glob
    from datetime import datetime
    
    # Buscar archivos procesados primero, luego datos brutos
    processed_files = glob.glob("processed_data/*.csv")
    data_files = glob.glob("data/*.csv")
    
    all_files = []
    
    # Priorizar archivos procesados
    if processed_files:
        all_files.extend(processed_files)
    if data_files:
        all_files.extend(data_files)
    
    if not all_files:
        print("❌ No se encontraron archivos CSV en processed_data/ o data/")
        return None
    
    print("\n🔥 SELECCIONAR ARCHIVO PARA MAPA DE CALOR:")
    print("=" * 60)
    print("ℹ️  Recomendado: usar archivos de 'processed_data/' para mejores resultados")
    print()
    
    for i, file_path in enumerate(all_files, 1):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / 1024  # KB
        mod_time = os.path.getmtime(file_path)
        mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
        
        if file_path.startswith("processed_data/"):
            folder = "📊 processed_data/"
            status = "✅ PROCESADO"
        else:
            folder = "📁 data/"
            status = "⚠️  RAW"
        
        print(f"{i:2d}. {folder}{file_name:<30} | {file_size:6.1f}KB | {mod_date} | {status}")
    
    print(f"\n 0. ❌ Cancelar")
    
    while True:
        try:
            choice = input(f"\n👆 Selecciona un archivo (1-{len(all_files)}) o 0 para cancelar: ").strip()
            
            if choice == '0':
                print("❌ Operación cancelada")
                return None
            
            file_idx = int(choice) - 1
            if 0 <= file_idx < len(all_files):
                selected_file = all_files[file_idx]
                print(f"✅ Archivo seleccionado: {selected_file}")
                return selected_file
            else:
                print(f"⚠️  Número inválido. Ingresa un número entre 1 y {len(all_files)}")
                
        except ValueError:
            print("⚠️  Por favor ingresa un número válido")
        except KeyboardInterrupt:
            print("\n❌ Operación cancelada")
            return None


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='GENERADOR DE MAPAS DE CALOR UWB PARA FUTBOL SALA',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python heatmap_generator.py                                    # Selección interactiva
  python heatmap_generator.py processed_data/mi_archivo.csv      # Archivo específico
  python heatmap_generator.py --style heat --zones              # Estilo calor con zonas
  python heatmap_generator.py --comparison                      # Comparar todos los estilos
        """
    )
    
    parser.add_argument('csv_file', nargs='?',
                       help='Archivo CSV con datos procesados (opcional - si no se especifica, selección interactiva)')
    parser.add_argument('--style', choices=['professional', 'heat', 'futsal'],
                       default='professional',
                       help='Estilo del mapa de calor')
    parser.add_argument('--method', choices=['gaussian', 'histogram', 'kde'],
                       default='gaussian',
                       help='Método de cálculo de densidad')
    parser.add_argument('--zones', action='store_true',
                       help='Mostrar zonas tácticas')
    parser.add_argument('--no-trajectory', action='store_true',
                       help='No mostrar trayectoria')
    parser.add_argument('--comparison', action='store_true',
                       help='Generar comparación de estilos')
    parser.add_argument('--output-dir', default='plots',
                       help='Directorio de salida')
    
    args = parser.parse_args()
    
    # Selección de archivo
    if args.csv_file:
        # Archivo especificado por parámetro
        if not os.path.exists(args.csv_file):
            print(f"❌ Error: No se encontró el archivo '{args.csv_file}'")
            return
        selected_file = args.csv_file
    else:
        # Selección interactiva
        selected_file = select_heatmap_file_interactive()
        if selected_file is None:
            return
    
    print("GENERADOR DE MAPAS DE CALOR UWB")
    print("=" * 50)
    
    # Crear generador
    generator = FutsalHeatmapGenerator()
    
    # Cargar datos
    df = generator.load_processed_data(selected_file)
    if df is None:
        return
    
    # Análisis de zonas
    generator.analyze_zone_activity(df)
    
    if args.comparison:
        # Generar comparación
        fig_comp = generator.create_comparison_heatmaps(df)
        comp_file = os.path.join(args.output_dir, 
                                f"heatmap_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        fig_comp.savefig(comp_file, dpi=300, bbox_inches='tight',
                        facecolor='black', edgecolor='white')
        print(f"💾 Comparación guardada: {comp_file}")
        plt.show()
    else:
        # Generar mapa individual
        fig, ax, density = generator.create_heatmap(
            df, 
            style=args.style,
            method=args.method,
            show_trajectory=not args.no_trajectory,
            show_zones=args.zones
        )
        
        # Guardar
        generator.save_heatmap(fig, df, args.style, args.output_dir)
        
        # Mostrar
        plt.show()

if __name__ == "__main__":
    main() 