from risk.core import RiskGate
from scoring.weights import Weights

rg = RiskGate(Weights())

print(rg.apply( 1.0, {"symbol":"AAA"}))   # BUY 예상
print(rg.apply(-1.0, {"symbol":"BBB"}))   # SELL 예상
print(rg.apply( 0.0, {"symbol":"CCC"}))   # 대기(None) 예상
