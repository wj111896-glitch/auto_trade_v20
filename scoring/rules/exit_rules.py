# -*- coding: utf-8 -*-
"""
통합 익절·손절·트레일링 스탑 엔진
- 개별 룰(TP/SL/Trailing)을 하나의 인터페이스로 묶음
- Hub 또는 RiskGate에서 쉽게 호출 가능
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ExitParams:
    """익절/손절/트레일링 스탑 파라미터"""
    tp_pct: float = 0.012      # +1.2%
    sl_pct: float = -0.008     # -0.8%
    trailing_pct: float = 0.006  # +0.6% 후 트레일링
    min_hold_ticks: int = 3      # 최소 홀드틱 (너무 짧게 자르지 않게)
    cooldown_ticks: int = 5      # 재진입 방지 쿨다운


@dataclass
class ExitResult:
    """룰 평가 결과"""
    exit: bool
    reason: str = ""
    pnl_pct: Optional[float] = None


class ExitRules:
    """
    ExitRule 통합 엔진.
    가격·틱 흐름 기반으로 익절/손절/트레일링 판단.
    """
    def __init__(self, params: Optional[ExitParams] = None):
        self.p = params or ExitParams()
        self.highest_since_entry: Dict[str, float] = {}
        self.hold_ticks: Dict[str, int] = {}

    def _pnl_pct(self, entry: float, now: float) -> float:
        return (now / entry - 1.0) if entry else 0.0

    def apply_exit(self, symbol: str, entry_price: float, current_price: float, ctx: Dict[str, Any]) -> ExitResult:
        p = self.p
        pnl = self._pnl_pct(entry_price, current_price)
        ticks = self.hold_ticks.get(symbol, 0) + 1
        self.hold_ticks[symbol] = ticks

        # 최소 보유틱 미만이면 강제 보류
        if ticks < p.min_hold_ticks:
            return ExitResult(False, reason=f"hold_too_short:{ticks}")

        # 최고가 갱신
        prev_high = self.highest_since_entry.get(symbol, entry_price)
        new_high = max(prev_high, current_price)
        self.highest_since_entry[symbol] = new_high

        # === 익절 ===
        if pnl >= p.tp_pct:
            return ExitResult(True, reason=f"take_profit:{pnl:.2%}", pnl_pct=pnl)

        # === 손절 ===
        if pnl <= p.sl_pct:
            return ExitResult(True, reason=f"stop_loss:{pnl:.2%}", pnl_pct=pnl)

        # === 트레일링 ===
        drawdown_from_high = (current_price / new_high - 1.0)
        if pnl > 0 and drawdown_from_high <= -p.trailing_pct:
            return ExitResult(True, reason=f"trailing_stop:{drawdown_from_high:.2%}", pnl_pct=pnl)

        return ExitResult(False, reason="hold", pnl_pct=pnl)
