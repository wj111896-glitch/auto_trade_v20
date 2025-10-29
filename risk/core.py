# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Dict
from common.config import DAYTRADE

@dataclass
class RiskGate:
    """
    단타 러너용 간단 리스크 게이트 (예산/노출/종목 캡 적용)
      - allow_entry(sym, portfolio, price) -> bool
      - size_for(sym, price) -> int
      - heartbeat_ok() -> bool
    """
    cfg: dict = field(default_factory=lambda: DAYTRADE.get("risk", {}))
    exposure_now: float = 0.0
    day_dd: float = 0.0
    _last_portfolio: Dict[str, dict] = field(default_factory=dict, repr=False)

    # ----- helpers -----
    def _budget(self) -> float:
        return float(self.cfg.get("budget", 100_000_000))

    def _per_symbol_cap(self) -> tuple[float, float]:
        min_cap = float(self.cfg.get("per_symbol_cap_min", 0.10))
        max_cap = float(self.cfg.get("per_symbol_cap_max", 0.15))
        return min_cap, max_cap

    def _intraday_exposure_max(self) -> float:
        return float(self.cfg.get("intraday_exposure_max", 0.60))

    def _calc_exposure(self, portfolio: Dict[str, dict]) -> float:
        budget = self._budget()
        if budget <= 0:
            return 0.0
        total_value = 0.0
        for pos in portfolio.values():
            qty = float(pos.get("qty", 0))
            avg = float(pos.get("avg_px", 0.0))
            total_value += max(0.0, qty * max(avg, 0.0))
        return total_value / budget

    def _symbol_value(self, sym: str, portfolio: Dict[str, dict], fallback_px: float) -> float:
        pos = portfolio.get(sym)
        if not pos:
            return 0.0
        qty = float(pos.get("qty", 0))
        avg = float(pos.get("avg_px", 0.0)) or float(fallback_px)
        return max(0.0, qty * max(avg, 0.0))

    # ----- API -----
    def allow_entry(self, sym: str, portfolio: Dict[str, dict], price: float) -> bool:
        self._last_portfolio = dict(portfolio)  # snapshot
        budget = self._budget()
        _, max_cap = self._per_symbol_cap()
        exposure_limit = self._intraday_exposure_max()

        self.exposure_now = self._calc_exposure(portfolio)
        if self.exposure_now >= exposure_limit:
            return False

        sym_value_now = self._symbol_value(sym, portfolio, price)
        if sym_value_now >= max_cap * budget:
            return False

        return True

    def size_for(self, sym: str, price: float) -> int:
        if price <= 0:
            return 0

        budget = self._budget()
        _, max_cap = self._per_symbol_cap()
        exposure_limit = self._intraday_exposure_max()

        portfolio = self._last_portfolio or {}
        total_expo = self._calc_exposure(portfolio)
        sym_value_now = self._symbol_value(sym, portfolio, price)

        total_remaining_value = max(0.0, exposure_limit * budget - total_expo * budget)
        sym_remaining_value   = max(0.0, max_cap * budget - sym_value_now)
        target_value = min(total_remaining_value, sym_remaining_value)

        if target_value < price:
            return 0
        return int(target_value // price)  # floor: never exceed caps

    def heartbeat_ok(self) -> bool:
        # TODO: cfg['day_dd_kill'] 도입 시 드로우다운 컷 적용
        return True
