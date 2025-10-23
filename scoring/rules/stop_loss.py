def should_stop_loss(position, price, sl_pct: float = 0.02) -> bool:
    if not position or position.get("qty",0) == 0:
        return False
    avg = float(position.get("avg_price", 0.0))
    return price <= avg * (1.0 - sl_pct)
