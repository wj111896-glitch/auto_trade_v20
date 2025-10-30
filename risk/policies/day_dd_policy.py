# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

from .base import BasePolicy, PolicyResult

@dataclass
class DayDDParams:
    limit_pct: float = -2.0
    soft_pct: float = -1.0
    cool_minutes: int = 15
    scale_min: float = 0.4

class DayDrawdownPolicy(BasePolicy):
    def __init__(self, params: Optional[DayDDParams] = None):
        self.p = params or DayDDParams()

    def _now(self, ctx: Dict[str, Any]) -> float:
        try:
            return float(ctx.get("now_ts") or time.time())
        except Exception:
            return time.time()

    def _pnl_pct(self, ctx: Dict[str, Any]) -> float:
        eq = ctx.get("equity_now"); day0 = ctx.get("day_start_equity")
        if isinstance(eq, (int, float)) and isinstance(day0, (int, float)) and float(day0) > 0:
            try:
                return (float(eq) / float(day0) - 1.0) * 100.0
            except Exception:
                pass
        try:
            return float(ctx.get("today_pnl_pct") or 0.0)
        except Exception:
            return 0.0

    def _scale_for(self, pnl_pct: float) -> float:
        p = self.p
        if pnl_pct <= p.limit_pct: return 0.0
        if pnl_pct >= p.soft_pct: return 1.0
        t = (pnl_pct - p.limit_pct) / max(1e-9, (p.soft_pct - p.limit_pct))
        scaled = p.scale_min + t * (1.0 - p.scale_min)
        return max(p.scale_min, min(1.0, float(scaled)))

    def check_entry(self, symbol: str, price: float,
                    portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        p = self.p
        pnl = float(self._pnl_pct(ctx))
        now = self._now(ctx)
        block_until = float(ctx.get("dd_block_until_ts") or 0.0)

        if pnl <= p.limit_pct:
            until = now + p.cool_minutes * 60
            ctx["dd_block_until_ts"] = until
            return PolicyResult(False, f"daydd_hard({pnl:.3f}%)")

        if now < block_until:
            left = int(block_until - now)
            return PolicyResult(False, f"daydd_cooldown({left}s)")

        if pnl <= p.soft_pct:
            return PolicyResult(True, f"daydd_soft({pnl:.3f}%)")

        return PolicyResult(True, "ok")

    def size_hint(self, symbol: str, price: float,
                  portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        if "planned_qty" not in ctx:
            return None
        planned = int(ctx.get("planned_qty") or 0)
        if planned <= 0:
            return 0
        pnl = float(self._pnl_pct(ctx))
        scale = self._scale_for(pnl)
        return max(0, int(planned * scale))
