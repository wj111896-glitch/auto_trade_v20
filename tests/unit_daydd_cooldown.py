# tests/unit_daydd_cooldown.py
# -*- coding: utf-8 -*-
import os, sys, time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from risk.policies.day_dd import DayDrawdownPolicy, DayDDParams

policy = DayDrawdownPolicy(DayDDParams(
    limit_pct=-2.0,   # 하드컷
    soft_pct=-1.0,    # 소프트 시작
    cool_minutes=15,    # 1분 쿨다운
    scale_min=0.30,
))

portfolio = {}

# t0: 하드컷 발동
t0 = time.time()
ctx1 = {"today_pnl_pct": -0.70, "now_ts": t0}
r1 = policy.check_entry("005930", 10.0, portfolio, ctx1)
print("[t0]     ", r1.allow, r1.reason, "dd_block_until_ts:", ctx1.get("dd_block_until_ts"))

# ⬇️ 다음 호출들에 쿨다운 만료시각을 넘겨줍니다
dd_until = ctx1.get("dd_block_until_ts")

# t0+30s: 아직 쿨다운 유지 → allow=False
ctx2 = {"today_pnl_pct": -0.10, "now_ts": t0 + 30, "dd_block_until_ts": dd_until}
r2 = policy.check_entry("005930", 10.0, portfolio, ctx2)
print("[t0+30s] ", r2.allow, r2.reason)

# t0+70s: 쿨다운 해제 → allow=True
ctx3 = {"today_pnl_pct": -0.10, "now_ts": t0 + 70, "dd_block_until_ts": dd_until}
r3 = policy.check_entry("005930", 10.0, portfolio, ctx3)
print("[t0+70s] ", r3.allow, r3.reason)
