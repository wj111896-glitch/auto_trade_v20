from hub.hub_trade import Hub
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

class DummyScoreEngine:
    def __init__(self, score): self._score = score
    def evaluate(self, snapshot): return self._score

w = Weights()
gate = RiskGate(w)
router = OrderRouter(MockAdapter())
hub = Hub(DummyScoreEngine(0.0), gate, router)

print("=== TAKE PROFIT ===")
snap = {"symbol":"AAA","price":103,"position":{"qty":1,"avg_price":100}}
print("decision:", hub.on_tick(snap))

print("\n=== STOP LOSS ===")
snap = {"symbol":"BBB","price":98,"position":{"qty":1,"avg_price":100}}
print("decision:", hub.on_tick(snap))

print("\n=== TRAILING STOP ===")
pos = {"qty":1,"avg_price":102}
print("up1:", hub.on_tick({"symbol":"CCC","price":101,"position":pos}))
print("up2:", hub.on_tick({"symbol":"CCC","price":103,"position":pos}))
print("hit:", hub.on_tick({"symbol":"CCC","price":100.9,"position":pos}))
