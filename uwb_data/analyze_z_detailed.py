import pandas as pd
import numpy as np

file_path = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\uwb_positions_20251127_154628.csv"
output_file = r"c:\Users\Control Lunar\Documents\Indoor-UWB-Tracking-Platform-Firmware-Tools-\uwb_data\z_axis_report.txt"

print(f"Analyzing Z-Axis stability in: {file_path}")
df = pd.read_csv(file_path)

with open(output_file, "w", encoding="utf-8") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    log(f"File: {file_path}")
    log(f"Total Samples: {len(df)}")
    
    z_mean = df['z'].mean()
    z_std = df['z'].std()
    z_min = df['z'].min()
    z_max = df['z'].max()
    
    log("\n=== Z-AXIS STATISTICS ===")
    log(f"Mean Z: {z_mean:.3f} m")
    log(f"Std Dev Z: {z_std:.3f} m ({z_std*100:.1f} cm)")
    log(f"Min Z: {z_min:.3f} m")
    log(f"Max Z: {z_max:.3f} m")
    log(f"Range Z: {z_max - z_min:.3f} m")
    
    # Check for outliers (Z > 2m or Z < -1m which are physically unlikely for a tag on a desk/person)
    outliers = df[(df['z'] > 2.5) | (df['z'] < -0.5)]
    log(f"\n=== OUTLIER CHECK ===")
    log(f"Outliers (Z > 2.5m or Z < -0.5m): {len(outliers)}")
    if not outliers.empty:
        log("Sample outliers:")
        log(str(outliers[['timestamp', 'z']].head()))
    
    # Distribution
    log("\n=== DISTRIBUTION ===")
    log(str(df['z'].describe()))

    log("\n=== CONCLUSION ===")
    if z_std > 0.3:
        log("WARNING: High Z-axis variance (>30cm). Typical for UWB due to poor vertical geometry (GDOP).")
        log("Recommendation: If 2D tracking is the goal, ignore Z or fix it to a constant height.")
    else:
        log("Z-axis is relatively stable.")
