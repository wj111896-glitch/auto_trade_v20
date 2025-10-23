from obs.log import info, error
from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter

def main():
    info("앱 시작")
    hub = Hub(ScoreEngine(Weights(buy_threshold=0.3)), RiskGate(Weights(buy_threshold=0.3)), OrderRouter(MockAdapter()))
    info("허브 준비 완료")

    # HOLD 케이스
    hub.on_tick({"symbol":"AAA", "curr_vol":1000, "avg_vol":1000})
    # BUY 케이스 (거래량 3배)
    hub.on_tick({"symbol":"VOL", "curr_vol":3000, "avg_vol":1000})

    info("앱 종료")

if __name__ == "__main__":
    main()
