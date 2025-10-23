from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

def main():
    # 임계값을 낮춰 BUY가 한 번 나오게 구성
    w = Weights(buy_threshold=0.3)
    hub = Hub(ScoreEngine(w), RiskGate(w), OrderRouter(MockAdapter()))

    # HOLD 케이스
    hub.on_tick({"symbol":"AAA", "curr_vol":1000, "avg_vol":1000, "fast":10, "slow":10})

    # BUY 케이스 (거래량 3배 → volume_surge=+1.0)
    hub.on_tick({"symbol":"VOL", "curr_vol":3000, "avg_vol":1000})

if __name__ == "__main__":
    main()
