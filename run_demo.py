from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter
from market.price import get_snapshot

class DummyScoreEngine:
    def __init__(self, score): self._score = score
    def evaluate(self, snapshot): return self._score

def run_with_real_engine(symbol: str):
    print("=== REAL ENGINE (features stub → HOLD 예상) ===")
    engine = ScoreEngine(Weights())               # 현재 features는 0.0 → 총점 0.0
    gate = RiskGate(Weights())                    # 기본 임계값: buy 0.7 / sell -0.7
    router = OrderRouter(MockAdapter())
    hub = Hub(engine, gate, router)
    dec = hub.on_tick(get_snapshot(symbol))
    print("decision:", dec)

def run_with_dummy_buy(symbol: str):
    print("=== DUMMY ENGINE (강제 BUY) ===")
    engine = DummyScoreEngine(1.0)                # 점수 1.0 강제 주입 → BUY
    gate = RiskGate(Weights())
    router = OrderRouter(MockAdapter())
    hub = Hub(engine, gate, router)
    dec = hub.on_tick(get_snapshot(symbol))
    print("decision:", dec)

if __name__ == "__main__":
    run_with_real_engine("AAA")
    print()
    run_with_dummy_buy("BBB")
