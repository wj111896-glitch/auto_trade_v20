# -*- coding: utf-8 -*-
# risk/policies/throttle.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import BasePolicy, PolicyResult

@dataclass
class ThrottleParams:
    cool_ticks: int = 3  # 심볼별 쿨다운 틱 수(허브에서 관리해도 되지만 예시로 제공)

class ThrottlePolicy(BasePolicy):
    """
    ctx 필요 키:
      - "symbol_cool": Dict[str, int]  # 남은 쿨다운 틱
    """
    def __init__(self, params: Optional[ThrottleParams] = None):
        self.p = params or ThrottleParams()

    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        cool = (ctx.get("symbol_cool") or {}).get(symbol, 0)
        if int(cool) > 0:
            return PolicyResult(False, "cooldown")
        return PolicyResult(True)
