from dataclasses import dataclass, field
from typing import Dict, Any
from scoring.weights import Weights
from bus.schema import Decision
from scoring.rules.take_profit import should_take_profit
from scoring.rules.stop_loss import should_stop_loss
from scoring.rules.trailing import trailing_exit
from common.config import TP_PCT, SL_PCT, TRAIL_PCT   # ← 설정값 읽어오기

@dataclass
class RiskGate:
    weights: Weights | None = None
    max_exposure: float = 1.0
    peaks: Dict[str, float] = field(default_factory=dict)  # 심볼별 고점(트레일링)

    def __post_init__(self):
        if self.weights is None:
            self.weights = Weights()

    def apply(self, score: float, snapshot: Dict[str, Any]) -> Decision:
        """
        순서:
        1) 보유중이면 출구 규칙(익절/손절/트레일링) 우선 — 파라미터는 common.config 사용
        2) 아니면 점수 임계값으로 진입/청산
        """
        sym = snapshot.get("symbol", "TEST")
        price = float(snapshot.get("price", 0.0))
        pos: dict | None = snapshot.get("position")

        # === 보유중: 출구 규칙 ===
        if pos and float(pos.get("qty", 0)) > 0:
            # 1) 익절
            if should_take_profit(pos, price, tp_pct=TP_PCT):
                return Decision(sym, "SELL", float(pos.get("qty", 0)), "take_profit")
            # 2) 손절
            if should_stop_loss(pos, price, sl_pct=SL_PCT):
                return Decision(sym, "SELL", float(pos.get("qty", 0)), "stop_loss")
            # 3) 트레일링 스톱
            peak = self.peaks.get(sym)
            exit_sig, new_peak = trailing_exit(pos, price, peak_price=peak, trail_pct=TRAIL_PCT)
            self.peaks[sym] = new_peak
            if exit_sig:
                return Decision(sym, "SELL", float(pos.get("qty", 0)), "trailing_stop")

        # === 미보유 또는 출구 신호 없음: 점수로 판단 ===
        if score >= self.weights.buy_threshold:
            return Decision(sym, "BUY", 1.0, "score>=buy_threshold")
        if score <= self.weights.sell_threshold:
            return Decision(sym, "SELL", 1.0, "score<=sell_threshold")
        return Decision(sym, None, 0.0, "hold")
