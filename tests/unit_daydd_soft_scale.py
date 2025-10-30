# -*- coding: utf-8 -*-
import os, sys

# 프로젝트 루트를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from risk.policies.day_dd import DayDrawdownPolicy, DayDDParams

policy = DayDrawdownPolicy(DayDDParams(
    limit_pct=-0.60,
    soft_pct=-0.30,
    cool_minutes=1,
    scale_min=0.30,
))

portfolio = {}
planned = 2000

def try_scale(pct):
    ctx = {"today_pnl_pct": pct, "planned_qty": planned}
    # 진입 허용 여부
    r = policy.check_entry("005930", 10.0, portfolio, ctx)
    # 축소 수량 힌트
    q = policy.size_hint("005930", 10.0, portfolio, ctx)
    print(f"[{pct:+.2f}%] allow={r.allow:5} reason={r.reason:20} "
          f"planned={planned} -> sized={q if q is not None else 'None'}")

# 소프트 시작(-0.30%), 중간(-0.45%), 하드컷 직전(-0.59%), 하드컷 이하(-0.60%)
for pct in (-0.30, -0.45, -0.59, -0.60):
    try_scale(pct)
