from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

snapshot = {"symbol":"TF", "buy_vol":70, "sell_vol":30}  # tick_flow = +0.4

w = Weights(volume=0.0, tickflow=1.0, ta=0.0, buy_threshold=0.3)  # ← 핵심
engine = ScoreEngine(w)
gate   = RiskGate(w)
router = OrderRouter(MockAdapter())
hub    = Hub(engine, gate, router)

dec = hub.on_tick(snapshot)
print("decision:", dec)
