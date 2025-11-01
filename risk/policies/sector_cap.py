# -*- coding: utf-8 -*-
# risk/policies/sector_cap.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .base import BasePolicy, PolicyResult

__all__ = ["SectorParams", "SectorCapPolicy"]


@dataclass
class SectorParams:
    """섹터 집중도 제한 파라미터"""
    sector_cap_pct: float = 0.40   # 섹터별 최대 노출 비율 (예: 0.4 = 40%)
    budget: float = 10_000_000.0   # 총 운용자산 (기본값)


class SectorCapPolicy(BasePolicy):
    """
    동일 섹터 내 노출이 일정 비율(cap)을 초과하면 신규 진입 차단

    ctx 요구 키:
      - "symbol_sector": Dict[str, str]     # 심볼별 섹터 매핑  {"005930": "IT", ...}
      - "sector_exposure": Dict[str, float] # 섹터별 현재 노출 금액
      - "budget": float                     # 전체 운용자금 (선택, 없으면 params.budget)
    """

    def __init__(self, params: Optional[SectorParams] = None):
        self.p = params or SectorParams()

    # ===================== 메인 로직 ===================== #
    def check_entry(self, symbol: str, price: float,
                    portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:

        sector_map: Dict[str, str] = ctx.get("symbol_sector", {}) or {}
        sector = sector_map.get(symbol)
        if not sector:
            return PolicyResult(True, "no_sector_info")

        # 현재 섹터별 노출 금액
        sector_exp: Dict[str, float] = ctx.get("sector_exposure", {}) or {}
        current_value = float(sector_exp.get(sector, 0.0))

        # 총 운용 예산
        budget = float(ctx.get("budget") or self.p.budget)
        if budget <= 0:
            return PolicyResult(True, "invalid_budget")

        # 섹터 한도 계산
        cap_value = budget * self.p.sector_cap_pct

        if current_value >= cap_value:
            return PolicyResult(False, f"sector_cap:{sector}:{current_value:.0f}/{cap_value:.0f}")

        return PolicyResult(True, f"ok:{sector}:{current_value:.0f}/{cap_value:.0f}")

    # ===================== 힌트(잔여 진입량) ===================== #
    def size_hint(self, symbol: str, price: float,
                  portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        """
        섹터 여유분을 기준으로 진입 가능 수량 힌트 제공.
        """
        sector_map: Dict[str, str] = ctx.get("symbol_sector", {}) or {}
        sector = sector_map.get(symbol)
        if not sector or price <= 0:
            return None

        sector_exp: Dict[str, float] = ctx.get("sector_exposure", {}) or {}
        current_value = float(sector_exp.get(sector, 0.0))
        budget = float(ctx.get("budget") or self.p.budget)
        if budget <= 0:
            return None

        cap_value = budget * self.p.sector_cap_pct
        remaining = max(cap_value - current_value, 0)
        if remaining <= 0:
            return 0
        return int(remaining // price)
