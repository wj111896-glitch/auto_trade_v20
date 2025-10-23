def ma_cross(snapshot) -> float:
    """
    단순 이동평균 크로스:
      fast > slow → +1
      fast < slow → -1
      fast == slow 또는 값 없음 → 0
    fast/slow 키가 없으면 0 처리.
    """
    fast = snapshot.get("fast", None)
    slow = snapshot.get("slow", None)
    if fast is None or slow is None:
        return 0.0
    try:
        f = float(fast); s = float(slow)
    except (TypeError, ValueError):
        return 0.0
    if f > s:  return 1.0
    if f < s:  return -1.0
    return 0.0
