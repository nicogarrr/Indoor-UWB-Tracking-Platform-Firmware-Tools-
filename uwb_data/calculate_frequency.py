import pandas as pd
import numpy as np

# Configuración
file_path = "uwb_positions_20251128_132508.csv"

# Load data
df = pd.read_csv(file_path)

# Calculate differences in device_timestamp (ms)
# Filter out 0 or duplicate timestamps if any
df = df[df['device_timestamp'] > 0]
df = df.sort_values('device_timestamp')
diffs = df['device_timestamp'].diff().dropna()

# Remove large gaps (e.g., > 1000ms) which might indicate packet loss or restart
diffs = diffs[diffs < 1000]

# Calculate statistics
mean_diff = diffs.mean()
std_diff = diffs.std()
frequency = 1000 / mean_diff if mean_diff > 0 else 0

print("-" * 30)
print("ANÁLISIS DE FRECUENCIA")
print("-" * 30)
print(f"Archivo: {file_path}")
print(f"Muestras: {len(df)}")
print(f"Intervalo Promedio: {mean_diff:.2f} ms")
print(f"Desviación Estándar: {std_diff:.2f} ms")
print(f"Frecuencia Calculada: {frequency:.2f} Hz")
print("-" * 30)
