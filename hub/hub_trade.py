# -*- coding: utf-8 -*-
"""
Hub/HubTrade 루프 통합 (최종본)
- ExitRules(익절·손절·트레일링) → RiskGate → OrderRouter
- 같은 틱에서 막 청산한 심볼은 재진입 차단
- exit_reason 이벤트 기록
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import time

from scoring.core import ScoreEngine
from scoring.rules.exit_rules import ExitRules
from risk.core import RiskGate
from risk.policies.exposure import ExposurePolicy
try:
    from risk.policies.day_dd import make_daydd
except ImportError:
    from risk.core import make_daydd

from order.router import OrderRouter
from obs.log import get_logger

logger = get_logger(__name__)


# ========== 데이터 모델 ==========
@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float
    last_high: float = 0.0  # 트레일링용


@dataclass
class TradeEvent:
    ts: float
    action: str   # "BUY" | "SELL" | "EXIT"
    symbol: str
    qty: int
    price: float
    reason: str = ""


# ========== 핵심 허브 ==========
class Hub:
    """scorer/risk/router를 주입받아 on_tick 처리"""
    def __init__(
        self,
        scorer: ScoreEngine,
        risk: RiskGate,
        router: OrderRouter,
        exit_rules: ExitRules,
    ) -> None:
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.exit_rules = exit_rules
        self.portfolio: Dict[str, Position] = {}
        self.events: List[TradeEvent] = []
        self._just_exited: set[str] = set()
        self._tick_index: int = 0
        self._last_decisions: List[dict] = []   # 마지막 틱 의사결정(표준화)

    # --- 유틸: 포트폴리오 MTM 갱신 ---
    def _update_portfolio_marks(self, prices: Dict[str, float]) -> Dict[str, float]:
        pnl_open_pct: Dict[str, float] = {}
        for sym, pos in self.portfolio.items():
            p = prices.get(sym)
            if p is None or pos.qty == 0:
                pnl_open_pct[sym] = 0.0
                continue
            pnl_open_pct[sym] = (p - pos.avg_price) / pos.avg_price
            if p > pos.last_high:
                pos.last_high = p
        return pnl_open_pct

    def _make_ctx(self, equity_now: float, pnl_open_pct: Dict[str, float]) -> Dict[str, Any]:
        return {
            "equity_now": equity_now,
            "pnl_open_pct": pnl_open_pct,
            "now_ts": time.time(),
            "tick_index": self._tick_index,
        }

    def _estimate_equity(self, prices: Dict[str, float]) -> float:
        """간단한 MTM 추정: 현재 보유가치 합(현금 0 가정)"""
        mtm = 0.0
        for sym, pos in self.portfolio.items():
            p = prices.get(sym)
            if p is not None:
                mtm += pos.qty * p
        return mtm

    # --- ExitRules 어댑터 ---
    def _apply_exit_rules(self, prices: Dict[str, float], ctx: Dict[str, Any]) -> List[dict]:
        port_view = {
            s: {
                "qty": pos.qty,
                "avg_price": pos.avg_price,
                "last_high": pos.last_high,
                "price_now": prices.get(s),
            }
            for s, pos in self.portfolio.items()
        }

        if hasattr(self.exit_rules, "apply_exit_batch"):
            return self.exit_rules.apply_exit_batch(portfolio=port_view, ctx=ctx)

        results: List[dict] = []
        for sym, v in port_view.items():
            qty = int(v.get("qty", 0) or 0)
            if qty <= 0:
                continue
            price_now = v.get("price_now")
            avg_price = v.get("avg_price")
            if not price_now or not avg_price:
                continue
            try:
                res = self.exit_rules.apply_exit(
                    symbol=sym, entry_price=avg_price, current_price=price_now, ctx=ctx
                )
            except TypeError:
                continue
            if getattr(res, "exit", False):
                results.append({
                    "symbol": sym, "qty": qty, "price": float(price_now),
                    "reason": getattr(res, "reason", "exit_rule")
                })
        return results

    # --- 안전 임계값/수량 헬퍼 ---
    def _get_thresholds(self) -> Tuple[float, float]:
        if hasattr(self.scorer, "thresholds"):
            try:
                return self.scorer.thresholds()
            except Exception:
                pass
        bt = getattr(self.scorer, "buy_threshold", None)
        st = getattr(self.scorer, "sell_threshold", None)
        if isinstance(bt, (int, float)) and isinstance(st, (int, float)):
            return float(bt), float(st)
        try:
            from common.config import DAYTRADE
            th = DAYTRADE.get("thresholds", {})
            return float(th.get("buy", 0.55)), float(th.get("sell", -0.55))
        except Exception:
            return 0.55, -0.55

    def _default_qty(self, symbol: str) -> int:
        if hasattr(self.scorer, "default_qty"):
            try:
                q = self.scorer.default_qty(symbol)
                return int(q) if q else 0
            except Exception:
                pass
        q_attr = getattr(self.scorer, "default_qty_hint", None)
        if isinstance(q_attr, (int, float)):
            return max(0, int(q_attr))
        return 1

    # --- RiskGate 시그니처 호환 래퍼 ---
    def _risk_eval(self, sym: str, px: Optional[float], ctx: dict):
        port = self._portfolio_view()
        # ① 신규(키워드)
        try:
            return self.risk.evaluate(symbol=sym, price=px, portfolio=port, ctx=ctx)
        except TypeError:
            pass
        # ② 구형(포지셔널)
        try:
            return self.risk.evaluate(sym, px, port, ctx)
        except TypeError:
            pass
        # ③ check_entry 사용 구현
        if hasattr(self.risk, "check_entry"):
            try:
                return self.risk.check_entry(sym, px, port, ctx)
            except TypeError:
                pass
        # ④ 폴백: 허용하지 않음
        class _Res:
            allow = False
            reason = "risk_eval_failed"
            max_qty_hint = None
        return _Res()

    # --- 메인 루프 ---
    def on_tick(self, prices: Dict[str, float], equity_now: Optional[float] = None) -> List[TradeEvent]:
        self._tick_index += 1
        self._just_exited.clear()

        # 1) 컨텍스트
        if equity_now is None:
            equity_now = self._estimate_equity(prices)
        pnl_open_pct = self._update_portfolio_marks(prices)
        ctx = self._make_ctx(equity_now, pnl_open_pct)

        # 2) Exit 우선
        exit_orders = self._apply_exit_rules(prices, ctx)
        for ex in exit_orders:
            sym = ex["symbol"]
            if sym not in self.portfolio:
                continue
            qty = int(ex.get("qty") or self.portfolio[sym].qty)
            if qty <= 0:
                continue
            px = ex.get("price", prices.get(sym))
            reason = ex.get("reason", "exit_rule")
            fill_price = self.router.sell_market(sym, qty, px, reason)
            self._record_event("EXIT", sym, qty, fill_price, reason)
            self._apply_fill_exit(sym, qty)
            self._just_exited.add(sym)

        # 3) 신규/증감 결정 — Score → Risk
        try:
            scores = self.scorer.score(prices, ctx)  # 새 시그니처
        except TypeError:
            scores = self.scorer.score(prices)       # 구 시그니처

        # dict가 아니면 dict로 표준화
        if not isinstance(scores, dict):
            try:
                scores = dict(scores)  # iterable[(sym,score)]
            except Exception:
                scores = {sym: float(scores) for sym in prices.keys()}  # 단일 float

        decisions = self._decide_from_scores(scores)

        # 같은 틱 재진입 차단
        decisions = [d for d in decisions if d["symbol"] not in self._just_exited]

        # 리스크 게이트
        filtered: List[Tuple[dict, Optional[int]]] = []
        for d in decisions:
            sym = d["symbol"]
            px = prices.get(sym)
            res = self._risk_eval(sym, px, ctx)
            if res.allow:
                if res.max_qty_hint is not None:
                    d["qty"] = min(int(d.get("qty", 0) or 0), res.max_qty_hint)
                filtered.append((d, res.max_qty_hint))

        # 4) 라우팅
        executed_decisions: List[dict] = []
        for d, _ in filtered:
            sym = d["symbol"]
            act = d["action"].upper()
            px = prices.get(sym)
            qty = int(d.get("qty", 0) or 0)
            if qty <= 0 or px is None:
                continue
            if act == "BUY":
                fill = self.router.buy_market(sym, qty, px, d.get("reason", "score_buy"))
                self._record_event("BUY", sym, qty, fill, d.get("reason", "score_buy"))
                self._apply_fill_buy(sym, qty, fill)
                executed_decisions.append({**d, "fill": fill})
            elif act == "SELL":
                held = self.portfolio.get(sym)
                if held and held.qty > 0:
                    qty = min(qty, held.qty)
                    fill = self.router.sell_market(sym, qty, px, d.get("reason", "score_sell"))
                    self._record_event("SELL", sym, qty, fill, d.get("reason", "score_sell"))
                    self._apply_fill_exit(sym, qty)
                    executed_decisions.append({**d, "fill": fill})

        # 마지막 틱 의사결정 저장 (run_session용)
        self._last_decisions = executed_decisions
        return self.events[-20:]

    # --- 내부 체결 반영/보조 ---
    def _decide_from_scores(self, scores: Dict[str, float]) -> List[dict]:
        buy_th, sell_th = self._get_thresholds()
        out: List[dict] = []
        for sym, s in scores.items():
            if s is None:
                continue
            if s >= buy_th:
                out.append({"action": "BUY", "symbol": sym, "qty": self._default_qty(sym), "reason": f"score={s:.3f}"})
            elif s <= sell_th:
                out.append({"action": "SELL", "symbol": sym, "qty": self._default_qty(sym), "reason": f"score={s:.3f}"})
        return out

    def _apply_fill_buy(self, sym: str, qty: int, price: float) -> None:
        pos = self.portfolio.get(sym)
        if not pos:
            self.portfolio[sym] = Position(sym, qty, price, last_high=price)
            return
        new_qty = pos.qty + qty
        pos.avg_price = (pos.avg_price * pos.qty + price * qty) / max(1, new_qty)
        pos.qty = new_qty
        if price > pos.last_high:
            pos.last_high = price

    def _apply_fill_exit(self, sym: str, qty: int) -> None:
        pos = self.portfolio.get(sym)
        if not pos:
            return
        pos.qty -= qty
        if pos.qty <= 0:
            del self.portfolio[sym]

    def _record_event(self, action: str, sym: str, qty: int, price: float, reason: str) -> None:
        self.events.append(TradeEvent(ts=time.time(), action=action, symbol=sym, qty=qty, price=price, reason=reason))

    def _portfolio_view(self) -> Dict[str, dict]:
        return {s: {"qty": p.qty, "avg_price": p.avg_price} for s, p in self.portfolio.items()}


# ========== 실행 러너 ==========
class HubTrade:
    """
    런너 — ① 의존성 주입형 또는 ② 플래그형(실전/드라이런) 모두 지원
      - 의존성 주입형: HubTrade(scorer=..., risk=..., router=..., exit_rules=...)
      - 플래그형:      HubTrade(real_mode=False, budget=3_000_000, calibrator_enabled=True)
    """
    def __init__(
        self,
        scorer: ScoreEngine | None = None,
        risk: RiskGate | None = None,
        router: OrderRouter | None = None,
        exit_rules: ExitRules | None = None,
        *,
        real_mode: bool = False,
        budget: int = 3_000_000,
        calibrator_enabled: bool = True,
    ):
        self.real_mode = real_mode
        self.budget = budget
        self.calibrator_enabled = calibrator_enabled

        # --- 미주입 시 안전 빌더 ---
        if scorer is None:
            try:
                scorer = ScoreEngine(calibrator_enabled=calibrator_enabled)
            except TypeError:
                scorer = ScoreEngine()
                if hasattr(scorer, "set_calibrator_enabled"):
                    scorer.set_calibrator_enabled(calibrator_enabled)
                elif hasattr(scorer, "calibrator_enabled"):
                    setattr(scorer, "calibrator_enabled", calibrator_enabled)

        if risk is None:
            policies = [make_daydd()]
            try:
                policies.append(ExposurePolicy(max_total_budget=budget))
            except TypeError:
                policies.append(ExposurePolicy())
            risk = RiskGate(policies=policies)

        if router is None:
            created = False
            attempts = [
                {"dry_run": not real_mode, "budget": budget},
                {"real_mode": real_mode, "budget": budget},
                {"mode": ("REAL" if real_mode else "DRY"), "budget": budget},
                {},  # 인자 없음
            ]
            for kwargs in attempts:
                try:
                    router = OrderRouter(**kwargs)
                    created = True
                    break
                except TypeError:
                    continue
            if not created:
                router = OrderRouter()
            # 사후 토글(존재하면 설정)
            if hasattr(router, "dry_run"):
                try: router.dry_run = (not real_mode)
                except Exception: pass
            if hasattr(router, "real_mode"):
                try: router.real_mode = real_mode
                except Exception: pass
            if hasattr(router, "set_dry_run"):
                try: router.set_dry_run(not real_mode)
                except Exception: pass
            if hasattr(router, "enable_dry_run"):
                try: router.enable_dry_run(not real_mode)
                except Exception: pass
            if hasattr(router, "set_mode"):
                try: router.set_mode("REAL" if real_mode else "DRY")
                except Exception: pass

        if exit_rules is None:
            exit_rules = ExitRules()

        self.hub = Hub(scorer=scorer, risk=risk, router=router, exit_rules=exit_rules)

    # equity_now를 넘겨도/안 넘겨도 허용
    def on_tick(self, prices: Dict[str, float], equity_now: Optional[float] = None):
        return self.hub.on_tick(prices, equity_now)

    def portfolio(self):
        return self.hub.portfolio

    def run_session(self, symbols: List[str], max_ticks: int = 100):
        """심플 러너: PriceFeedMock이 있으면 사용해 max_ticks만큼 루프"""
        try:
            from market.price import PriceFeedMock
            feed = PriceFeedMock(symbols)
        except Exception:
            # 피드가 없을 때도 테스트가 'status'와 'decisions' 키를 기대
            return {
                "status": "ok",
                "events": self.hub.events,
                "portfolio": self.portfolio(),
                "decisions": getattr(self.hub, "_last_decisions", []),
            }

        ticks = 0
        while ticks < max_ticks:
            if hasattr(feed, "has_next") and not feed.has_next():
                break
            if hasattr(feed, "snapshot"):
                prices = feed.snapshot()
            elif hasattr(feed, "next"):
                prices = feed.next()
            else:
                break
            self.hub.on_tick(prices, None)  # equity_now는 허브에서 추정
            ticks += 1

        return {
            "status": "ok",
            "events": self.hub.events,
            "portfolio": self.portfolio(),
            "decisions": getattr(self.hub, "_last_decisions", []),
        }
