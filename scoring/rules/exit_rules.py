# -*- coding: utf-8 -*-
"""
통합 익절·손절·트레일링 스탑 엔진 (HubTrade 루프 통합 대응판)
- 개별 룰(TP/SL/Trailing) 통합
- 배치 API: apply_exit_batch(portfolio, ctx) → [{symbol, qty, price, reason}]
- 쿨다운/최고가/보유틱 상태 관리
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ExitParams:
    """익절/손절/트레일링 스탑 파라미터"""
    tp_pct: float = 0.012         # +1.2%
    sl_pct: float = -0.008        # -0.8%
    trailing_pct: float = 0.006   # 최고가 대비 -0.6% 이탈 시
    min_hold_ticks: int = 3       # 최소 홀드틱 (너무 짧게 자르지 않게)
    cooldown_ticks: int = 5       # 재진입 방지 쿨다운 (틱 기준)


@dataclass
class ExitResult:
    """단일 심볼 룰 평가 결과 (단일 API 호환용)"""
    exit: bool
    reason: str = ""
    pnl_pct: Optional[float] = None


class ExitRules:
    """
    ExitRule 통합 엔진.
    가격·틱 흐름 기반으로 익절/손절/트레일링 판단.

    호환되는 배치 입력 포맷 (HubTrade에서 전달):
        portfolio = {
          "AAA": {"qty": 100, "avg_price": 100.0, "last_high": 104.0, "price_now": 102.5},
          ...
        }
        ctx = {
          "pnl_open_pct": {"AAA": 0.025, ...},  # 선택(없으면 내부 계산)
          "tick_index": 123,                    # 현재 틱
          ...                                   # 기타 컨텍스트
        }

    반환:
        [{"symbol":"AAA","qty":100,"price":102.5,"reason":"take_profit"}, ...]
    """
    def __init__(self, params: Optional[ExitParams] = None):
        self.p = params or ExitParams()
        self.highest_since_entry: Dict[str, float] = {}
        self.hold_ticks: Dict[str, int] = {}
        self.cooldown_until_tick: Dict[str, int] = {}  # 심볼별 재진입 금지 종료 틱

    # ---------- 상태 훅(선택) ----------
    def on_entry_fill(self, symbol: str, entry_price: float, tick_index: int) -> None:
        """새 진입 체결 시 상태 초기화 (허브에서 호출해주면 더 정확)"""
        self.highest_since_entry[symbol] = entry_price
        self.hold_ticks[symbol] = 0
        # 진입 순간에는 쿨다운 없음
        self.cooldown_until_tick.pop(symbol, None)

    def on_exit_fill(self, symbol: str, tick_index: int) -> None:
        """청산 체결 시 쿨다운 시작"""
        self.highest_since_entry.pop(symbol, None)
        self.hold_ticks.pop(symbol, None)
        self.cooldown_until_tick[symbol] = tick_index + self.p.cooldown_ticks

    # ---------- 내부 유틸 ----------
    @staticmethod
    def _pnl_pct(entry: float, now: float) -> float:
        return (now / entry - 1.0) if entry else 0.0

    # ---------- 단일 심볼 API (기존 호환용) ----------
    def apply_exit(self, symbol: str, entry_price: float, current_price: float, ctx: Dict[str, Any]) -> ExitResult:
        p = self.p
        tick_idx = int(ctx.get("tick_index", 0))
        ticks = self.hold_ticks.get(symbol, 0) + 1
        self.hold_ticks[symbol] = ticks

        # 최소 보유틱 미만이면 보류
        if ticks < p.min_hold_ticks:
            return ExitResult(False, reason=f"hold_too_short:{ticks}")

        # 최고가 갱신
        prev_high = self.highest_since_entry.get(symbol, entry_price)
        new_high = max(prev_high, current_price)
        self.highest_since_entry[symbol] = new_high

        pnl = self._pnl_pct(entry_price, current_price)

        # ① 익절
        if pnl >= p.tp_pct:
            return ExitResult(True, reason="take_profit", pnl_pct=pnl)

        # ② 손절
        if pnl <= p.sl_pct:
            return ExitResult(True, reason="stop_loss", pnl_pct=pnl)

        # ③ 트레일링
        drawdown_from_high = (current_price / new_high - 1.0)
        if pnl > 0 and drawdown_from_high <= -p.trailing_pct:
            return ExitResult(True, reason="trailing_stop", pnl_pct=pnl)

        return ExitResult(False, reason="hold", pnl_pct=pnl)

    # ---------- 배치 API (HubTrade 전용) ----------
    def apply_exit_batch(self, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> List[dict]:
        """
        HubTrade가 사용하는 표준 배치 API.
        portfolio/ctx를 받아 청산 주문 리스트를 반환한다.
        """
        p = self.p
        results: List[dict] = []

        pnl_ctx: Dict[str, float] = ctx.get("pnl_open_pct", {}) or {}
        tick_idx: int = int(ctx.get("tick_index", 0))

        for sym, pos in portfolio.items():
            qty = int(pos.get("qty", 0) or 0)
            if qty <= 0:
                continue

            price_now = pos.get("price_now")
            avg_price = pos.get("avg_price")
            if not price_now or not avg_price:
                continue

            # 보유틱
            ticks = self.hold_ticks.get(sym, 0) + 1
            self.hold_ticks[sym] = ticks

            # 최소 보유틱
            if ticks < p.min_hold_ticks:
                continue

            # 최고가 갱신 (입력에 last_high가 있으면 우선)
            prev_high = self.highest_since_entry.get(sym, avg_price)
            last_high = pos.get("last_high", prev_high)
            new_high = max(prev_high, last_high, price_now)
            self.highest_since_entry[sym] = new_high

            # 손익률
            pnl_now = pnl_ctx.get(sym)
            if pnl_now is None:
                pnl_now = self._pnl_pct(avg_price, price_now)

            # 룰 판단
            reason: Optional[str] = None

            if pnl_now >= p.tp_pct:
                reason = "take_profit"
            elif pnl_now <= p.sl_pct:
                reason = "stop_loss"
            else:
                drawdown_from_high = (price_now / new_high - 1.0)
                if pnl_now > 0 and drawdown_from_high <= -p.trailing_pct:
                    reason = "trailing_stop"

            if reason:
                # 청산 결정
                results.append({
                    "symbol": sym,
                    "qty": qty,
                    "price": float(price_now),
                    "reason": reason,
                })
                # 쿨다운 시작 및 상태 리셋
                self.on_exit_fill(sym, tick_idx)

        return results

    # ---------- 보조: 재진입 가능 여부(선택) ----------
    def can_reenter(self, symbol: str, tick_index: int) -> bool:
        """허브에서 신규 진입 전에 호출하면 쿨다운 존중 가능 (선택)"""
        until = self.cooldown_until_tick.get(symbol)
        return True if until is None else (tick_index >= until)
