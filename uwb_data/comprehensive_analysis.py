import pandas as pd
import numpy as np
import os

def analyze_uwb_data(file_paths):
    results = []

    print(f"{'File':<40} | {'Freq (Hz)':<10} | {'Jitter (ms)':<12} | {'Mean X':<8} | {'Mean Y':<8} | {'Std X':<8} | {'Std Y':<8}")
    print("-" * 120)

    for file_path in file_paths:
        try:
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                continue

            df = pd.read_csv(file_path)
            if df.empty:
                print(f"Empty file: {file_path}")
                continue

            # Timestamp processing
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['delta_t'] = df['timestamp'].diff().dt.total_seconds()
            
            # Filter valid deltas for frequency calculation
            valid_deltas = df['delta_t'][1:]
            valid_deltas = valid_deltas[valid_deltas > 0] # Avoid division by zero

            if not valid_deltas.empty:
                freqs = 1.0 / valid_deltas
                avg_freq = freqs.mean()
                jitter_ms = valid_deltas.std() * 1000
            else:
                avg_freq = 0
                jitter_ms = 0

            # Position statistics
            mean_x = df['x'].mean()
            mean_y = df['y'].mean()
            std_x = df['x'].std()
            std_y = df['y'].std()
            
            # Z statistics if available
            if 'z' in df.columns:
                mean_z = df['z'].mean()
                std_z = df['z'].std()
            else:
                mean_z = np.nan
                std_z = np.nan

            file_name = os.path.basename(file_path)
            print(f"{file_name:<40} | {avg_freq:<10.2f} | {jitter_ms:<12.2f} | {mean_x:<8.3f} | {mean_y:<8.3f} | {std_x:<8.3f} | {std_y:<8.3f}")

            results.append({
                'file': file_name,
                'avg_freq': avg_freq,
                'jitter_ms': jitter_ms,
                'mean_x': mean_x,
                'mean_y': mean_y,
                'mean_z': mean_z,
                'std_x': std_x,
                'std_y': std_y,
                'std_z': std_z,
                'samples': len(df)
            })

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    return results

if __name__ == "__main__":
    files = [
        r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251125_134019.csv",
        r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251125_135213.csv",
        r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251125_142558.csv",
        r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251125_122654.csv"
    ]
    
    analyze_uwb_data(files)
