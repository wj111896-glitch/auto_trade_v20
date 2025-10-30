# -*- coding: utf-8 -*-
"""
ExposurePolicy — 포트폴리오 노출(익스포저) 한도 점검 + 진입 수량 힌트

인터페이스( RiskGate 호환 )
- check_entry(symbol, price, portfolio, ctx) -> PolicyResult
- size_hint(symbol, price, portfolio, ctx) -> Optional[int]

ctx 기대 키
- budget: float                      # 총 예산(원) — 없으면 params.budget 사용
- sector_of: Callable[[str], str|None]  # 심볼→섹터 매핑(선택)
- planned_qty: int                   # (선택) 이번 진입 예정 수량 — check_entry에 반영

포트폴리오 포맷 예시
{
  "005930": {"qty": 100, "avg_px": 72000},
  "000660": {"qty": 50,  "avg_px": 115000},
}
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

from .base import BasePolicy, PolicyResult

__all__ = ["ExposureParams", "ExposurePolicy"]


# ================== Params ==================
@dataclass
class ExposureParams:
    """
    노출(익스포저) 한도 파라미터
    - max_total_exposure_pct : 총자산 대비 전체 보유 한도 (ex. 0.50 = 50%)
    - per_symbol_cap_pct     : 종목당 보유 한도 (ex. 0.10 = 10%)
    - per_sector_cap_pct     : 섹터당 보유 한도 (ex. 0.40 = 40%)  # sector_of 제공 시만 적용
    - min_order_value        : 최소 주문금액(원) — size_hint에서 수량 산출 기준
    - lot_size               : 수량 라운딩 단위
    - budget                 : 기본 예산(원). ctx["budget"]가 오면 그 값으로 대체
    """
    max_total_exposure_pct: float = 1.0
    per_symbol_cap_pct: float = 0.5
    per_sector_cap_pct: float = 0.8

    min_order_value: int = 20_000
    lot_size: int = 1
    budget: float = 10_000_000.0


# ================== Policy ==================
class ExposurePolicy(BasePolicy):
    """
    포트폴리오 익스포저 한도를 점검하는 정책.

    BasePolicy 인터페이스:
      - check_entry(symbol, price, portfolio, ctx) -> PolicyResult
      - size_hint(symbol, price, portfolio, ctx) -> Optional[int]
    """

    def __init__(self, params: Optional[ExposureParams] = None):
        self.p = params or ExposureParams()

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def _pf_value(pf: Dict[str, dict]) -> float:
        # 보유자산 평가액 합 (avg_px 기반, 보수적 용도면 size_hint에서 cap으로 조정)
        return sum(float(v.get("qty", 0)) * float(v.get("avg_px", 0)) for v in (pf or {}).values())

    @staticmethod
    def _sym_value(pf: Dict[str, dict], sym: str, live_px: float) -> float:
        pos = (pf or {}).get(sym)
        if not pos:
            return 0.0
        qty = float(pos.get("qty", 0))
        avg = float(pos.get("avg_px", 0))
        base = max(avg, float(live_px))  # 보수적 평가(더 큰 가격 기준)
        return qty * base

    @staticmethod
    def _sector_value(
        pf: Dict[str, dict],
        sector_of: Callable[[str], Optional[str]],
        live_prices: Dict[str, float],
    ) -> Dict[str, float]:
        """섹터별 현재 보유 평가금액 합계"""
        sector_sum: Dict[str, float] = {}
        for sym, pos in (pf or {}).items():
            sector = sector_of(sym) or "UNKNOWN"
            qty = float(pos.get("qty", 0))
            avg = float(pos.get("avg_px", 0))
            px = float(live_prices.get(sym, avg))
            base = max(avg, px)
            sector_sum[sector] = sector_sum.get(sector, 0.0) + qty * base
        return sector_sum

    # ---- policy checks ---------------------------------------------------
    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        p = self.p
        budget: float = float(ctx.get("budget") or p.budget)
        planned_qty: int = int(ctx.get("planned_qty") or 0)
        planned_value: float = max(float(price), 0.0) * max(planned_qty, 0)

        # 현재 노출 평가
        total_val = self._pf_value(portfolio)
        sym_val = self._sym_value(portfolio, symbol, float(price))

        # ① 총 노출 한도 (이번 진입 포함 가정 평가)
        if (total_val + planned_value) > p.max_total_exposure_pct * budget:
            return PolicyResult(False, "total_exposure_cap")

        # ② 종목 한도
        if (sym_val + planned_value) > p.per_symbol_cap_pct * budget:
            return PolicyResult(False, "symbol_exposure_cap")

        # ③ 섹터 한도 (sector_of 제공시에만)
        sector_of: Optional[Callable[[str], Optional[str]]] = ctx.get("sector_of")
        if callable(sector_of):
            live_prices = {symbol: float(price)}  # 부족하면 avg_px로 대체하도록 _sector_value가 처리
            sector_vals = self._sector_value(portfolio, sector_of, live_prices)
            sector = sector_of(symbol) or "UNKNOWN"
            sector_cur = float(sector_vals.get(sector, 0.0))
            if (sector_cur + planned_value) > p.per_sector_cap_pct * budget:
                return PolicyResult(False, "sector_exposure_cap")

        return PolicyResult(True, "ok")

    # ---- sizing ----------------------------------------------------------
    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        """
        최소 주문금액 기반 기본 수량을 만든 뒤,
        총/심볼/섹터 남은 한도에 맞춰 자동으로 '깎아'서 반환.
        -> total_exposure_cap 때문에 막히던 진입을 수량 조절로 통과시킴.
        """
        price = float(price)
        if price <= 0:
            return 0
        p = self.p

        # 0) 기본 수량(최소 주문금액 + lot_size)
        base_qty = max(0, int(p.min_order_value // int(price)))
        base_qty = (base_qty // p.lot_size) * p.lot_size
        if base_qty == 0 and p.min_order_value <= price:
            base_qty = p.lot_size

        budget: float = float(ctx.get("budget") or p.budget)
        sector_of = ctx.get("sector_of")

        # 현재 노출
        total_val = self._pf_value(portfolio)
        sym_val   = self._sym_value(portfolio, symbol, price)

        # 1) 총 한도 남은 여유(원) → 수량
        max_total = p.max_total_exposure_pct * budget
        head_total = max(0.0, max_total - total_val)
        allow_by_total = int(head_total // price)

        # 2) 종목 한도 남은 여유(원) → 수량
        max_sym = p.per_symbol_cap_pct * budget
        head_sym = max(0.0, max_sym - sym_val)
        allow_by_symbol = int(head_sym // price)

        # 3) 섹터 한도 남은 여유(있을 때만)
        allow_by_sector = 10**9  # 사실상 무한
        if callable(sector_of):
            sector = sector_of(symbol) or "UNKNOWN"
            # 섹터 현재 노출 합계
            sec_cur = 0.0
            for s, pos in (portfolio or {}).items():
                if (sector_of(s) or "UNKNOWN") == sector:
                    q = float(pos.get("qty", 0)); avg = float(pos.get("avg_px", 0))
                    px = max(avg, price if s == symbol else avg)
                    sec_cur += q * px
            max_sec = p.per_sector_cap_pct * budget
            head_sec = max(0.0, max_sec - sec_cur)
            allow_by_sector = int(head_sec // price)

        # 4) 한도 모두 만족하도록 수량 결정
        qty = min(base_qty, allow_by_total, allow_by_symbol, allow_by_sector)

        # lot_size 보정 및 하한
        qty = (qty // p.lot_size) * p.lot_size
        return max(0, qty)

