# -*- coding: utf-8 -*-
"""
hub/hub_trade.py - 전략 허브 (단일/멀티 심볼 공용)
시세 스냅샷(snapshot)을 받아 점수 → 리스크 → 주문 실행(진입/청산)까지 연결
ExitRules(익절/손절/트레일링)를 우선 평가 후 신규 진입 로직 수행
"""
from __future__ import annotations

# ==== ① 경로 자동 세팅 ====
import os, sys, time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from obs.log import get_logger
from scoring.core import ScoreEngine
from scoring.rules.exit_rules import ExitRules, ExitParams
from risk.core import RiskGate
from order.router import OrderRouter


__all__ = ["Hub", "HubTrade"]


# =========================
# Hub 본체
# =========================
class Hub:
    """
    단일 허브: 보유 포지션이 있으면 ExitRules를 우선 평가, 없으면 신규 진입 판단.
    portfolio 포맷: {"SYM": {"qty": int, "avg_price": float, "mtm_price": float}}
    """

    def __init__(
        self,
        scorer: ScoreEngine,
        risk: RiskGate,
        router: OrderRouter,
        exit_rules: Optional[ExitRules] = None,
        log=None,
    ):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.exit_rules = exit_rules or ExitRules(ExitParams())
        self.log = log or get_logger("hub")
        self.portfolio: Dict[str, Dict[str, float]] = {}  # qty/avg_price/mtm_price

    # --- 내부 유틸 ---
    def _get_pos(self, sym: str) -> Dict[str, float]:
        return self.portfolio.get(sym, {"qty": 0, "avg_price": 0.0, "mtm_price": 0.0})

    def _set_pos(self, sym: str, qty: int, avg_price: float, mtm_price: float) -> None:
        self.portfolio[sym] = {"qty": int(qty), "avg_price": float(avg_price), "mtm_price": float(mtm_price)}

    def _apply_fill_buy(self, sym: str, qty: int, price: float) -> None:
        pos = self._get_pos(sym)
        old_qty = int(pos["qty"])
        old_avg = float(pos["avg_price"])
        new_qty = old_qty + int(qty)
        new_avg = ((old_avg * old_qty) + (price * qty)) / max(1, new_qty)
        self._set_pos(sym, new_qty, new_avg, price)

    def _apply_fill_sell(self, sym: str, qty: int, price: float) -> None:
        pos = self._get_pos(sym)
        new_qty = max(0, int(pos["qty"]) - int(qty))
        new_avg = 0.0 if new_qty == 0 else float(pos["avg_price"])
        self._set_pos(sym, new_qty, new_avg, price)

    def _route_buy(self, sym: str, qty: int, price: float, reason: str) -> None:
        if hasattr(self.router, "buy"):
            self.router.buy(sym, qty=qty, price=price, reason=reason)
        else:
            self.router.route({"action": "BUY", "symbol": sym, "qty": qty, "price": price, "reason": reason})
        self._apply_fill_buy(sym, qty, price)

    def _route_sell(self, sym: str, qty: int, price: float, reason: str) -> None:
        if qty <= 0:
            return
        if hasattr(self.router, "sell"):
            self.router.sell(sym, qty=qty, price=price, reason=reason)
        else:
            self.router.route({"action": "SELL", "symbol": sym, "qty": qty, "price": price, "reason": reason})
        self._apply_fill_sell(sym, qty, price)

    def _decide_qty(self, sym: str, price: float, score: float, size_hint: Optional[int]) -> int:
        """
        아주 단순한 기본 사이저:
        - size_hint가 있으면 그 값을 상한으로 사용
        - score가 양수면 1주(또는 size_hint) 진입, 0/음수면 0
        """
        base = 1 if score > 0 else 0
        if size_hint is None:
            return base
        return min(max(0, base), int(size_hint))

    # --- 메인 틱 처리 ---
    def on_tick(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sym = str(snapshot.get("symbol"))
        price = float(snapshot.get("price") or 0.0)

        # 포지션 MTM 반영
        pos = self._get_pos(sym)
        if pos["qty"] > 0:
            pos["mtm_price"] = price
            self.portfolio[sym] = pos

        # 1) Exit 우선 평가 (보유중일 때)
        if pos["qty"] > 0:
            entry = float(pos["avg_price"] or pos["mtm_price"] or price)
            ctx = snapshot.get("ctx") or {}
            r = self.exit_rules.apply_exit(sym, entry_price=entry, current_price=price, ctx=ctx)
            if r.exit:
                self.log.info(f"[EXIT] {sym} {r.reason} pnl={'' if r.pnl_pct is None else f'{r.pnl_pct:.2%}'}")
                self._route_sell(sym, qty=int(pos["qty"]), price=price, reason=r.reason)
                return {"action": "SELL", "symbol": sym, "qty": int(pos["qty"]), "price": price, "reason": r.reason}

        # 2) 신규 진입 판단
        # 점수 계산: 구현마다 시그니처가 달라서 순차 폴백
        sc_ctx = snapshot.get("ctx") or {}
        try:
            # 케이스 A: score(snapshot)
            score = float(self.scorer.score(snapshot))
        except TypeError:
            try:
                # 케이스 B: score(sym, price, ctx)
                score = float(self.scorer.score(sym, price, sc_ctx))
            except TypeError:
                # 케이스 C: evaluate(snapshot)
                score = float(self.scorer.evaluate(snapshot))
        except AttributeError:
            # score가 없으면 evaluate로
            try:
                score = float(self.scorer.evaluate(snapshot))
            except Exception:
                score = 0.0

      
        # 리스크 체크
        allow, reason, size_hint = self.risk.check(sym, price, self.portfolio, snapshot.get("ctx") or {})
        if not allow:
            self.log.debug(f"[BLOCK] {sym} by RiskGate: {reason}")
            return {"action": "HOLD", "symbol": sym, "qty": 0, "price": price, "reason": f"risk:{reason}"}

        qty = self._decide_qty(sym, price, score, size_hint)
        if qty > 0:
            why = f"score={score:.3f}"
            self._route_buy(sym, qty=qty, price=price, reason=why)
            return {"action": "BUY", "symbol": sym, "qty": qty, "price": price, "reason": why}

        return {"action": "HOLD", "symbol": sym, "qty": 0, "price": price, "reason": "no_signal"}


# =========================
# HubTrade 러너(목업용)
# =========================
@dataclass
class _RunnerOpts:
    real_mode: bool = False
    budget: Optional[float] = None
    note: str = ""


class HubTrade:
    """
    간단 러너: mock feed를 사용해 Hub를 구동
    """
    def __init__(self, real_mode: bool = False, budget: Optional[float] = None, **kwargs):
        self.log = get_logger("hubtrade")
        self.opts = _RunnerOpts(real_mode=real_mode, budget=budget, note=kwargs.get("note", ""))

        scorer, risk = self._make_scorer_risk()
        router = self._make_router()
        self.hub = Hub(scorer, risk, router)

    def _make_scorer_risk(self) -> Tuple[ScoreEngine, RiskGate]:
        # Scorer
        try:
            scorer = ScoreEngine(logger=get_logger("scorer"))
        except Exception:
            class _DummyScorer(ScoreEngine):
                def score(self, sym, price, ctx):  # 항상 매수 유도
                    return 1.0
            scorer = _DummyScorer()

        # Risk
        try:
            risk = RiskGate()
        except Exception:
            class _DummyRisk(RiskGate):
                def check(self, sym, price, portfolio, ctx):
                    return True, "ok", None
            risk = _DummyRisk()

        return scorer, risk

    def _make_router(self) -> OrderRouter:
        try:
            router = OrderRouter(get_logger("router"))
        except Exception:
            class _DummyRouter:
                def __init__(self): self.log = get_logger("router")
                def buy(self, sym, qty, price, reason=""): self.log.info(f"[BUY] {sym} x{qty} @ {price} ({reason})")
                def sell(self, sym, qty, price, reason=""): self.log.info(f"[SELL]{sym} x{qty} @ {price} ({reason})")
            router = _DummyRouter()  # type: ignore
        return router

    def _mock_snapshot(self, sym: str, tick: int) -> Dict[str, Any]:
        # 간단한 가격 패턴: 100 → 102(익절), 98(손절) 등 테스트용
        base = 100.0
        price = base + ((tick % 5) - 2) * 1.0
        return {"symbol": sym, "price": price, "ctx": {"account": {"equity": 3_000_000}}}

    def run_session(self, symbols: List[str], max_ticks: int) -> Dict[str, Any]:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log.info("run_session start: symbols=%s max_ticks=%s", symbols, max_ticks)

        ticks = 0
        decisions: List[Dict[str, Any]] = []

        while ticks < max_ticks:
            for sym in symbols:
                snap = self._mock_snapshot(sym, ticks)
                decision = self.hub.on_tick(snap)
                decisions.append(decision)
                ticks += 1
                if ticks >= max_ticks:
                    break
            time.sleep(0.001)

        self.log.info("run_session end: ticks=%s started=%s", ticks, started)
        return {"status": "ok", "ticks": ticks, "symbols": symbols, "decisions": decisions[-10:]}


if __name__ == "__main__":
    hubtrade = HubTrade(real_mode=False, budget=1_000_000)
    out = hubtrade.run_session(["005930"], max_ticks=10)
    print("decision_out(last10):", out.get("decisions"))
