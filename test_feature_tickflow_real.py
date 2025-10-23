from scoring.features.tickflow import tick_flow

print("ratio50_50", tick_flow({"buy_vol":100, "sell_vol":100}))     # 0.0
print("ratio70_30", tick_flow({"buy_vol":70,  "sell_vol":30}))      # +0.4
print("ratio30_70", tick_flow({"buy_vol":30,  "sell_vol":70}))      # -0.4
print("from_prints", tick_flow({"prints":[
    {"side":"BUY","size":3},{"side":"SELL","size":1},{"side":"BUY","size":1}
]}))  # (4-1)/5 = +0.6
print("zero_tot", tick_flow({"buy_vol":0,"sell_vol":0}))            # 0.0
