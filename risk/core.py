# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# 러너에서 기대하는 최소 인터페이스만 구현합니다.
# - allow_entry(sym, portfolio, price) -> bool
# - size_for(sym, price) -> int
# - heartbeat_ok() -> bool

from common.config import DAYTRADE

@dataclass
class RiskGate:
    """단타 러너용 간단 리스크 게이트 (예산/노출/종목 캡만 적용)"""
    cfg: dict = field(default_factory=lambda: DAYTRADE.get("risk", {}))
    exposure_now: float = 0.0   # 현재 총 노출(예산 대비 비율)
    day_dd: float = 0.0         # 일중 드로우다운 (향후 확장용)

    # ---------- 내부 헬퍼 ----------
    def _budget(self) -> float:
        return float(self.cfg.get("budget", 100_000_000))

    def _per_symbol_cap(self) -> tuple[float, float]:
        min_cap = float(self.cfg.get("per_symbol_cap_min", 0.10))
        max_cap = float(self.cfg.get("per_symbol_cap_max", 0.15))
        return min_cap, max_cap

    def _intraday_exposure_max(self) -> float:
        return float(self.cfg.get("intraday_exposure_max", 0.60))

    def _calc_exposure(self, portfolio: Dict[str, dict]) -> float:
        """보유 종목들의 평가금액 합 / 예산"""
        budget = self._budget()
        if budget <= 0:
            return 0.0
        total_value = 0.0
        for pos in portfolio.values():
            qty = float(pos.get("qty", 0))
            avg = float(pos.get("avg_px", 0.0))
            total_value += max(0.0, qty * max(avg, 0.0))
        return total_value / budget

    # ---------- 러너가 호출하는 메서드 ----------
    def allow_entry(self, sym: str, portfolio: Dict[str, dict], price: float) -> bool:
        """
        진입 허용 여부:
        - 총 노출이 intraday_exposure_max를 넘으면 거부
        - 해당 심볼의 평가금액이 per_symbol_cap_max를 넘으면 거부
        """
        budget = self._budget()
        min_cap, max_cap = self._per_symbol_cap()
        exposure_limit = self._intraday_exposure_max()

        # 총 노출 갱신
        self.exposure_now = self._calc_exposure(portfolio)

        # 1) 총 노출 제한
        if self.exposure_now >= exposure_limit:
            return False

        # 2) 심볼별 캡 체크 (현재 평가금액)
        sym_value = 0.0
        pos = portfolio.get(sym)
        if pos:
            qty = float(pos.get("qty", 0))
            avg = float(pos.get("avg_px", price))
            sym_value = max(0.0, qty * max(avg, 0.0))

        target_max_value = max_cap * budget
        if sym_value >= target_max_value:
            return False

        return True

    def size_for(self, sym: str, price: float) -> int:
        """
        매수 수량 산정(정수 주식 수):
        - 남은 총 노출 한도와 per_symbol_cap_max 내에서 가능한 최대치
        - 최소 1주는 보장(가능 시)
        """
        budget = self._budget()
        min_cap, max_cap = self._per_symbol_cap()
        exposure_limit = self._intraday_exposure_max()

        # 총 노출 기준 남은 한도 금액
        max_total_value = exposure_limit * budget
        used_value = self.exposure_now * budget
        remaining = max(0.0, max_total_value - used_value)

        # 심볼별 상한
        per_symbol_max_value = max_cap * budget

        # 이번 주문으로 목표하는 금액(상한과 잔여 한도 중 작은 값)
        target_value = min(per_symbol_max_value, remaining)

        if target_value <= 0 or price <= 0:
            return 0

        qty = int(target_value // price)
        return max(1, qty)

    def heartbeat_ok(self) -> bool:
        """
        시스템 정상 여부 체크.
        - 향후: 일중 드로우다운(day_dd)이 cfg['day_dd_kill'] 넘으면 False 처리
        - 지금은 테스트이므로 True 반환
        """
        # kill = float(self.cfg.get("day_dd_kill", 0.03))
        # if self.day_dd <= -kill:  # 예: -0.03 ( -3% )
        #     return False
        return True

