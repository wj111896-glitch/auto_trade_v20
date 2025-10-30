# -*- coding: utf-8 -*-
"""
utils/sector_map.py
- sector_map.csv(UTF-8 BOM 권장) 를 읽어 심볼→섹터 매핑 함수 제공
- Excel이 0패딩을 지워도 dtype=str 로 복구
"""
from __future__ import annotations
from typing import Callable, Dict, Optional
import csv
import os

def load_sector_map(csv_path: str) -> Dict[str, str]:
    """
    CSV 포맷:
      symbol,sector
      005930,전자
      000660,반도체
      035420,인터넷
    """
    m: Dict[str, str] = {}
    if not os.path.exists(csv_path):
        return m

    # UTF-8 BOM 우선, 실패하면 CP949 폴백
    encodings = ["utf-8-sig", "cp949"]
    for enc in encodings:
        try:
            with open(csv_path, "r", encoding=enc, newline="") as f:
                rdr = csv.DictReader(f)
                for row in rdr:
                    sym = str(row.get("symbol", "")).strip()
                    sec = str(row.get("sector", "")).strip()
                    # 숫자로 열렸던 걸 복구: (5930 → 005930) 같은 상황 방지용
                    if sym.isdigit() and len(sym) < 6:
                        sym = sym.zfill(6)
                    if sym:
                        m[sym] = sec or "UNKNOWN"
            break
        except Exception:
            continue
    return m

def make_sector_of(map_dict: Dict[str, str]) -> Callable[[str], Optional[str]]:
    def sector_of(symbol: str) -> Optional[str]:
        if not symbol:
            return None
        s = str(symbol).strip()
        if s.isdigit() and len(s) < 6:
            s = s.zfill(6)
        return map_dict.get(s)
    return sector_of

# 편의 함수: 경로만 넣으면 sector_of 콜러블 바로 리턴
def get_sector_of(csv_path: str) -> Callable[[str], Optional[str]]:
    return make_sector_of(load_sector_map(csv_path))
