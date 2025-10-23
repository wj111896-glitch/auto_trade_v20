from scoring.weights import Weights

# === 전략 가중치 및 임계값 (여기만 수정하면 전체에 반영) ===
WEIGHTS = Weights(
    volume=0.4,       # 거래량 신호 가중치
    tickflow=0.3,     # 체결강도 신호 가중치
    ta=0.3,           # 기술적 신호 가중치
    buy_threshold=0.7,
    sell_threshold=-0.7,
)

# === 출구 규칙 기본 파라미터 ===
TP_PCT = 0.03     # 익절 +3%
SL_PCT = 0.02     # 손절 -2%
TRAIL_PCT = 0.02  # 트레일링 2%
