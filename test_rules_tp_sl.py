from scoring.rules.take_profit import should_take_profit
from scoring.rules.stop_loss import should_stop_loss

pos = {"qty":1, "avg_price":100}
print("TP_false", should_take_profit(pos, 102))   # False (3% 미만)
print("TP_true",  should_take_profit(pos, 103))   # True  (+3%)
print("SL_false", should_stop_loss(pos, 99))      # False (2% 미만)
print("SL_true",  should_stop_loss(pos, 98))      # True  (-2% 이하)
