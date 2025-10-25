# ====== BEGIN: DAYTRADE PRESET ======
DAYTRADE = {
    "weights": {
        "volume":   0.45,
        "tickflow": 0.35,
        "ta":       0.20,
    },
    "thresholds": {
        "buy":   0.55,
        "sell": -0.55,
    },
    "exits": {
        "tp_pct":        0.012,  # +1.2%
        "sl_pct":       -0.008,  # -0.8%
        "trailing_pct":  0.010,  # 1.0%
    },
    "risk": {
        "budget":                 100_000_000,  # 모의 예산(1억원)
        "intraday_exposure_max":  0.60,         # 일중 총 노출 60%
        "per_symbol_cap_min":     0.10,         # 종목 최소 캡
        "per_symbol_cap_max":     0.15,         # 종목 최대 캡
        "day_dd_kill":            0.03,         # 일중 DD -3%면 중지
    },
    "ops": {
        "cooldown_sec_after_fill": 60,   # 체결 직후 과열 진입 방지
        "session_only": True,            # 정규장만(모의에선 무시 가능)
    }
}
# ====== END: DAYTRADE PRESET ======

# ---- legacy constants for risk.core compatibility ----
# risk/core.py가 옛날 방식으로 불러와도 에러 나지 않게 하는 호환 상수
TP_PCT = 0.012     # +1.2%
SL_PCT = -0.008    # -0.8%
TRAIL_PCT = 0.010  # 1.0%

