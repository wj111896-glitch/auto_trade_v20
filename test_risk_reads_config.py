from risk.core import RiskGate
from scoring.weights import Weights
from common.config import TP_PCT, SL_PCT, TRAIL_PCT

rg = RiskGate(Weights())

print("CFG:", TP_PCT, SL_PCT, TRAIL_PCT)

# TP_PCT 적용(기본 3%): avg 100 → 103 → SELL(take_profit)
print("TP:", rg.apply(0.0, {"symbol":"AAA","price":100*(1+TP_PCT), "position":{"qty":1,"avg_price":100}}))

# SL_PCT 적용(기본 2%): avg 100 → 98 → SELL(stop_loss)
print("SL:", rg.apply(0.0, {"symbol":"BBB","price":100*(1-SL_PCT), "position":{"qty":1,"avg_price":100}}))

# TRAIL_PCT 적용(기본 2%): 고점 갱신 후 TRAIL_PCT만큼 하락 시 SELL(trailing_stop)
pos = {"qty":1,"avg_price":102}   # 익절 먼저 안 걸리도록 avg 조정
print("TR up:", rg.apply(0.0, {"symbol":"CCC","price":103,"position":pos}))
trail_hit_price = 103*(1-TRAIL_PCT)
print("TR hit:", rg.apply(0.0, {"symbol":"CCC","price":trail_hit_price,"position":pos}))
