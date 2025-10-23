from dataclasses import dataclass

@dataclass
class Weights:
    volume: float = 0.4
    tickflow: float = 0.3
    ta: float = 0.3
    buy_threshold: float = 0.7
    sell_threshold: float = -0.7
