#!/usr/bin/env python3
"""
🔧 UWB Replay Processor
-----------------------
Limpia y normaliza ficheros CSV producidos por `mqtt_to_csv_collector.py` / `log_receiver_opt.py`.

Funcionalidades principales
1. Elimina duplicados exactos (timestamp + resto de columnas).
2. Filtra filas con distancias nulas o menores que un umbral (default 50 cm).
3. Opcionalmente remuestrea a intervalos fijos (default 500 ms) interpolando posiciones.
4. Guarda un CSV limpio en `processed_data/` (o la ruta indicada).

Uso rápido
----------
Procesar un único archivo:
    python uwb_replay_processor.py --input uwb_replay_csv/uwb_replay_20250627_131955.csv

Procesar todos los CSV de una carpeta:
    python uwb_replay_processor.py --input uwb_replay_csv --resample --freq 400ms
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def discover_csvs(path: Path) -> List[Path]:
    """Devuelve lista de ficheros CSV dentro de un path (archivo o carpeta)."""
    if path.is_file() and path.suffix.lower() == ".csv":
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.csv"))
    raise FileNotFoundError(f"Ruta no válida: {path}")


def clean_dataframe(df: pd.DataFrame, dist_threshold: float = 50.0) -> pd.DataFrame:
    """Limpia duplicados y distancias inválidas."""
    initial_rows = len(df)
    # 1. Eliminar duplicados exactos
    df = df.drop_duplicates()

    # 2. Filtrar distancias <= threshold
    dist_cols = [c for c in df.columns if c.endswith("_dist")]
    mask_valid = df[dist_cols].gt(dist_threshold).all(axis=1)
    df = df[mask_valid]

    removed = initial_rows - len(df)
    return df, removed


def resample_dataframe(df: pd.DataFrame, freq: str = "500ms") -> pd.DataFrame:
    """Ajusta el DataFrame a una frecuencia fija usando primer valor + interpolación lineal."""
    df = df.copy()
    df.index = pd.to_datetime(df["timestamp"])
    df = df.sort_index()

    # Re-muestreo, manteniendo la primera observación del intervalo y
    # luego interpolando valores numéricos faltantes.
    df_res = df.resample(freq).first()
    df_res[df_res.select_dtypes(float).columns] = df_res.select_dtypes(float).interpolate()
    df_res["tag_id"] = df_res["tag_id"].ffill()

    # Restaurar índice numérico
    df_res = df_res.reset_index()
    return df_res


# --------------------------------------------------
# CLI
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Limpia y normaliza CSVs UWB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Archivo CSV o carpeta que contiene CSVs")
    parser.add_argument("--output-dir", default="processed_data", help="Directorio destino para CSVs limpios")
    parser.add_argument("--dist-threshold", type=float, default=50.0, help="Umbral mín. para distancias válidas (cm)")
    parser.add_argument("--resample", action="store_true", help="Re-muestrear a frecuencia fija")
    parser.add_argument("--freq", default="500ms", help="Frecuencia de remuestreo (ej. '500ms', '1s')")

    args = parser.parse_args()

    input_path = Path(args.input)
    csv_paths = discover_csvs(input_path)

    os.makedirs(args.output_dir, exist_ok=True)

    for csv_path in csv_paths:
        print(f"\n📂 Procesando {csv_path} …")
        df = pd.read_csv(csv_path)

        cleaned_df, removed = clean_dataframe(df, args.dist_threshold)
        print(f"   • Filas iniciales: {len(df):,} → tras limpieza: {len(cleaned_df):,} (−{removed})")

        if args.resample:
            cleaned_df = resample_dataframe(cleaned_df, args.freq)
            print(f"   • Tras remuestreo '{args.freq}': {len(cleaned_df):,} filas")

        out_name = csv_path.stem + "_cleaned.csv"
        out_path = Path(args.output_dir) / out_name
        cleaned_df.to_csv(out_path, index=False)
        print(f"✅ Guardado → {out_path}")


if __name__ == "__main__":
    main() 