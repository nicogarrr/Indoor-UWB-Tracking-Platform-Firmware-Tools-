import pandas as pd
import numpy as np
import argparse
import os
import matplotlib.pyplot as plt

def validate_precision(csv_file, true_x, true_y, true_z=None):
    print(f"\n=== UWB PRECISION VALIDATION ===")
    print(f"File: {os.path.basename(csv_file)}")
    print(f"Ground Truth: ({true_x}, {true_y}" + (f", {true_z})" if true_z is not None else ")"))
    
    try:
        df = pd.read_csv(csv_file)
        
        if df.empty:
            print("Error: CSV is empty")
            return

        # Calculate statistics
        mean_x = df['x'].mean()
        mean_y = df['y'].mean()
        std_x = df['x'].std()
        std_y = df['y'].std()
        
        # Errors
        df['error_x'] = df['x'] - true_x
        df['error_y'] = df['y'] - true_y
        
        if true_z is not None and 'z' in df.columns:
            mean_z = df['z'].mean()
            std_z = df['z'].std()
            df['error_z'] = df['z'] - true_z
            df['dist_error'] = np.sqrt(df['error_x']**2 + df['error_y']**2 + df['error_z']**2)
            print("-" * 40)
            print(f"SAMPLES:       {len(df)}")
            print(f"MEAN POS:      ({mean_x:.3f}, {mean_y:.3f}, {mean_z:.3f})")
            print(f"OFFSET:        ({mean_x - true_x:.3f}, {mean_y - true_y:.3f}, {mean_z - true_z:.3f})")
            print("-" * 40)
            print(f"PRECISION (Std Dev):")
            print(f"  X: {std_x:.3f} m")
            print(f"  Y: {std_y:.3f} m")
            print(f"  Z: {std_z:.3f} m")
        else:
            df['dist_error'] = np.sqrt(df['error_x']**2 + df['error_y']**2)
            print("-" * 40)
            print(f"SAMPLES:       {len(df)}")
            print(f"MEAN POS:      ({mean_x:.3f}, {mean_y:.3f})")
            print(f"OFFSET:        ({mean_x - true_x:.3f}, {mean_y - true_y:.3f})")
            print("-" * 40)
            print(f"PRECISION (Std Dev):")
            print(f"  X: {std_x:.3f} m")
            print(f"  Y: {std_y:.3f} m")
        
        mean_error = df['dist_error'].mean()
        rmse = np.sqrt((df['dist_error']**2).mean())
        cep95 = np.percentile(df['dist_error'], 95)
        
        print("-" * 40)
        print(f"ACCURACY (3D)" if true_z is not None else f"ACCURACY (2D)")
        print(f"  Mean Error:  {mean_error:.3f} m")
        print(f"  RMSE:        {rmse:.3f} m")
        print(f"  CEP 95%:     {cep95:.3f} m")
        print("-" * 40)
        
        # Plot
        plt.figure(figsize=(10, 8))
        plt.scatter(df['x'], df['y'], alpha=0.5, label='Measurements', s=10)
        plt.scatter(true_x, true_y, color='red', marker='x', s=100, label='Ground Truth', linewidths=3)
        plt.scatter(mean_x, mean_y, color='green', marker='+', s=100, label='Mean Position', linewidths=3)
        
        # Draw circle for CEP95 (2D projection)
        circle = plt.Circle((true_x, true_y), cep95, color='red', fill=False, linestyle='--', label=f'CEP95 ({cep95:.2f}m)')
        plt.gca().add_patch(circle)
        
        plt.axis('equal')
        plt.grid(True)
        plt.legend()
        plt.title(f"UWB Validation\nRMSE: {rmse:.3f}m | StdDev: ({std_x:.3f}, {std_y:.3f})")
        plt.xlabel("X (m)")
        plt.ylabel("Y (m)")
        
        output_plot = csv_file.replace('.csv', '_validation.png')
        plt.savefig(output_plot)
        print(f"Plot saved to: {output_plot}")
        # plt.show() # Uncomment if running locally with display

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate UWB precision against ground truth")
    parser.add_argument("file", help="Path to CSV file with positions")
    parser.add_argument("x", type=float, help="Ground truth X coordinate")
    parser.add_argument("y", type=float, help="Ground truth Y coordinate")
    parser.add_argument("--z", type=float, help="Ground truth Z coordinate (optional)", default=None)
    
    args = parser.parse_args()
    
    validate_precision(args.file, args.x, args.y, args.z)
