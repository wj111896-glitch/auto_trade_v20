# -*- coding: utf-8 -*-
# Stop loss rule

class StopLoss:
    """평단 대비 손실률이 sl_pct 이하(음수)면 True"""
    def __init__(self, sl_pct: float):
        self.sl_pct = sl_pct  # 예: -0.008 = -0.8%

    def check(self, sym: str, pos: dict, price: float) -> bool:
        qty = pos.get("qty", 0)
        avg = pos.get("avg_px", 0.0)
        if qty <= 0 or avg <= 0:
            return False
        pnl = price / avg - 1.0
        return pnl <= self.sl_pct
