import pandas as pd
import numpy as np
import sys

file_path = r"C:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251120_134419.csv"

try:
    df = pd.read_csv(file_path)
    if df.empty:
        print("CSV is empty.")
        sys.exit(1)
        
    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Calculate time differences in seconds
    df['delta_t'] = df['timestamp'].diff().dt.total_seconds()
    
    # Filter out the first NaN and any zero deltas to avoid division by zero
    valid_deltas = df['delta_t'][1:]
    valid_deltas = valid_deltas[valid_deltas > 0]
    
    if valid_deltas.empty:
        print("Not enough data to calculate frequency.")
        sys.exit(1)
        
    # Calculate Instantaneous Frequency
    freqs = 1.0 / valid_deltas
    
    print(f"Analysis of: {file_path}")
    print(f"Total Samples: {len(df)}")
    print(f"Duration: {(df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds():.2f} seconds")
    print("-" * 30)
    print(f"Average Frequency: {freqs.mean():.2f} Hz")
    print(f"Median Frequency:  {freqs.median():.2f} Hz")
    print(f"Min Frequency:     {freqs.min():.2f} Hz")
    print(f"Max Frequency:     {freqs.max():.2f} Hz")
    print(f"Std Dev Frequency: {freqs.std():.2f} Hz")
    print("-" * 30)
    
    # Jitter (Standard Deviation of the time intervals)
    jitter_ms = valid_deltas.std() * 1000
    print(f"Jitter (Interval Std Dev): {jitter_ms:.2f} ms")
    print(f"Average Interval:          {valid_deltas.mean() * 1000:.2f} ms")

except Exception as e:
    print(f"Error: {e}")
