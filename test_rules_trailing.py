from scoring.rules.trailing import trailing_exit

peak=None
sig, peak = trailing_exit({"qty":1,"avg_price":100}, 101, peak, 0.02); print("up", sig, peak)   # False, 101
sig, peak = trailing_exit({"qty":1,"avg_price":100}, 103, peak, 0.02); print("up2", sig, peak)  # False, 103
sig, peak = trailing_exit({"qty":1,"avg_price":100}, 101, peak, 0.02); print("down", sig, peak) # False, 103 (2% 미만)
sig, peak = trailing_exit({"qty":1,"avg_price":100}, 100.9, peak, 0.02); print("trigger", sig, peak) # True, 103 (약 2%↓)
