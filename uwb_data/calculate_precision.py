import pandas as pd
import numpy as np

# Load data
file_path = 'uwb_positions_20251128_122723.csv'
df = pd.read_csv(file_path)

# Ground Truth
gt_x = 2.25
gt_y = 3.50

# Calculate Errors
df['error_x'] = df['x'] - gt_x
df['error_y'] = df['y'] - gt_y

# Calculate Statistics
stats = {
    'x_mean': df['x'].mean(),
    'y_mean': df['y'].mean(),
    'x_std': df['x'].std(),
    'y_std': df['y'].std(),
    'x_error_mean': df['error_x'].mean(), # Bias
    'y_error_mean': df['error_y'].mean(), # Bias
    'x_error_abs_mean': df['error_x'].abs().mean(), # MAE
    'y_error_abs_mean': df['error_y'].abs().mean(), # MAE
    'x_rmse': np.sqrt((df['error_x']**2).mean()),
    'y_rmse': np.sqrt((df['error_y']**2).mean())
}

print("-" * 30)
print("ANÁLISIS DE PRECISIÓN REAL (X/Y)")
print("-" * 30)
print(f"Ground Truth: X={gt_x}, Y={gt_y}")
print(f"Muestras: {len(df)}")
print("-" * 30)
print(f"EJE X:")
print(f"  Promedio Medido: {stats['x_mean']:.4f} m")
print(f"  Desviación Estándar (Jitter/Ruido): {stats['x_std']*100:.2f} cm")
print(f"  Error Medio (Bias/Offset): {stats['x_error_mean']*100:.2f} cm")
print(f"  Error Absoluto Medio (MAE): {stats['x_error_abs_mean']*100:.2f} cm")
print(f"  RMSE (Error Total): {stats['x_rmse']*100:.2f} cm")
print("-" * 30)
print(f"EJE Y:")
print(f"  Promedio Medido: {stats['y_mean']:.4f} m")
print(f"  Desviación Estándar (Jitter/Ruido): {stats['y_std']*100:.2f} cm")
print(f"  Error Medio (Bias/Offset): {stats['y_error_mean']*100:.2f} cm")
print(f"  Error Absoluto Medio (MAE): {stats['y_error_abs_mean']*100:.2f} cm")
print(f"  RMSE (Error Total): {stats['y_rmse']*100:.2f} cm")
print("-" * 30)
