from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

# fast > slow → ma_cross = +1.0
snapshot = {"symbol":"TA", "fast": 20, "slow": 10}

# 임계값 낮춰 BUY 유도
w = Weights(buy_threshold=0.3)
engine = ScoreEngine(w)
gate   = RiskGate(w)
router = OrderRouter(MockAdapter())
hub    = Hub(engine, gate, router)

dec = hub.on_tick(snapshot)
print("decision:", dec)
