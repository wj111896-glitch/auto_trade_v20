from risk.core import RiskGate
from scoring.weights import Weights

rg = RiskGate(Weights())  # 기본 임계값: buy 0.7 / sell -0.7

# 1) 익절: 평균 100, 가격 103(+3%) -> SELL(take_profit)
pos = {"qty":1, "avg_price":100}
print("TP:", rg.apply(0.0, {"symbol":"AAA","price":103,"position":pos}))

# 2) 손절: 평균 100, 가격 98(-2%) -> SELL(stop_loss)
print("SL:", rg.apply(0.0, {"symbol":"BBB","price":98,"position":pos}))

# 3) 트레일링: 101→103(고점 형성)→100.9(약 2% 하락) -> SELL(trailing_stop)
print("TR up1:", rg.apply(0.0, {"symbol":"CCC","price":101,"position":pos}))
print("TR up2:", rg.apply(0.0, {"symbol":"CCC","price":103,"position":pos}))
print("TR hit:", rg.apply(0.0, {"symbol":"CCC","price":100.9,"position":pos}))
