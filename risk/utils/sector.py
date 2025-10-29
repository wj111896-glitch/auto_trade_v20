# -*- coding: utf-8 -*-
"""
risk/utils/sector.py
- 심볼→섹터 매핑 로드/확인
- 포트폴리오 섹터별 노출액 집계 (보수적/현재가 기준)
"""
from __future__ import annotations
from typing import Dict, Any, Optional, Iterable
import csv
import os

Symbol = str
Sector = str

# ====== 섹터 맵 로드/유틸 ======

def load_sector_map(path: str, symbol_col: str = "symbol", sector_col: str = "sector") -> Dict[Symbol, Sector]:
    """
    CSV에서 심볼→섹터 매핑 로드.
    - 첫 행 헤더 필요. 기본 컬럼명: symbol, sector
    - 예시:
        symbol,sector
        005930,IT
        000660,IT
        035420,Internet
    """
    if not path or not os.path.exists(path):
        return {}
    out: Dict[Symbol, Sector] = {}
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            sym = str(row.get(symbol_col, "")).strip()
            sec = str(row.get(sector_col, "")).strip()
            if sym and sec:
                out[sym] = sec
    return out


def get_sector(symbol: Symbol, sector_map: Dict[Symbol, Sector], default: Sector = "UNKNOWN") -> Sector:
    return sector_map.get(symbol, default)


# ====== 섹터 노출액 집계 ======

def compute_sector_exposure(
    portfolio: Dict[Symbol, Dict[str, Any]],
    live_prices: Optional[Dict[Symbol, float]] = None,
    mode: str = "conservative",
) -> Dict[Sector, float]:
    """
    섹터별 노출액 집계.
    - portfolio 형식: {sym: {"qty": float, "avg_px": float}, ...}
    - live_prices: 현재가(없으면 avg_px만 사용)
    - mode:
        * 'conservative' → max(avg_px, live_price) * qty (더 보수적으로 큰 값 사용)
        * 'live'         → (live_price or avg_px) * qty
        * 'avg'          → avg_px * qty
    반환: {sector: exposure_value}
    """
    sector_map: Dict[Symbol, Sector] = portfolio.get("_sector_map__", {}) or {}
    out: Dict[Sector, float] = {}

    for sym, pos in portfolio.items():
        if sym.startswith("_"):
            continue
        qty = float(pos.get("qty", 0.0) or 0.0)
        if qty <= 0:
            continue
        avg = float(pos.get("avg_px", 0.0) or 0.0)
        live = None if live_prices is None else live_prices.get(sym)
        if mode == "conservative":
            base = max(avg, (live if live is not None else 0.0))
            if live is None:
                base = avg  # 라이브가 없으면 avg 사용
        elif mode == "live":
            base = (live if live is not None else avg)
        else:  # 'avg'
            base = avg
        exposure = qty * float(base)
        sec = get_sector(sym, sector_map, default="UNKNOWN")
        out[sec] = out.get(sec, 0.0) + exposure

    return out


def attach_sector_map_to_portfolio(
    portfolio: Dict[Symbol, Dict[str, Any]],
    sector_map: Dict[Symbol, Sector],
) -> Dict[Symbol, Dict[str, Any]]:
    """
    포트폴리오 dict에 섹터맵 메타를 동봉해서 compute_sector_exposure()가 사용 가능하도록 함.
    - 부작용 없이 사본 반환
    """
    new_pf = dict(portfolio)
    new_pf["_sector_map__"] = dict(sector_map)
    return new_pf


# ====== 요약/출력 헬퍼 ======

def summarize_by_sector(sector_exposure: Dict[Sector, float]) -> str:
    """
    간단 문자열 요약(로그용)
    """
    if not sector_exposure:
        return "(no exposure)"
    parts = [f"{sec}:{val:,.0f}" for sec, val in sorted(sector_exposure.items(), key=lambda x: -x[1])]
    return " | ".join(parts)
