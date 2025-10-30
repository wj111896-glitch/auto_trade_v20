# -*- coding: utf-8 -*-
# risk/policies/exposure.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
import math

from .base import BasePolicy, PolicyResult


__all__ = ["ExposureConfig", "ExposurePolicy"]


# ================== Config ==================
@dataclass
class ExposureConfig:
    """익스포저(노출) 한도 파라미터"""
    # 자본 대비 한도
    max_total_exposure_pct: float = 0.60    # 전체 포트폴리오 노출 한도 (예: 0.60 = 60%)
    max_symbol_exposure_pct: float = 0.20   # 종목당 노출 한도 (예: 0.20 = 20%)
    max_sector_exposure_pct: Optional[float] = None  # 섹터 한도 (없으면 미적용)

    # 사이징 관련
    lot_size: int = 1                        # 최소 거래 단위(주)
    min_order_value: int = 0                 # 최소 주문 금액(원). 0이면 제한 없음

    # 컨텍스트 키
    equity_key: str = "equity"               # ctx["account"][equity_key] 사용


# ================== Policy ==================
class ExposurePolicy(BasePolicy):
    """
    포트폴리오 익스포저(총/심볼/섹터) 한도를 점검하고, 남은 한도 기반의 size_hint를 제공합니다.

    BasePolicy 인터페이스:
      - check_entry(symbol, price, portfolio, ctx) -> PolicyResult
      - size_hint(symbol, price, portfolio, ctx) -> Optional[int]

    ctx 기대 키:
      - account: {"equity": float}                    # 필수(자본)
      - planned_qty: int                              # 선택(이번 진입 예정 수량)
      - sector_of: Callable[[str], Optional[str]]     # 선택(섹터명 매핑 함수)
    """

    def __init__(self, cfg: Optional[ExposureConfig] = None):
        self.cfg = cfg or ExposureConfig()

    # ---- helpers ---------------------------------------------------------
    def _equity(self, ctx: Dict[str, Any]) -> Optional[float]:
        acct = (ctx or {}).get("account") or {}
        eq = acct.get(self.cfg.equity_key)
        return float(eq) if eq is not None else None

    @staticmethod
    def _price_from_pos(pos: dict, live_px: Optional[float] = None) -> float:
        """포지션 평가에 사용할 가격(보수적으로 mtm>avg>live 순서로 선택)."""
        if pos is None:
            return float(live_px or 0.0)
        mtm = pos.get("mtm_price")
        if mtm is not None:
            return float(mtm)
        avg = pos.get("avg_price") or pos.get("avg_px")
        if avg is not None:
            return float(avg)
        return float(live_px or 0.0)

    def _position_value(self, pos: dict, live_px: Optional[float] = None) -> float:
        qty = float((pos or {}).get("qty") or 0.0)
        px = self._price_from_pos(pos, live_px)
        return max(0.0, qty * px)

    def _portfolio_value(self, pf: Dict[str, dict]) -> float:
        return sum(self._position_value(pos) for pos in (pf or {}).values())

    def _symbol_value(self, pf: Dict[str, dict], sym: str, live_px: float) -> float:
        return self._position_value((pf or {}).get(sym), live_px)

    def _sector_values(
        self,
        pf: Dict[str, dict],
        sector_of: Callable[[str], Optional[str]],
    ) -> Dict[str, float]:
        """섹터별 현재 보유 평가금액 합계"""
        by_sector: Dict[str, float] = {}
        for sym, pos in (pf or {}).items():
            sector = sector_of(sym) or "UNKNOWN"
            val = self._position_value(pos)  # pos 내부의 mtm/avg 기준
            by_sector[sector] = by_sector.get(sector, 0.0) + val
        return by_sector

    # ---- core calc -------------------------------------------------------
    def _remaining_values(
        self,
        symbol: str,
        price: float,
        portfolio: Dict[str, dict],
        ctx: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        총/심볼/섹터(옵션) 남은 한도를 원화 기준으로 계산해서 반환.
        """
        eq = self._equity(ctx) or 0.0
        total_cap = eq * self.cfg.max_total_exposure_pct
        symbol_cap = eq * self.cfg.max_symbol_exposure_pct

        tot_val = self._portfolio_value(portfolio)
        sym_val = self._symbol_value(portfolio, symbol, float(price))

        rem_total = max(0.0, total_cap - tot_val)
        rem_symbol = max(0.0, symbol_cap - sym_val)

        rem_sector = float("inf")
        sector_of = ctx.get("sector_of")
        if callable(sector_of) and self.cfg.max_sector_exposure_pct is not None:
            sector = sector_of(symbol) or "UNKNOWN"
            by_sector = self._sector_values(portfolio, sector_of)
            sector_cap = eq * float(self.cfg.max_sector_exposure_pct)
            sector_now = float(by_sector.get(sector, 0.0))
            rem_sector = max(0.0, sector_cap - sector_now)

        return {"total": rem_total, "symbol": rem_symbol, "sector": rem_sector}

    def _max_qty_from_remaining(self, remain_value: float, price: float) -> int:
        if price <= 0:
            return 0
        qty = int(math.floor(remain_value / float(price)))
        # lot_size 정렬
        lot = max(1, int(self.cfg.lot_size))
        qty = (qty // lot) * lot
        return max(0, qty)

    # ---- policy API ------------------------------------------------------
    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        eq = self._equity(ctx)
        if not eq or eq <= 0:
            # 계좌 정보 없으면 정책 적용 불가 → 통과(로그만 남기는게 일반적)
            return PolicyResult(allow=True, reason="exposure:ctx-missing")

        remain = self._remaining_values(symbol, float(price), portfolio, ctx)

        # planned_qty(선택)까지 고려해 하드 블록 여부 판단
        planned_qty = int(ctx.get("planned_qty") or 0)
        planned_val = max(0.0, float(price)) * max(0, planned_qty)

        total_cap_ok = remain["total"] - planned_val > 0
        symbol_cap_ok = remain["symbol"] - planned_val > 0
        sector_cap_ok = True
        if self.cfg.max_sector_exposure_pct is not None and callable(ctx.get("sector_of")):
            sector_cap_ok = remain["sector"] - planned_val > 0

        if not total_cap_ok:
            return PolicyResult(False, f"exposure:block:total used={1 - remain['total']/ (eq*self.cfg.max_total_exposure_pct + 1e-9):.0%}")
        if not symbol_cap_ok:
            return PolicyResult(False, "exposure:block:symbol")
        if not sector_cap_ok:
            return PolicyResult(False, "exposure:block:sector")

        # 통과 시에도 남은 한도 기반 최대 진입 수량 힌트 제공
        effective_remain = min(remain["total"], remain["symbol"], remain["sector"])
        max_qty = self._max_qty_from_remaining(effective_remain, float(price))

        # 최소 주문금액 기준 하한(있다면)
        if self.cfg.min_order_value > 0 and float(price) > 0:
            min_qty = max(1, int(self.cfg.min_order_value // float(price)))
            min_qty = (min_qty // max(1, self.cfg.lot_size)) * max(1, self.cfg.lot_size)
            max_qty = max(max_qty, min_qty) if effective_remain >= self.cfg.min_order_value else max_qty

        return PolicyResult(True, f"exposure:ok remain≈{effective_remain/eq:.0%}", max_qty_hint=max_qty)

    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        """check_entry와 동일 로직으로 최대 진입 수량을 재계산하여 반환."""
        eq = self._equity(ctx)
        if not eq or eq <= 0:
            return None
        remain = self._remaining_values(symbol, float(price), portfolio, ctx)
        effective_remain = min(remain["total"], remain["symbol"], remain["sector"])
        max_qty = self._max_qty_from_remaining(effective_remain, float(price))

        if self.cfg.min_order_value > 0 and float(price) > 0:
            min_qty = max(1, int(self.cfg.min_order_value // float(price)))
            min_qty = (min_qty // max(1, self.cfg.lot_size)) * max(1, self.cfg.lot_size)
            max_qty = max(max_qty, min_qty) if effective_remain >= self.cfg.min_order_value else max_qty
        return max_qty

