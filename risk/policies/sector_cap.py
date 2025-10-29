# -*- coding: utf-8 -*-
# risk/policies/sector_cap.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import BasePolicy, PolicyResult

@dataclass
class SectorParams:
    sector_cap_pct: float = 0.40   # 섹터별 최대 노출
    budget: float = 10_000_000.0

class SectorCapPolicy(BasePolicy):
    """
    ctx 필요 키:
      - "symbol_sector": Dict[str, str]    # 예: {"005930": "IT", ...}
      - "sector_exposure": Dict[str, float]# 섹터별 현재 노출 금액(없으면 0)
    """
    def __init__(self, params: Optional[SectorParams] = None):
        self.p = params or SectorParams()

    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        sector_map: Dict[str, str] = ctx.get("symbol_sector", {}) or {}
        sector = sector_map.get(symbol)
        if not sector:
            return PolicyResult(True)  # 섹터 정보 없으면 통과
        sector_exp: Dict[str, float] = ctx.get("sector_exposure", {}) or {}
        budget = float(ctx.get("budget") or self.p.budget)
        cap = budget * self.p.sector_cap_pct
        if float(sector_exp.get(sector, 0.0)) >= cap:
            return PolicyResult(False, f"sector_cap:{sector}")
        return PolicyResult(True)
