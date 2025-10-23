from scoring.features.volume import volume_surge
print("case1", volume_surge({"curr_vol":1000,"avg_vol":1000}))   # 0.0
print("case2", volume_surge({"curr_vol":2000,"avg_vol":1000}))   # 1.0 (clip)
print("case3", volume_surge({"curr_vol":500,"avg_vol":1000}))    # -0.5
print("case4", volume_surge({"curr_vol":0,"avg_vol":0}))         # 0.0 (guard)
