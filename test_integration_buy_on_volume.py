from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

# 거래량이 평균의 3배 → volume_surge = clip(3/1 -1) = 1.0
snapshot = {"symbol":"VOL","curr_vol":3000,"avg_vol":1000}

engine = ScoreEngine(Weights(buy_threshold=0.3))   # 임계값 낮춰 BUY 유도
gate   = RiskGate(Weights(buy_threshold=0.3))
router = OrderRouter(MockAdapter())
hub    = Hub(engine, gate, router)

dec = hub.on_tick(snapshot)
print("decision:", dec)
