from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter
from obs.log import info  # ← 추가: 로깅

class Hub:
    def __init__(self, scorer: ScoreEngine, risk: RiskGate, router: OrderRouter, bus=None):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.bus = bus
        info("HUB init: scorer=%s risk=%s router=%s", type(scorer).__name__, type(risk).__name__, type(router).__name__)

    def on_tick(self, snapshot):
        sym = snapshot.get("symbol", "NA")
        price = snapshot.get("price", None)
        info("HUB on_tick: symbol=%s price=%s", sym, price)

        score = self.scorer.evaluate(snapshot)
        info("HUB score: %.3f", score)

        decision = self.risk.apply(score, snapshot)
        info("HUB decision: %s", decision)

        self.router.route(decision)
        return decision
