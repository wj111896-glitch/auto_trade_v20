from hub.hub_trade import Hub
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

class DummyScoreEngine:
    def __init__(self, score): self._score = score
    def evaluate(self, snapshot): return self._score

adapter = MockAdapter()
router = OrderRouter(adapter)

print("=== BUY path ===")
hub = Hub(DummyScoreEngine(1.0), RiskGate(), router)
hub.on_tick({"symbol":"AAA"})

print("=== HOLD path ===")
hub2 = Hub(DummyScoreEngine(0.0), RiskGate(), router)
hub2.on_tick({"symbol":"BBB"})
