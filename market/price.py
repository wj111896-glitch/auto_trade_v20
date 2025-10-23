def get_snapshot(symbol: str):
    """
    아주 단순 스냅샷 더미:
    실제로는 시세 어댑터에서 받아오는 값들을 넣게 됩니다.
    """
    return {
        "symbol": symbol,
        "price": 1000.0,
        "volume": 0,
        "fast": 0.0,  # TA용 자리
        "slow": 0.0,  # TA용 자리
    }
