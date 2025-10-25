# -*- coding: utf-8 -*-
# Take profit rule for intraday runner

class TakeProfit:
    """평단 대비 수익률이 tp_pct 이상이면 True"""
    def __init__(self, tp_pct: float):
        self.tp_pct = tp_pct  # 예: 0.012 = +1.2%

    def check(self, sym: str, pos: dict, price: float) -> bool:
        qty = pos.get("qty", 0)
        avg = pos.get("avg_px", 0.0)
        if qty <= 0 or avg <= 0:
            return False
        pnl = price / avg - 1.0
        return pnl >= self.tp_pct
