# -*- coding: utf-8 -*-
"""
hub/hub_trade.py - 전략 허브 (단일/멀티 심볼 공용)
시세 스냅샷(snapshot)을 받아 점수 → 리스크 → 의사결정 → 주문 실행까지 연결
"""
from __future__ import annotations
from typing import Dict, Any

from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter
from obs.log import get_logger


class Hub:
    """전략 허브 (단일 심볼/멀티 심볼 공용)

    흐름:
        on_tick(snapshot)
          → ScoreEngine.evaluate()
          → RiskGate.apply()
          → router.route(decision)

    decision 포맷(권장):
        {
            "action": "BUY" | "SELL" | "HOLD",
            "symbol": "005930",
            "qty": 10,
            "order_type": "MKT" | "LMT",
            "price": None or float,
            "tag": "optional-user-tag"
        }
    """

    def __init__(self, scorer: ScoreEngine, risk: RiskGate, router: OrderRouter):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.log = get_logger("hub")

        self.log.info(
            "HUB init: scorer=%s risk=%s router=%s",
            type(scorer).__name__,
            type(risk).__name__,
            type(router).__name__,
        )

    def on_tick(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """하나의 틱 데이터를 받아 스코어링, 리스크 판단, 주문 실행"""
        sym = snapshot.get("symbol", "NA")
        price = snapshot.get("price")
        self.log.info("HUB on_tick: symbol=%s price=%s", sym, price)

        # ① 스코어 평가
        score = self.scorer.evaluate(snapshot)
        self.log.info("HUB score: %.3f", score)

        # ② 리스크 적용 → 의사결정 딕셔너리
        decision = self.risk.apply(score, snapshot)

        # 문자열로만 오는 경우 (예: "HOLD")
        if isinstance(decision, str):
            decision = {
                "action": decision,
                "symbol": sym,
                "qty": 0,
                "order_type": "MKT",
                "price": None,
            }

        self.log.info("HUB decision: %s", decision)

        # ③ 주문 라우팅
        routed = self.router.route(decision)
        if routed is not None:
            decision = {**decision, "route_result": routed}

        return decision


# =========================
# 단독 실행 테스트 (DRY_RUN)
# =========================
if __name__ == "__main__":
    from common import config

    # 더미 클래스 정의 (실제 엔진 대신)
    class DummyScorer(ScoreEngine):
        def evaluate(self, snapshot):
            return 1.0 if snapshot.get("price", 0) <= 10 else -1.0

    class DummyRisk(RiskGate):
        def apply(self, score, snapshot):
            sym = snapshot.get("symbol", "NA")
            if score > 0:
                return {
                    "action": "BUY",
                    "symbol": sym,
                    "qty": 1,
                    "order_type": "MKT",
                    "price": None,
                    "tag": "smoke",
                }
            return {"action": "HOLD", "symbol": sym, "qty": 0}

    # DRY_RUN 설정
    config.BROKER = "KIWOOM"
    config.DRY_RUN = True
    config.ACCOUNT_NO = "00000000"

    # 허브 초기화 및 테스트
    hub = Hub(DummyScorer(), DummyRisk(), OrderRouter(get_logger("router")))
    assert hub.router.connect()
    result = hub.on_tick({"symbol": "005930", "price": 10.0})
    print("decision_out:", result)

