def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def _from_prints(prints) -> tuple[float, float]:
    buy = sell = 0.0
    for p in prints or []:
        side = str(p.get("side","")).upper()
        size = float(p.get("size", 0.0) or 0.0)
        if side == "BUY":  buy  += size
        elif side == "SELL": sell += size
    return buy, sell

def tick_flow(snapshot) -> float:
    """
    매수/매도 체결 비중 기반 체결강도 프록시:
      score = (buy - sell) / (buy + sell)  → [-1, 1]로 클리핑
    입력 형태:
      1) snapshot["buy_vol"], snapshot["sell_vol"]  (우선)
      2) snapshot["prints"] = [{"side":"BUY"/"SELL","size":...}, ...]
    둘 다 없거나 합이 0이면 0.0
    """
    buy = snapshot.get("buy_vol")
    sell = snapshot.get("sell_vol")

    if buy is None or sell is None:
        buy, sell = _from_prints(snapshot.get("prints"))

    tot = (buy or 0.0) + (sell or 0.0)
    if tot <= 0.0:
        return 0.0
    raw = ((buy or 0.0) - (sell or 0.0)) / tot
    return _clip(raw)
