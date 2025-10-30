# -*- coding: utf-8 -*-
# risk/policies/day_dd.py
"""
DayDrawdownPolicy — 일중 손실(%) 기반 진입 차단/쿨다운/스케일다운
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

from .base import BasePolicy, PolicyResult


@dataclass
class DayDDParams:
    limit_pct: float = -2.0      # 이하면 하드 차단 (%)
    soft_pct: float  = -1.0      # 이하면 축소 진입  (%)
    cool_minutes: int = 15       # 하드 차단 유지 시간(분)
    scale_min: float = 0.3       # soft~limit 구간 최소 스케일(0~1)


class DayDrawdownPolicy(BasePolicy):
    def __init__(self, params: Optional[DayDDParams] = None, **kwargs):
        """
        RiskGate가 limit_pct, soft_pct, scale_min, cool_minutes, use_unrealized
        같은 키워드를 직접 넘겨도 받도록 허용.
        """
        p = params or DayDDParams()
        # 키워드로 들어온 값이 있으면 덮어쓰기
        if "limit_pct" in kwargs:   p.limit_pct   = float(kwargs["limit_pct"])
        if "soft_pct" in kwargs:    p.soft_pct    = float(kwargs["soft_pct"])
        if "scale_min" in kwargs:   p.scale_min   = float(kwargs["scale_min"])
        if "cool_minutes" in kwargs: p.cool_minutes = int(kwargs["cool_minutes"])
        # use_unrealized는 본 정책에선 미사용이지만 에러 방지를 위해 받아만 둠
        self._ignore_use_unrealized = kwargs.get("use_unrealized", None)
        self.p = p

    # ---- 내부 유틸 ----
    def _now(self, ctx: Dict[str, Any]) -> float:
        try:
            return float(ctx.get("now_ts") or time.time())
        except Exception:
            return time.time()

    def _pnl_pct(self, ctx: Dict[str, Any]) -> float:
        """ctx에서 일중 손익률(%) 계산 또는 사용."""
        eq   = ctx.get("equity_now")
        day0 = ctx.get("day_start_equity")
        # equity 기반 계산 우선
        if isinstance(eq, (int, float)) and isinstance(day0, (int, float)) and float(day0) > 0:
            try:
                return (float(eq) / float(day0) - 1.0) * 100.0
            except Exception:
                pass
        # 직접 제공 퍼센트가 있으면 사용
        try:
            return float(ctx.get("today_pnl_pct") or 0.0)
        except Exception:
            return 0.0

    def _scale_for(self, pnl_pct: float) -> float:
        """soft~limit 사이에서 선형 보간으로 스케일 계산."""
        p = self.p
        if pnl_pct <= p.limit_pct: return 0.0
        if pnl_pct >= p.soft_pct:  return 1.0
        t = (pnl_pct - p.limit_pct) / max(1e-9, (p.soft_pct - p.limit_pct))
        scaled = p.scale_min + t * (1.0 - p.scale_min)
        return max(p.scale_min, min(1.0, float(scaled)))

    # ---- 정책 본체 ----
    def check_entry(self, symbol: str, price: float,
                    portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        p   = self.p
        pnl = float(self._pnl_pct(ctx))
        now = self._now(ctx)
        block_until = float(ctx.get("dd_block_until_ts") or 0.0)

        # ① 하드 차단
        if pnl <= p.limit_pct:
            until = now + p.cool_minutes * 60
            if until > block_until:
                ctx["dd_block_until_ts"] = until
            return PolicyResult(False, f"daydd_hard({pnl:.3f}%)")

        # ② 쿨다운 유지
        if now < block_until:
            left = int(block_until - now)
            return PolicyResult(False, f"daydd_cooldown({left}s)")

        # ③ 소프트 구간
        if pnl <= p.soft_pct:
            return PolicyResult(True, f"daydd_soft({pnl:.3f}%)")

        # ④ 정상
        return PolicyResult(True, "ok")

    def size_hint(self, symbol: str, price: float,
                  portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        """planned_qty가 있을 때만 축소 수량 반환."""
        if "planned_qty" not in ctx:
            return None
        try:
            planned = int(ctx.get("planned_qty") or 0)
            if planned <= 0: return 0
            scale = self._scale_for(self._pnl_pct(ctx))
            return max(0, int(planned * scale))
        except Exception:
            return None


