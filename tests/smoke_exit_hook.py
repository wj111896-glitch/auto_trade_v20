# -*- coding: utf-8 -*-
import time
from hub.hub_trade import HubTrade
from scoring.rules.exit_rules import ExitRules

# 상승 후 급락 → 트레일링 스탑 청산 시나리오
prices = [
    {"AAA": 100.0},
    {"AAA": 101.0},
    {"AAA": 102.5},  # 고점 형성
    {"AAA": 99.2},   # 고점 대비 약 -3% → trailing_stop 기대
]

def feed():
    for snap in prices:
        yield snap
        time.sleep(0.001)

if __name__ == "__main__":
    ht = HubTrade(
        symbols=["AAA"],
        exit_rules=ExitRules(),  # 기본 파라미터 사용 (클래스 시그니처에 맞춤)
    )
    ht.run_session(price_feed_iter=feed(), max_ticks=10)
