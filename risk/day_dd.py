# -*- coding: utf-8 -*-
"""
risk/day_dd.py — DayDrawdownPolicy 실거래 설정용 팩토리

역할:
- risk/policies/day_dd_policy 의 DayDrawdownPolicy 를
  실거래 기본 파라미터(-2% / -1% / 15분 / 0.4)로 감싸서 제공
- RiskGate 에서 자동 주입됨 (make_daydd)
"""

from __future__ import annotations
from risk.policies.day_dd_policy import DayDrawdownPolicy, DayDDParams


# ===================== 실거래용 파라미터 세트 =====================
PROD_DAYDD = DayDDParams(
    limit_pct=-2.0,     # 하루 누적 손익률이 -2% 이하 → 하드 컷 (진입 금지 + 쿨다운 시작)
    soft_pct=-1.0,      # 하루 손익률이 -1% 이하부터는 축소 진입
    cool_minutes=15,    # 하드컷 후 15분 동안 신규 진입 차단 (쿨다운)
    scale_min=0.40,     # 소프트 구간 하단에서는 최소 40% 비율만 진입 허용
)


# ===================== 팩토리 함수 =====================
def make_daydd() -> DayDrawdownPolicy:
    """실거래용 기본 파라미터로 DayDrawdownPolicy 생성"""
    return DayDrawdownPolicy(PROD_DAYDD)
