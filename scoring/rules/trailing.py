def trailing_exit(position, price, peak_price=None, trail_pct: float = 0.02) -> tuple[bool, float]:
    """
    peak_price를 갱신하며, peak 대비 trail_pct 하락 시 True 반환.
    반환: (exit?, new_peak)
    """
    if peak_price is None:
        peak_price = price
    new_peak = max(peak_price, price)
    exit_sig = price <= new_peak * (1.0 - trail_pct)
    return exit_sig, new_peak
