from dataclasses import dataclass

@dataclass
class Tick:
    symbol: str
    price: float
    volume: int
    ts: float  # epoch ms

@dataclass
class Decision:
    symbol: str
    action: str | None  # "BUY"/"SELL"/None
    size: float = 0.0
    reason: str = ""
