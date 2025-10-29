# -*- coding: utf-8 -*-
"""
risk/core.py — RiskGate (policies orchestrator, relaxed defaults)
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from obs.log import get_logger
except Exception:
    class _L:
        def info(self, *a, **k): print("[INFO]", *a)
        def warning(self, *a, **k): print("[WARN]", *a)
        def error(self, *a, **k): print("[ERROR]", *a)
    def get_logger(name): return _L()

try:
    from common import config
    _BUDGET = float(getattr(config, "BUDGET", 0.0) or 0.0)
except Exception:
    _BUDGET = 0.0

# 정책들
from .policies.base import Policy, PolicyResult
from .policies.exposure import ExposurePolicy, ExposureParams
from .policies.day_dd import DayDrawdownPolicy, DayDDParams
# 필요 시 옵션 정책 추가:
# from .policies.sector_cap import SectorCapPolicy, SectorParams
# from .policies.throttle import ThrottlePolicy, ThrottleParams

@dataclass
class RiskContext:
    budget: float = 10_000_000.0
    today_pnl_pct: float = 0.0
    now_ts: float = 0.0
    dd_block_until_ts: float = 0.0
    symbol_sector: Optional[Dict[str, str]] = None
    sector_exposure: Optional[Dict[str, float]] = None
    symbol_cool: Optional[Dict[str, int]] = None

class RiskGate:
    """
    새 API:
      - allow_entry(symbol, portfolio, price, ctx=None) -> bool
      - size_for(symbol, price, portfolio, ctx=None) -> int

    레거시:
      - apply(score, snapshot) -> decision(dict)
    """

    def __init__(self, policies: Optional[List[Policy]] = None, budget: Optional[float] = None):
        self.log = get_logger("risk")
        self.budget = float(budget or _BUDGET or 10_000_000.0)
        # 기본 정책 조합(완화형)
        if policies is None:
            policies = [
                ExposurePolicy(ExposureParams(budget=self.budget)),
                DayDrawdownPolicy(DayDDParams(max_dd_pct=-5.0, cool_minutes=15)),
                # 필요시 아래 주석해제:
                # SectorCapPolicy(SectorParams(sector_cap_pct=0.40, budget=self.budget)),
                # ThrottlePolicy(ThrottleParams(cool_ticks=3)),
            ]
        self.policies = policies

    # ---------- 유틸 ----------
    def _merge_ctx(self, ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        out = dict(ctx or {})
        out.setdefault("budget", self.budget)
        return out

    # ---------- 새 API ----------
    def allow_entry(self, symbol: str, portfolio: Dict[str, dict], price: float, ctx: Optional[Dict[str, Any]] = None) -> bool:
        cx = self._merge_ctx(ctx)
        for pol in self.policies:
            r: PolicyResult = pol.check_entry(symbol, price, portfolio, cx)
            if not r.allow:
                self.log.warning(f"[RISK] block by {pol.__class__.__name__}: {r.reason}")
                return False
        return True

    def size_for(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Optional[Dict[str, Any]] = None) -> int:
        cx = self._merge_ctx(ctx)
        hints: List[int] = []
        for pol in self.policies:
            h = pol.size_hint(symbol, price, portfolio, cx)
            if h is not None:
                hints.append(int(h))
        return max(0, min(hints) if hints else 0)

    # ---------- 레거시 ----------
    def apply(self, score: float, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sym = str(snapshot.get("symbol", "NA"))
        price = float(snapshot.get("price", 0.0) or 0.0)
        pf = snapshot.get("_portfolio", {})  # 허브에서 전달 안 하면 빈 dict
        if score > 0:
            if self.allow_entry(sym, pf, price):
                qty = self.size_for(sym, price, pf)
                if qty > 0:
                    return {"action": "BUY", "symbol": sym, "qty": int(qty), "order_type": "MKT", "price": None, "tag": "risk-legacy"}
        elif score < 0:
            pos = pf.get(sym)
            if pos and int(pos.get("qty", 0)) > 0:
                return {"action": "SELL", "symbol": sym, "qty": 1, "order_type": "MKT", "price": None, "tag": "risk-legacy"}
        return {"action": "HOLD", "symbol": sym, "qty": 0}

