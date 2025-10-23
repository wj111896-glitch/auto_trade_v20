from dataclasses import dataclass
from scoring.weights import Weights
from bus.schema import Decision

@dataclass
class RiskGate:
    weights: Weights | None = None
    max_exposure: float = 1.0  # (확장 예정)

    def __post_init__(self):
        if self.weights is None:
            self.weights = Weights()

    def apply(self, score: float, snapshot) -> Decision:
        """
        단순 규칙:
        - score >= buy_threshold  → BUY
        - score <= sell_threshold → SELL
        - 그 외 → 대기(None)
        """
        sym = snapshot.get("symbol","TEST")
        if score >= self.weights.buy_threshold:
            return Decision(sym, "BUY", 1.0, "score>=buy_threshold")
        if score <= self.weights.sell_threshold:
            return Decision(sym, "SELL", 1.0, "score<=sell_threshold")
        return Decision(sym, None, 0.0, "hold")
