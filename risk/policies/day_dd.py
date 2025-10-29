# -*- coding: utf-8 -*-
# risk/policies/day_dd.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import BasePolicy, PolicyResult

@dataclass
class DayDDParams:
    max_dd_pct: float = -5.0  # 일중 손익률 이 값 이하이면 차단
    cool_minutes: int = 15    # 차단 유지 시간(분)

class DayDrawdownPolicy(BasePolicy):
    """
    ctx 에서 사용하는 키:
      - "today_pnl_pct": float (일중 손익률, %)
      - "now_ts": float (epoch seconds)
      - "dd_block_until_ts": float (차단 해제 시각)
    """
    def __init__(self, params: Optional[DayDDParams] = None):
        self.p = params or DayDDParams()

    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        pnl = float(ctx.get("today_pnl_pct") or 0.0)
        now = float(ctx.get("now_ts") or 0.0)
        block_until = float(ctx.get("dd_block_until_ts") or 0.0)
        # 손실컷 발동
        if pnl <= self.p.max_dd_pct:
            until = now + self.p.cool_minutes * 60
            if until > block_until:
                ctx["dd_block_until_ts"] = until
            return PolicyResult(False, "day_drawdown_cut")
        # 쿨다운 유지
        if now < block_until:
            return PolicyResult(False, "dd_cooldown")
        return PolicyResult(True)
