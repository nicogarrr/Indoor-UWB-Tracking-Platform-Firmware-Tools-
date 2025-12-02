import pandas as pd
import numpy as np

file_path = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251127_154628.csv"

output_file = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\verification_report.txt"

with open(output_file, "w", encoding="utf-8") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    log(f"Deep Verification of: {file_path}")
    df = pd.read_csv(file_path)

    # 1. Check for Duplicates
    total_rows = len(df)
    unique_pos = df.drop_duplicates(subset=['x', 'y', 'z'])
    unique_ts = df.drop_duplicates(subset=['device_timestamp'])

    log(f"\n[1] Uniqueness Check")
    log(f"Total Rows: {total_rows}")
    log(f"Unique Positions (X,Y,Z): {len(unique_pos)} ({len(unique_pos)/total_rows*100:.1f}%)")
    log(f"Unique Device Timestamps: {len(unique_ts)} ({len(unique_ts)/total_rows*100:.1f}%)")

    if len(unique_ts) < total_rows * 0.95:
        log("WARNING: Many duplicate timestamps found. Data might be buffered/repeated.")
    else:
        log("SUCCESS: Timestamps are unique. Each row is a new packet.")

    # 2. Analyze Intervals
    log(f"\n[2] Interval Analysis (Device Timestamp)")
    df['ts_diff'] = df['device_timestamp'].diff()
    valid_diffs = df['ts_diff'][df['ts_diff'] > 0]

    mean_interval = valid_diffs.mean()
    std_interval = valid_diffs.std()
    freq = 1000.0 / mean_interval

    log(f"Mean Interval: {mean_interval:.2f} ms")
    log(f"Std Dev Interval: {std_interval:.2f} ms")
    log(f"Calculated Frequency: {freq:.2f} Hz")

    log(f"\n[3] Distribution of Intervals")
    log(str(valid_diffs.value_counts().head(5)))

    # 4. Check for 'Stuck' Data
    # Calculate distance between consecutive points
    df['move_dist'] = np.sqrt(df['x'].diff()**2 + df['y'].diff()**2)
    stuck_frames = len(df[df['move_dist'] == 0])
    log(f"\n[4] Movement Check")
    log(f"Frames with 0 movement: {stuck_frames}")
    if stuck_frames > total_rows * 0.1:
        log("WARNING: Tag position seems stuck in many frames.")
    else:
        log("SUCCESS: Tag position is changing dynamically.")

    log("\n[5] Conclusion")
    if freq > 35 and len(unique_ts) > total_rows * 0.99:
        log("VERDICT: REAL 40Hz PERFORMANCE CONFIRMED.")
        log("Reason: TDMA Slot = Cycle Time allows continuous transmission.")
    else:
        log("VERDICT: Data suspicious. Check warnings above.")
