import time
from hub.hub_trade import Hub
from scoring.core import ScoreEngine
from scoring.weights import Weights
from risk.core import RiskGate
from order.router import OrderRouter
from order.adapters.mock import MockAdapter
from obs.log import info

# 임계값 낮춰 반응 보이게
W = Weights(buy_threshold=0.3)

hub = Hub(ScoreEngine(W), RiskGate(W), OrderRouter(MockAdapter()))

def main():
    info("=== LOOP DEMO START ===")

    # 시나리오: HOLD → 거래량 급증 BUY → 보유 상태에서 익절/손절/트레일링
    steps = [
        {"symbol":"AAA", "curr_vol":1000, "avg_vol":1000, "fast":10, "slow":10},  # HOLD
        {"symbol":"VOL", "curr_vol":3000, "avg_vol":1000},                        # BUY (volume)
        # 보유 가정 후 가격 변화(익절/손절/트레일링 테스트)
        {"symbol":"VOL", "price":101, "position":{"qty":1,"avg_price":100}},      # hold
        {"symbol":"VOL", "price":103, "position":{"qty":1,"avg_price":100}},      # take_profit
        {"symbol":"TF",  "buy_vol":70, "sell_vol":30},                             # BUY (tickflow)
        {"symbol":"TF",  "price":69,  "position":{"qty":1,"avg_price":70}},       # stop_loss 예시
        {"symbol":"CC",  "fast":20, "slow":10},                                    # BUY (ta)
        {"symbol":"CC",  "price":101, "position":{"qty":1,"avg_price":102}},      # 트레일링 준비
        {"symbol":"CC",  "price":103, "position":{"qty":1,"avg_price":102}},      # 고점 갱신
        {"symbol":"CC",  "price":100.9, "position":{"qty":1,"avg_price":102}},    # trailing_stop
    ]

    for step in steps:
        hub.on_tick(step)
        time.sleep(2)

    info("=== LOOP DEMO END ===")

if __name__ == "__main__":
    main()
