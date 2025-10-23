from scoring.features.ta import ma_cross
print("gt", ma_cross({"fast": 12, "slow": 10}))  # +1.0
print("lt", ma_cross({"fast":  8, "slow": 10}))  # -1.0
print("eq", ma_cross({"fast": 10, "slow": 10}))  # 0.0
print("na", ma_cross({}))                        # 0.0
