def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def volume_surge(snapshot) -> float:
    """
    (현재거래량 / 평균거래량) - 1  값을 [-1, 1]로 클리핑.
    키 후보: curr_vol / avg_vol  (없으면 0 처리)
    """
    curr = float(snapshot.get("curr_vol") or snapshot.get("volume") or 0.0)
    avg  = float(snapshot.get("avg_vol")  or snapshot.get("volume_avg") or 0.0)
    if avg <= 0:
        return 0.0
    return _clip(curr / avg - 1.0)
