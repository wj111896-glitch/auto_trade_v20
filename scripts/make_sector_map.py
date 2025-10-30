# -*- coding: utf-8 -*-
"""
pandas/NumPy 없이 sector_map.csv 생성 (엑셀 호환 UTF-8 BOM)
"""
import os, csv, io

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)

rows = [
    ["symbol", "sector"],
    ["005930", "전자"],
    ["000660", "반도체"],
    ["035420", "인터넷"],
]

path = os.path.join(data_dir, "sector_map.csv")

# UTF-8 with BOM으로 저장 (엑셀에서 한글/0-패딩 유지)
with open(path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print(f"[OK] sector_map.csv 생성 완료 → {path}")
