def should_take_profit(position, price, tp_pct: float = 0.03) -> bool:
    if not position or position.get("qty",0) == 0: 
        return False
    avg = float(position.get("avg_price", 0.0))
    return price >= avg * (1.0 + tp_pct)
