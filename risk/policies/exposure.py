# -*- coding: utf-8 -*-
# risk/policies/exposure.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import BasePolicy, PolicyResult

@dataclass
class ExposureParams:
    max_total_exposure_pct: float = 0.70   # 총자산 대비 보유 한도
    per_symbol_cap_pct: float = 0.30       # 심볼당 한도
    min_order_value: int = 50_000          # 최소 주문금액
    lot_size: int = 1                      # 수량 라운딩
    budget: float = 10_000_000.0           # 기본 예산 (ctx에서 override 가능)

class ExposurePolicy(BasePolicy):
    def __init__(self, params: Optional[ExposureParams] = None):
        self.p = params or ExposureParams()

    def _pf_value(self, pf: Dict[str, dict]) -> float:
        return sum(float(v.get("qty",0))*float(v.get("avg_px",0)) for v in pf.values())

    def _sym_value(self, pf: Dict[str, dict], sym: str, live_px: float) -> float:
        pos = pf.get(sym)
        if not pos: return 0.0
        qty = float(pos.get("qty",0))
        avg = float(pos.get("avg_px",0))
        base = max(avg, live_px)  # 보수적(더 큰 값 기준)
        return qty * base

    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        budget = float(ctx.get("budget") or self.p.budget)
        max_total = budget * self.p.max_total_exposure_pct
        max_symbol = budget * self.p.per_symbol_cap_pct
        tot_val = self._pf_value(portfolio)
        sym_val = self._sym_value(portfolio, symbol, price)
        if tot_val >= max_total:
            return PolicyResult(False, "total_exposure_cap")
        if sym_val >= max_symbol:
            return PolicyResult(False, "per_symbol_cap")
        return PolicyResult(True)

    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        if price <= 0:
            return 0
        p = self.p
        qty = max(0, p.min_order_value // int(price))
        qty = (qty // p.lot_size) * p.lot_size
        return max(qty, p.lot_size if p.min_order_value <= price else 0)
