# -*- coding: utf-8 -*-
# Trailing stop rule (ver.2 완전본)

class TrailingStop:
    """
    고점(peak_px) 대비 하락폭이 trailing_pct 이상이면 True
    pos dict 안에 'peak_px', 'qty'가 있다고 가정
    """
    def __init__(self, trailing_pct: float):
        self.trailing_pct = trailing_pct  # 예: 0.010 = 1.0%

    def check(self, sym: str, pos: dict, price: float) -> bool:
        qty = pos.get("qty", 0)
        peak = pos.get("peak_px", 0.0)
        if qty <= 0 or peak <= 0:
            return False
        drawdown = price / peak - 1.0
        return drawdown <= -self.trailing_pct


# --- 호환용 함수 (risk/core.py의 옛 import 방지용) ---
def trailing_exit(pos: dict, price: float, trailing_pct: float = 0.010) -> bool:
    """
    peak_px 대비 하락폭이 trailing_pct 이상이면 True
    pos에는 'qty'와 'peak_px'가 있다고 가정
    """
    qty = pos.get("qty", 0)
    peak = pos.get("peak_px", 0.0)
    if qty <= 0 or peak <= 0:
        return False
    drawdown = price / peak - 1.0
    return drawdown <= -trailing_pct
