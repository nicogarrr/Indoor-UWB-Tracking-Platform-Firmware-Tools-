import pandas as pd
import numpy as np
import sys

file_path = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251127_154628.csv"
output_file = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\analysis_results_30hz.txt"

# Ground Truth
GT_X = 2.25
GT_Y = 3.50

try:
    print(f"Analyzing file: {file_path}")
    df = pd.read_csv(file_path)
    if df.empty:
        print("CSV is empty.")
        sys.exit(1)
        
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Analyzing file: {file_path}\n")
        f.write(f"Ground Truth: ({GT_X}, {GT_Y})\n")
        
        # === FREQUENCY ANALYSIS (Using device_timestamp) ===
        f.write("\n=== FREQUENCY ANALYSIS (Device Timestamp) ===\n")
        if 'device_timestamp' in df.columns:
            # Convert ms to seconds for frequency calc
            # Handle potential rollovers or non-monotonicity if needed, but simple diff usually works for short tests
            df['dev_ts_sec'] = df['device_timestamp'] / 1000.0
            df['delta_t'] = df['dev_ts_sec'].diff()
            
            # Filter valid deltas (ignore negative if rollover, though unlikely in short test)
            valid_deltas = df['delta_t'][1:]
            valid_deltas = valid_deltas[valid_deltas > 0]
            
            if valid_deltas.empty:
                f.write("Not enough valid timestamp data.\n")
            else:
                freqs = 1.0 / valid_deltas
                f.write(f"Total Samples: {len(df)}\n")
                duration = df['dev_ts_sec'].iloc[-1] - df['dev_ts_sec'].iloc[0]
                f.write(f"Duration (Device): {duration:.2f} seconds\n")
                f.write(f"Average Frequency: {freqs.mean():.2f} Hz\n")
                f.write(f"Median Frequency:  {freqs.median():.2f} Hz\n")
                f.write(f"Min Frequency:     {freqs.min():.2f} Hz\n")
                f.write(f"Max Frequency:     {freqs.max():.2f} Hz\n")
                f.write(f"Std Dev Frequency: {freqs.std():.2f} Hz\n")
                
                jitter_ms = valid_deltas.std() * 1000
                f.write(f"Jitter (Interval Std Dev): {jitter_ms:.2f} ms\n")
                f.write(f"Average Interval:          {valid_deltas.mean() * 1000:.2f} ms\n")
        else:
            f.write("Column 'device_timestamp' not found. Skipping accurate frequency analysis.\n")

        # === POSITION PRECISION (STABILITY) ===
        f.write("\n=== POSITION PRECISION (STABILITY) ===\n")
        if 'x' in df.columns and 'y' in df.columns:
            mean_x = df['x'].mean()
            mean_y = df['y'].mean()
            mean_z = df['z'].mean() if 'z' in df.columns else 0.0
            
            std_x = df['x'].std()
            std_y = df['y'].std()
            std_z = df['z'].std() if 'z' in df.columns else 0.0

            f.write(f"Mean Position: X={mean_x:.3f}m, Y={mean_y:.3f}m, Z={mean_z:.3f}m\n")
            f.write(f"Std Dev (Precision):\n")
            f.write(f"  X: {std_x:.4f} m ({std_x*100:.2f} cm)\n")
            f.write(f"  Y: {std_y:.4f} m ({std_y*100:.2f} cm)\n")
            f.write(f"  Z: {std_z:.4f} m ({std_z*100:.2f} cm)\n")
            
            # 2D Error from Mean (Precision/Stability)
            df['err_from_mean'] = np.sqrt((df['x'] - mean_x)**2 + (df['y'] - mean_y)**2)
            f.write(f"Mean 2D Error (from centroid): {df['err_from_mean'].mean()*100:.2f} cm\n")
            
            # === POSITION ACCURACY (vs Ground Truth) ===
            f.write("\n=== POSITION ACCURACY (vs Ground Truth) ===\n")
            df['err_from_gt'] = np.sqrt((df['x'] - GT_X)**2 + (df['y'] - GT_Y)**2)
            
            f.write(f"Mean 2D Error (Accuracy): {df['err_from_gt'].mean()*100:.2f} cm\n")
            f.write(f"Min 2D Error:             {df['err_from_gt'].min()*100:.2f} cm\n")
            f.write(f"Max 2D Error:             {df['err_from_gt'].max()*100:.2f} cm\n")
            f.write(f"RMSE (Root Mean Sq Error): {np.sqrt((df['err_from_gt']**2).mean())*100:.2f} cm\n")
            
            f.write(f"X Offset (Mean - GT):      {(mean_x - GT_X)*100:.2f} cm\n")
            f.write(f"Y Offset (Mean - GT):      {(mean_y - GT_Y)*100:.2f} cm\n")

        else:
            f.write("Columns 'x' and 'y' not found in CSV.\n")

except Exception as e:
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Error: {e}\n")
    print(f"Error: {e}")

