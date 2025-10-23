from .weights import Weights
from .features.volume import volume_surge
from .features.tickflow import tick_flow
from .features.ta import ma_cross

class ScoreEngine:
    def __init__(self, weights: Weights | None = None):
        self.weights = weights or Weights()

    def evaluate(self, snapshot) -> float:
        s = 0.0
        s += self.weights.volume   * volume_surge(snapshot)
        s += self.weights.tickflow * tick_flow(snapshot)
        s += self.weights.ta       * ma_cross(snapshot)
        return s
