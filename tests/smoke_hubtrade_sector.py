# -*- coding: utf-8 -*-
"""
smoke_hubtrade_sector.py
- ScoreEngine → RiskGate(SectorCap 포함) → OrderRouter 순 통합 스모크
- 케이스1: 섹터 초과 → BUY 차단
- 케이스2: 섹터 여유 → BUY 발생
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

# === 주입 대상 ===
from risk.core import RiskGate
from risk.policies.sector_cap import SectorCapPolicy, SectorParams

# ---- 더미 구성요소 (테스트용) ----
class DummyScoreEngine:
    def score(self, snapshot: Dict[str, Any]) -> float:
        # 대상 심볼은 항상 매수 점수(+0.8)로 가정
        target = snapshot.get("symbol")
        return 0.8 if target in {"GOOG", "MSFT"} else 0.0

class DummyOrderRouter:
    def __init__(self):
        self.orders: List[Dict[str, Any]] = []

    def buy(self, symbol: str, qty: int, order_type="MKT", price=None, tag=""):
        self.orders.append({"action": "BUY", "symbol": symbol, "qty": qty, "order_type": order_type, "price": price, "tag": tag})

# ---- 허브: HubTrade 있으면 사용, 없으면 로컬 허브로 대체 ----
def make_hub(score_engine, risk_gate, router):
    try:
        # 프로젝트 허브 시그니처가 다를 수 있으므로, 주입 가능한 경우만 사용
        from hub.hub_trade import Hub  # or HubTrade
        # Hub가 존재하면 생성자에 주입 (프로젝트 구현에 맞춰 아래 중 택1)
        try:
            return Hub(scoring=score_engine, risk=risk_gate, router=router)
        except TypeError:
            # 다른 시그니처 대비
            return Hub(score_engine, risk_gate, router)
    except Exception:
        # 로컬 최소 허브
        class LocalHub:
            def __init__(self, scorer, risk, router):
                self.scorer = scorer
                self.risk = risk
                self.router = router

            def on_tick(self, snapshot: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None):
                sym = snapshot["symbol"]
                price = float(snapshot["price"])
                portfolio = snapshot.get("_portfolio", {})
                score = self.scorer.score(snapshot)
                if score <= 0:
                    return

                allow, reason, hint = self.risk.check(sym, price, portfolio, ctx or {})
                if allow:
                    qty = hint if (hint is not None and hint > 0) else 1
                    if qty > 0:
                        self.router.buy(sym, qty, order_type="MKT", price=None, tag="smoke")
                else:
                    # 차단 로그 대체
                    # print(f"[BLOCK] {sym} {reason}")
                    pass

        return LocalHub(score_engine, risk_gate, router)

# ---- 공통 RiskGate 생성 (SectorCap 강제 주입) ----
def make_gate_with_sector(max_pct=0.35, budget=3_000_000):
    gate = RiskGate(policies=None)
    gate.policies.append(SectorCapPolicy(SectorParams(sector_cap_pct=max_pct, budget=budget)))
    return gate

# ========== 테스트 ==========

def test_block_when_sector_over_cap():
    scorer = DummyScoreEngine()
    router = DummyOrderRouter()
    gate = make_gate_with_sector(0.35, 3_000_000)
    hub = make_hub(scorer, gate, router)

    snapshot = {"symbol": "GOOG", "price": 100_000.0, "_portfolio": {}}
    ctx = {
        "budget": 3_000_000,
        "symbol_sector": {"GOOG": "IT"},
        "sector_exposure": {"IT": 2_000_000},  # 66.7% > 35%
    }

    hub.on_tick(snapshot, ctx)
    assert len(router.orders) == 0, "섹터 초과인데 BUY가 나오면 안 됨"

def test_allow_when_sector_under_cap():
    scorer = DummyScoreEngine()
    router = DummyOrderRouter()
    gate = make_gate_with_sector(0.35, 3_000_000)
    hub = make_hub(scorer, gate, router)

    snapshot = {"symbol": "MSFT", "price": 50_000.0, "_portfolio": {}}
    ctx = {
        "budget": 3_000_000,
        "symbol_sector": {"MSFT": "IT"},
        "sector_exposure": {"IT": 900_000},  # 30% < 35%
    }

    hub.on_tick(snapshot, ctx)
    assert len(router.orders) == 1, "섹터 여유면 최소 1건 BUY가 발생해야 함"
    assert router.orders[0]["symbol"] == "MSFT"

def test_size_hint_respected_when_under_cap():
    scorer = DummyScoreEngine()
    router = DummyOrderRouter()
    gate = make_gate_with_sector(0.35, 3_000_000)
    hub = make_hub(scorer, gate, router)

    # cap = 1,050,000 / current 900,000 → remaining 150,000
    # price 30,000 → hint = 5
    snapshot = {"symbol": "MSFT", "price": 30_000.0, "_portfolio": {}}
    ctx = {
        "budget": 3_000_000,
        "symbol_sector": {"MSFT": "IT"},
        "sector_exposure": {"IT": 900_000},
    }

    hub.on_tick(snapshot, ctx)
    assert len(router.orders) == 1
    assert router.orders[0]["qty"] == 5, "size_hint(=5)이 반영되어야 함"
