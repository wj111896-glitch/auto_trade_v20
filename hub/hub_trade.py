# -*- coding: utf-8 -*-
"""
hub/hub_trade.py - 전략 허브 (단일/멀티 심볼 공용)
"""
from __future__ import annotations

# ==== ① 경로 자동 세팅 ====
import os, sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime
import time
from collections import defaultdict

from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter
from obs.log import get_logger

# (옵션) 보정기
try:
    from scoring.calibrator import Calibrator  # type: ignore
except Exception:
    Calibrator = None  # type: ignore

__all__ = ["Hub", "HubTrade"]


class Hub:
    """전략 허브"""

    def __init__(self, scorer: ScoreEngine, risk: RiskGate, router: OrderRouter):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.log = get_logger("hub")

        # 포지션/캐시
        self.pos: defaultdict[str, int] = defaultdict(int)
        self.avg_px: defaultdict[str, float] = defaultdict(float)
        self.last_px: defaultdict[str, float] = defaultdict(float)
        self.cooldown: defaultdict[str, int] = defaultdict(int)
        self.COOLDOWN_TICKS = 3

        # ✅ DayDD 기준선(하루 시작 자산) 고정
        self._day_start_equity = float(getattr(risk, "budget", 0.0))
        self._equity_now = float(self._day_start_equity)

        # 섹터 맵 로드 (선택)
        self.sector_map: Dict[str, str] = {}
        self._sector_of: Optional[Callable[[str], Optional[str]]] = None
        try:
            proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sector_csv = os.path.join(proj_root, "data", "sector_map.csv")
            import csv
            for enc in ("utf-8-sig", "cp949"):
                try:
                    with open(sector_csv, "r", encoding=enc, newline="") as f:
                        rdr = csv.DictReader(f)
                        for row in rdr:
                            sym = str(row.get("symbol", "")).strip()
                            sec = str(row.get("sector", "")).strip()
                            if sym.isdigit() and len(sym) < 6:
                                sym = sym.zfill(6)
                            if sym:
                                self.sector_map[sym] = sec or "UNKNOWN"
                    break
                except Exception:
                    continue
            if self.sector_map:
                self.log.info(f"[Sector] loaded map: {len(self.sector_map)} symbols")
        except Exception as e:
            self.log.warning(f"[Sector] load failed: {e}")

        if self.sector_map:
            def _sector_of(sym: str) -> Optional[str]:
                if not sym:
                    return None
                s = str(sym).strip()
                if s.isdigit() and len(s) < 6:
                    s = s.zfill(6)
                return self.sector_map.get(s)
            self._sector_of = _sector_of

        self.log.info(
            "HUB init: scorer=%s risk=%s router=%s",
            type(scorer).__name__, type(risk).__name__, type(router).__name__
        )

    # ---- 내부 유틸 ----
    def _portfolio_snapshot(self) -> Dict[str, dict]:
        pf: Dict[str, dict] = {}
        for s, q in self.pos.items():
            if q > 0:
                pf[s] = {"qty": float(q), "avg_px": float(self.avg_px.get(s, 0.0))}
        return pf

    def _record_realized_pnl_if_any(self, sym: str, side: str, qty: int, price: float) -> None:
        """매도 체결 시 실현 손익 기록 (DayDD는 MTM로 커버되지만 참고 로그 및 옵셔널 훅 제공)"""
        try:
            if side != "SELL" or qty <= 0:
                return
            closed_qty = min(self.pos.get(sym, 0), qty)
            if closed_qty <= 0:
                return
            avg = float(self.avg_px.get(sym, 0.0) or 0.0)
            if avg <= 0.0:
                return

            realized_delta = (price - avg) * closed_qty
            if hasattr(self.risk, "on_fill_realized"):
                self.risk.on_fill_realized(realized_delta)

            pnl_pct = (price / avg - 1.0) * 100.0
            if hasattr(self.scorer, "on_realized_pnl"):
                self.scorer.on_realized_pnl(pnl_pct)

            self.log.info(
                f"[PnL] realized {sym} qty={closed_qty} avg={avg:.4f} exit={price:.4f} "
                f"pnl%={pnl_pct:.3f} pnl₩={realized_delta:.0f}"
            )
        except Exception as e:
            self.log.warning(f"[PnL] record fail: {e}")

    # ---- 메인 틱 처리 ----
    def on_tick(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sym = snapshot.get("symbol", "NA")
        price = float(snapshot.get("price") or 0.0)
        self.last_px[sym] = price
        self.log.info("HUB on_tick: symbol=%s price=%s", sym, price)

        # (0) 보정기
        try:
            self.scorer.maybe_adjust_weights()
        except AttributeError:
            pass

        # ① 스코어
        score = self.scorer.evaluate(snapshot)
        self.log.info("HUB score: %.3f", score)

        # ② MTM 기반 현재 자산 갱신 (DayDD용)
        day0 = float(self._day_start_equity)
        unreal = 0.0
        for s, q in self.pos.items():
            if q > 0:
                last_px = float(self.last_px.get(s, 0.0))
                avg_px = float(self.avg_px.get(s, 0.0))
                unreal += float(q) * (last_px - avg_px)
        self._equity_now = day0 + unreal

        # ③ 기본 의사결정
        if score > 0:
            decision = {"action": "BUY", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score>0"}
        elif score < 0:
            decision = {"action": "SELL", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score<0"}
        else:
            decision = {"action": "HOLD", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score=0"}

        # ③.5 쿨다운/포지션 가드
        cd = self.cooldown[sym]
        if cd > 0 and decision["action"] in ("BUY", "SELL"):
            self.log.info("HUB cooldown(%s): %s → HOLD", sym, cd)
            decision = {**decision, "action": "HOLD", "qty": 0, "tag": "cooldown"}
        elif decision["action"] == "SELL" and self.pos[sym] <= 0:
            self.log.info("HUB pos_guard: no position → HOLD")
            decision = {**decision, "action": "HOLD", "qty": 0, "tag": "no_pos"}

        # ④ RiskGate (allow_entry/size_for)
        if hasattr(self.risk, "allow_entry") and hasattr(self.risk, "size_for"):
            if decision["action"] == "BUY":
                portfolio = self._portfolio_snapshot()

                # DayDD 컨텍스트
                eq_now = float(self._equity_now)
                day_pnl_pct = (eq_now / day0 - 1.0) * 100.0 if day0 > 0 else 0.0
                ctx: Dict[str, Any] = {
                    "budget": getattr(self.risk, "budget", None),
                    "equity_now": eq_now,
                    "day_start_equity": day0,
                    "today_pnl_pct": day_pnl_pct,
                    "now_ts": time.time(),
                }
                if self._sector_of:
                    ctx["sector_of"] = self._sector_of

                if not self.risk.allow_entry(sym, portfolio, price, ctx=ctx):
                    self.log.warning(f"[RISK BLOCK] entry denied for {sym}")
                    decision = {**decision, "action": "HOLD", "qty": 0, "tag": "risk_block"}
                else:
                    qty = self.risk.size_for(sym, price, portfolio, ctx=ctx)
                    if qty <= 0:
                        self.log.info(f"[RISK SIZE=0] {sym} skipped")
                        decision = {**decision, "action": "HOLD", "qty": 0, "tag": "risk_size0"}
                    else:
                        decision = {**decision, "qty": int(qty)}

        self.log.info("HUB decision: %s", decision)

        # ⑤ 주문 라우팅
        act = decision["action"]
        qty = int(decision.get("qty", 0) or 0)
        if act in ("BUY", "SELL") and qty > 0:
            routed = self.router.route(decision)
            if routed is not None:
                decision = {**decision, "route_result": routed}

        # ⑥ 포지션/쿨다운 갱신
        if act == "BUY" and qty > 0:
            old_qty = self.pos[sym]
            old_avg = self.avg_px[sym] if old_qty > 0 else 0.0
            new_qty = old_qty + qty
            self.avg_px[sym] = ((old_avg * old_qty) + (price * qty)) / max(1, new_qty)
            self.pos[sym] = new_qty
            self.cooldown[sym] = self.COOLDOWN_TICKS
        elif act == "SELL" and qty > 0 and self.pos[sym] >= qty:
            self._record_realized_pnl_if_any(sym, "SELL", qty, price)
            self.pos[sym] -= qty
            if self.pos[sym] == 0:
                self.avg_px[sym] = 0.0
            self.cooldown[sym] = self.COOLDOWN_TICKS
        else:
            if self.cooldown[sym] > 0:
                self.cooldown[sym] -= 1

        return decision


# =========================
# HubTrade 러너
# =========================
@dataclass
class _RunnerOpts:
    real_mode: bool = False
    budget: Optional[float] = None
    dry_run: Optional[bool] = None
    calibrator_enabled: bool = False
    calib_lr: float = 0.02
    calib_hist: int = 100
    calib_clip: float = 0.05
    note: str = ""


class HubTrade:
    def __init__(self, real_mode: bool = False, budget: Optional[float] = None, **kwargs):
        self.log = get_logger("hubtrade")
        self.opts = _RunnerOpts(
            real_mode=real_mode,
            budget=budget,
            **{k: kwargs[k] for k in ["calibrator_enabled", "calib_lr", "calib_hist", "calib_clip", "note"] if k in kwargs}
        )
        scorer, risk = self._make_scorer_risk()
        router = self._make_router()
        self.hub = Hub(scorer, risk, router)

    def _make_scorer_risk(self) -> Tuple[ScoreEngine, RiskGate]:
        calibrator = None
        if self.opts.calibrator_enabled and Calibrator is not None:
            calibrator = Calibrator(lr=self.opts.calib_lr, hist=self.opts.calib_hist, clip=self.opts.calib_clip)
            self.log.info(f"[Calibrator] enabled lr={self.opts.calib_lr} hist={self.opts.calib_hist} clip={self.opts.calib_clip}")

        try:
            scorer = ScoreEngine(calibrator=calibrator, logger=get_logger("scorer"))
        except Exception:
            class _DummyScorer(ScoreEngine):
                def evaluate(self, snapshot):
                    return 1.0 if snapshot.get("price", 0) <= 10 else -1.0
            scorer = _DummyScorer()

        try:
            risk = RiskGate(budget=self.opts.budget)
        except Exception:
            class _DummyRisk(RiskGate):
                def apply(self, score, snapshot):
                    sym = snapshot.get("symbol", "NA")
                    return {"action": "BUY" if score > 0 else "HOLD", "symbol": sym, "qty": 1}
            risk = _DummyRisk()
        return scorer, risk

    def _make_router(self) -> OrderRouter:
        router = OrderRouter(get_logger("router"))
        try:
            if hasattr(router, "set_mode"):
                mode = "REAL" if self.opts.real_mode else "DRY"
                router.set_mode(mode, budget=self.opts.budget)
                self.log.info(f"router.set_mode({mode}) applied")
        except Exception as e:
            self.log.warning(f"router.set_mode 예외: {e}")
        try:
            ok = router.connect()
            self.log.info("router.connect() -> %s", ok)
        except Exception as e:
            self.log.warning("router.connect 예외: %s", e)
        return router

    def _fetch_snapshot(self, feed, sym: str, ticks: int):
        for name in ("snapshot", "get_snapshot", "quote", "get", "next", "read"):
            if hasattr(feed, name):
                fn = getattr(feed, name)
                try:
                    data = fn(sym)
                except TypeError:
                    data = fn()
                if isinstance(data, (list, tuple)) and len(data) >= 2:
                    data = {"symbol": str(data[0]), "price": float(data[1])}
                if isinstance(data, dict):
                    data.setdefault("symbol", sym)
                    return data
        return {"symbol": sym, "price": 10.0 + (ticks % 5) * 0.1}

    def run_session(self, symbols: List[str], max_ticks: int) -> Dict[str, Any]:
        started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log.info("run_session start: symbols=%s max_ticks=%s", symbols, max_ticks)

        try:
            from market.price import PriceFeedMock
            feed = PriceFeedMock(symbols)
        except Exception:
            feed = None

        ticks = 0
        decisions: List[Dict[str, Any]] = []

        while ticks < max_ticks:
            for sym in symbols:
                snap = self._fetch_snapshot(feed, sym, ticks) if feed else {"symbol": sym, "price": 10.0 + (ticks % 5) * 0.1}
                decision = self.hub.on_tick(snap)
                decisions.append(decision)
                ticks += 1
                if ticks >= max_ticks:
                    break
            time.sleep(0.001)

        self.log.info("run_session end: ticks=%s", ticks)
        return {"status": "ok", "ticks": ticks, "symbols": symbols, "decisions": decisions[-10:]}


if __name__ == "__main__":
    hubtrade = HubTrade(real_mode=False, budget=1_000_000, calibrator_enabled=True)
    out = hubtrade.run_session(["005930", "000660"], max_ticks=10)
    print("decision_out(last10):", out.get("decisions"))
