import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse

def analyze_z_stability(csv_file, ground_truth_z=1.40):
    print(f"Analyzing Z-Stability for {csv_file}...")
    
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 1. Identify Active Anchors per row
    anchor_cols = [f'anchor_{i}_dist' for i in range(1, 7)]
    df['active_anchors'] = (df[anchor_cols] > 0).sum(axis=1)
    
    # 2. Identify Fallback (Z is exactly 1.0 or very close)
    # Assuming fallback Z is hardcoded to 1.0 in firmware
    df['is_fallback'] = np.isclose(df['z'], 1.0, atol=0.001)
    
    # 3. Calculate Error
    df['z_error'] = df['z'] - ground_truth_z
    
    # 4. Statistics
    print("\n=== Z-AXIS STATISTICS ===")
    print(f"Total Samples: {len(df)}")
    print(f"Ground Truth Z: {ground_truth_z}m")
    print(f"Mean Z: {df['z'].mean():.3f}m")
    print(f"Std Dev Z: {df['z'].std():.3f}m")
    print(f"Min Z: {df['z'].min():.3f}m")
    print(f"Max Z: {df['z'].max():.3f}m")
    
    print("\n=== FALLBACK ANALYSIS (Z=1.0) ===")
    fallback_count = df['is_fallback'].sum()
    print(f"Fallback Samples (Z=1.0): {fallback_count} ({fallback_count/len(df)*100:.1f}%)")
    
    if fallback_count > 0:
        print("Active Anchors during Fallback:")
        print(df[df['is_fallback']]['active_anchors'].value_counts().sort_index())
        
    print("\n=== STABILITY BY ACTIVE ANCHORS ===")
    stats_by_anchors = df.groupby('active_anchors')['z'].agg(['count', 'mean', 'std', 'min', 'max'])
    print(stats_by_anchors)
    
    # 5. Plotting
    plt.figure(figsize=(12, 6))
    
    # Plot Z over time
    # Create a simple index for x-axis if timestamp parsing is complex, or use index
    x = df.index
    
    # Scatter plot colored by number of anchors
    scatter = plt.scatter(x, df['z'], c=df['active_anchors'], cmap='viridis', alpha=0.6, label='Measured Z')
    plt.colorbar(scatter, label='Active Anchors')
    
    # Ground Truth Line
    plt.axhline(y=ground_truth_z, color='r', linestyle='--', linewidth=2, label=f'Ground Truth ({ground_truth_z}m)')
    
    # Fallback Line
    plt.axhline(y=1.0, color='orange', linestyle=':', linewidth=1, label='Fallback (1.0m)')
    
    plt.title(f'Z-Axis Stability Analysis\nFile: {csv_file}')
    plt.xlabel('Sample Index')
    plt.ylabel('Z Height (m)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    output_plot = csv_file.replace('.csv', '_z_analysis.png')
    plt.savefig(output_plot)
    print(f"\nPlot saved to: {output_plot}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to CSV file")
    parser.add_argument("--z", type=float, default=1.40, help="Ground truth Z")
    args = parser.parse_args()
    
    analyze_z_stability(args.file, args.z)
