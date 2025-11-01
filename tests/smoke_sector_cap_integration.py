# -*- coding: utf-8 -*-
"""
smoke_sector_cap_integration.py
- RiskGate 기본 정책(Exposure + DayDD + SectorCap) 주입 가정
- Hub 호환 인터페이스 check(symbol, price, portfolio, ctx)로 통합 검증
"""
from risk.core import RiskGate
from risk.policies.sector_cap import SectorParams, SectorCapPolicy

def make_gate_with_sector(max_pct=0.35):
    """DayDD/Exposure는 RiskGate 기본값을 사용하고, SectorCap만 확실히 주입"""
    # RiskGate(None)으로 만들면 DayDD/Exposure는 기본 주입되지만,
    # 테스트 확실성을 위해 policies 리스트를 명시 구성해도 됨.
    gate = RiskGate(policies=None)
    # 이미 SectorCap이 기본 주입돼 있다면 중복 주입을 피하고 싶으면 주석 처리 가능
    gate.policies.append(SectorCapPolicy(SectorParams(sector_cap_pct=max_pct, budget=3_000_000)))
    return gate

def test_block_when_sector_over_cap():
    gate = make_gate_with_sector(0.35)  # 35%
    portfolio = {
        # 예시: 현재 보유 포지션(섹터/평가금액) — Hub에서는 ctx로 노출 합산을 쓰므로 여기선 참고용
        "AAA": {"sector": "IT", "qty": 10, "value": 1_200_000},
        "BBB": {"sector": "IT", "qty": 5,  "value":   800_000},
        "CCC": {"sector": "FIN","qty": 3,  "value":   300_000},
    }
    ctx = {
        "budget": 3_000_000,
        # 심볼-섹터 맵
        "symbol_sector": {"GOOG": "IT", "AAA": "IT", "BBB": "IT", "CCC": "FIN"},
        # 섹터별 현재 노출 합계(허브에서 계산해 넣어주는 값)
        "sector_exposure": {"IT": 2_000_000, "FIN": 300_000},
    }
    allow, reason, hint = gate.check("GOOG", price=100_000, portfolio=portfolio, ctx=ctx)
    print("BLOCK →", allow, reason, hint)
    assert allow is False
    assert "sector_cap" in reason

def test_allow_when_sector_under_cap():
    gate = make_gate_with_sector(0.35)  # 35%
    portfolio = {}
    ctx = {
        "budget": 3_000_000,
        "symbol_sector": {"MSFT": "IT"},
        "sector_exposure": {"IT": 900_000},  # 30% 노출
    }
    allow, reason, hint = gate.check("MSFT", price=100_000, portfolio=portfolio, ctx=ctx)
    print("ALLOW →", allow, reason, hint)
    assert allow is True
    assert "ok" in reason or "IT" in reason  # ok:IT:... 형태

def test_size_hint_uses_remaining_room():
    gate = make_gate_with_sector(0.35)  # 35%
    portfolio = {}
    ctx = {
        "budget": 3_000_000,                         # 총자산
        "symbol_sector": {"AAPL": "IT"},
        "sector_exposure": {"IT": 900_000},          # 현재 900k (30%)
    }
    # cap = 3,000,000 * 0.35 = 1,050,000
    # remaining = 1,050,000 - 900,000 = 150,000 → price 50,000이면 3주 힌트
    allow, reason, hint = gate.check("AAPL", price=50_000, portfolio=portfolio, ctx=ctx)
    print("HINT →", allow, reason, hint)
    assert allow is True
    assert hint == 3
