from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter

class Hub:
    def __init__(self, scorer: ScoreEngine, risk: RiskGate, router: OrderRouter, bus=None):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.bus = bus  # (옵션)

    def on_tick(self, snapshot):
        score = self.scorer.evaluate(snapshot)
        decision = self.risk.apply(score, snapshot)
        self.router.route(decision)
        return decision
