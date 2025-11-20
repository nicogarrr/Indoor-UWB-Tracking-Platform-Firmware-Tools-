import pandas as pd
import numpy as np
import sys
import os

files = [
    ("NEW (13:44)", r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251120_134419.csv"),
    ("OLD (13:07)", r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251120_130758.csv")
]

for label, file_path in files:
    print(f"\n=== ANALYSIS: {label} ===")
    print(f"File: {os.path.basename(file_path)}")
    
    try:
        if not os.path.exists(file_path):
            print("Error: File not found")
            continue
            
        df = pd.read_csv(file_path)
        if df.empty:
            print("Error: CSV is empty")
            continue
            
        # Parse timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculate time differences
        df['delta_t'] = df['timestamp'].diff().dt.total_seconds()
        
        # Filter valid deltas
        valid_deltas = df['delta_t'][1:]
        valid_deltas = valid_deltas[valid_deltas > 0]
        
        if valid_deltas.empty:
            print("Error: No valid time deltas")
            continue
            
        freqs = 1.0 / valid_deltas
        
        print(f"Total Samples:       {len(df)}")
        print(f"Duration:            {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds():.2f} s")
        print(f"Average Frequency:   {freqs.mean():.2f} Hz")
        print(f"Median Frequency:    {freqs.median():.2f} Hz")
        print(f"Min Frequency:       {freqs.min():.2f} Hz")
        print(f"Max Frequency:       {freqs.max():.2f} Hz")
        print(f"Std Dev Frequency:   {freqs.std():.2f} Hz")
        print(f"Average Interval:    {valid_deltas.mean() * 1000:.2f} ms")
        print(f"Jitter (Std Dev):    {valid_deltas.std() * 1000:.2f} ms")

    except Exception as e:
        print(f"Error: {str(e)}")
