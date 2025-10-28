# -*- coding: utf-8 -*-
"""
공통 설정파일 (config.py)
v20 전체에서 공용: DAYTRADE 프리셋 + 브로커 설정 병행
"""

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
TP_PCT = 0.012     # +1.2%
SL_PCT = -0.008    # -0.8%
TRAIL_PCT = 0.010  # 1.0%

# ====== BEGIN: BROKER SETTINGS ======
# v20 허브/라우터/어댑터 공용
BROKER = "KIWOOM"       # "MOCK" | "KIWOOM"
ACCOUNT_NO = "00000000"  # 모의계좌 번호
DRY_RUN = True           # 실거래 False, 모의 True
ORDER_RATE_LIMIT_MS = 120
# ====== END: BROKER SETTINGS ======


