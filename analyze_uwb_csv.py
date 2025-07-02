#!/usr/bin/env python3
"""Analizador UWB Positions + Ranging
Uso: python analyze_uwb_csv.py new_positions.csv new_ranging.csv [old_positions.csv]
"""
import sys, os, pandas as pd
from datetime import datetime

def analyze_positions(csv):
    df = pd.read_csv(csv)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    samples=len(df)
    duration=(df['timestamp'].iloc[-1]-df['timestamp'].iloc[0]).total_seconds()
    freq=samples/duration if duration>0 else 0
    gaps=df['timestamp'].diff().dt.total_seconds()*1000
    gaps=gaps[1:]
    return {
        'samples':samples,'duration':duration,'freq':freq,
        'gap_avg':gaps.mean(),'gap_max':gaps.max(),
        'gap_bad':(gaps>200).sum()/len(gaps)*100
    }

def analyze_ranging(csv):
    df=pd.read_csv(csv)
    if 'Timestamp_ms' in df.columns:
        start,end=df['Timestamp_ms'].min(),df['Timestamp_ms'].max()
        duration=(end-start)/1000
        freq=len(df)/duration if duration>0 else 0
        return {'samples':len(df),'duration':duration,'freq':freq}
    return None

def print_stats(label,d):
    print(f"\n{label}:")
    for k,v in d.items():
        print(f"  {k}: {v:.2f}" if isinstance(v,float) else f"  {k}: {v}")

def main():
    if len(sys.argv)<3:
        print("Uso: python analyze_uwb_csv.py new_pos.csv new_rang.csv [old_pos.csv]");return
    new_pos, new_rang=sys.argv[1],sys.argv[2]
    old_pos=sys.argv[3] if len(sys.argv)>3 else None
    newp=analyze_positions(new_pos)
    newr=analyze_ranging(new_rang)
    print_stats('NUEVOS POS',newp)
    print_stats('NUEVO RANGING',newr)
    if old_pos:
        old=analyze_positions(old_pos)
        print_stats('ANTERIOR POS',old)
        print(f"\nΔ frecuencia posiciones: {(newp['freq']-old['freq']):.2f} Hz")
        print(f"Δ gap_max: {old['gap_max']-newp['gap_max']:.0f} ms")

if __name__=='__main__':
    main() 