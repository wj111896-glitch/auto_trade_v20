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
    max_total_exposure_pct: float = 0.1      # 전체 포트폴리오 노출 한도
    max_symbol_exposure_pct: float = 0.3     # 종목당 노출 한도
    max_sector_exposure_pct: Optional[float] = None  # 섹터 한도 (없으면 미적용)

    # 사이징 관련
    lot_size: int = 1
    min_order_value: int = 0                  # 최소 주문 금액(원). 0이면 제한 없음

    # 컨텍스트 키
    equity_key: str = "equity"                # ctx["account"][equity_key] 사용 기본키


class ExposurePolicy(BasePolicy):
    """
    포트폴리오 익스포저(총/심볼/섹터) 한도를 점검하고, 남은 한도 기반의 size_hint를 제공합니다.

    기대 ctx 키(여러 경로 허용):
      - account: {"equity": float}
      - equity / equity_now / cash (top-level)
      - exposure: { ... 동일 키 ... }
    """

    def __init__(self, cfg: Optional[ExposureConfig] = None):
        self.cfg = cfg or ExposureConfig()
        # RiskGate / Hub가 set_ctx 또는 속성 주입해 주는 경우 대응
        self.ctx: Dict[str, Any] = {}

    # ---- helpers ---------------------------------------------------------
    def _merge_ctx(self, ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """인자로 들어온 ctx가 비거나 누락되면 self.ctx를 폴백으로 사용."""
        base = dict(self.ctx or {})
        if isinstance(ctx, dict):
            base.update(ctx)
        return base

    def _equity(self, ctx: Dict[str, Any]) -> Optional[float]:
        """
        여러 위치의 equity를 허용:
        1) ctx["account"]["equity_key"]
        2) ctx["equity"] / ctx["equity_now"] / ctx["cash"]
        3) ctx["exposure"][동일 키들]
        """
        c = self._merge_ctx(ctx)

        # 1) account 블록
        acct = (c.get("account") or {})
        eq = acct.get(self.cfg.equity_key)
        if eq is not None:
            return float(eq)

        # 2) top-level 별칭들
        for k in ("equity", "equity_now", "cash"):
            if c.get(k) is not None:
                return float(c[k])

        # 3) nested exposure 블록
        exp = (c.get("exposure") or {})
        acct2 = (exp.get("account") or {})
        if acct2.get(self.cfg.equity_key) is not None:
            return float(acct2[self.cfg.equity_key])
        for k in ("equity", "equity_now", "cash"):
            if exp.get(k) is not None:
                return float(exp[k])

        return None

    @staticmethod
    def _price_from_pos(pos: dict, live_px: Optional[float] = None) -> float:
        """포지션 평가에 사용할 가격(보수적으로 mtm>avg>live 순서)."""
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
        by_sector: Dict[str, float] = {}
        for sym, pos in (pf or {}).items():
            sector = sector_of(sym) or "UNKNOWN"
            val = self._position_value(pos)  # pos 내부 mtm/avg 기준
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
        c = self._merge_ctx(ctx)
        eq = self._equity(c) or 0.0

        total_cap = eq * self.cfg.max_total_exposure_pct
        symbol_cap = eq * self.cfg.max_symbol_exposure_pct

        tot_val = self._portfolio_value(portfolio)
        sym_val = self._symbol_value(portfolio, symbol, float(price))

        rem_total = max(0.0, total_cap - tot_val)
        rem_symbol = max(0.0, symbol_cap - sym_val)

        rem_sector = float("inf")
        sector_of = c.get("sector_of")
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
        lot = max(1, int(self.cfg.lot_size))
        qty = (qty // lot) * lot
        return max(0, qty)

    # ---- policy API ------------------------------------------------------
    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        c = self._merge_ctx(ctx)
        eq = self._equity(c)
        if not eq or eq <= 0:
            return PolicyResult(allow=True, reason="exposure:ctx-missing")

        remain = self._remaining_values(symbol, float(price), portfolio, c)

        planned_qty = int((c.get("planned_qty") or 0))
        planned_val = max(0.0, float(price)) * max(0, planned_qty)

        total_cap_ok  = remain["total"]  - planned_val > 0
        symbol_cap_ok = remain["symbol"] - planned_val > 0
        sector_cap_ok = True
        if self.cfg.max_sector_exposure_pct is not None and callable(c.get("sector_of")):
            sector_cap_ok = remain["sector"] - planned_val > 0

        if not total_cap_ok:
            return PolicyResult(False, "exposure:block:total")
        if not symbol_cap_ok:
            return PolicyResult(False, "exposure:block:symbol")
        if not sector_cap_ok:
            return PolicyResult(False, "exposure:block:sector")

        effective_remain = min(remain["total"], remain["symbol"], remain["sector"])
        max_qty = self._max_qty_from_remaining(effective_remain, float(price))

        if self.cfg.min_order_value > 0 and float(price) > 0:
            min_qty = max(1, int(self.cfg.min_order_value // float(price)))
            min_qty = (min_qty // max(1, self.cfg.lot_size)) * max(1, self.cfg.lot_size)
            if effective_remain >= self.cfg.min_order_value:
                max_qty = max(max_qty, min_qty)

        ratio = (effective_remain / float(eq)) if eq else 0.0
        return PolicyResult(True, f"exposure:ok remain≈{ratio:.0%}", max_qty_hint=max_qty)

    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        c = self._merge_ctx(ctx)
        eq = self._equity(c)
        if not eq or eq <= 0:
            return None
        remain = self._remaining_values(symbol, float(price), portfolio, c)
        effective_remain = min(remain["total"], remain["symbol"], remain["sector"])
        max_qty = self._max_qty_from_remaining(effective_remain, float(price))
        if self.cfg.min_order_value > 0 and float(price) > 0:
            min_qty = max(1, int(self.cfg.min_order_value // float(price)))
            min_qty = (min_qty // max(1, self.cfg.lot_size)) * max(1, self.cfg.lot_size)
            if effective_remain >= self.cfg.min_order_value:
                max_qty = max(max_qty, min_qty)
        return max_qty
