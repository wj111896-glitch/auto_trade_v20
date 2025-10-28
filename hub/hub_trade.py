# -*- coding: utf-8 -*-
"""
hub/hub_trade.py - 전략 허브 (단일/멀티 심볼 공용)
시세 스냅샷(snapshot)을 받아 점수 → 리스크 → 의사결정 → 주문 실행까지 연결

본 파일은 두 가지 레벨을 제공합니다.
1) Hub  : 순수 도메인 허브 — scorer/risk/router를 주입 받아 on_tick 처리만 담당
2) HubTrade : 실행 러너 — 기본 구성요소를 자동으로 주입하고 run_session/start/run 제공

run_daytrade.py 와의 호환을 위해 `HubTrade`를 export 합니다.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import time
from collections import defaultdict

from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter
from obs.log import get_logger

__all__ = ["Hub", "HubTrade"]


class Hub:
    """전략 허브 (단일 심볼/멀티 심볼 공용)

    흐름:
        on_tick(snapshot)
          → ScoreEngine.evaluate()
          → (쿨다운/포지션 가드)
          → RiskGate(allow_entry/size_for)  ← ★ 추가
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
        # DRY_RUN용 로컬 포지션/쿨다운/평단/최근가 캐시
        self.pos: defaultdict[str, int] = defaultdict(int)
        self.avg_px: defaultdict[str, float] = defaultdict(float)
        self.last_px: defaultdict[str, float] = defaultdict(float)
        self.cooldown: defaultdict[str, int] = defaultdict(int)
        self.COOLDOWN_TICKS = 3

        self.log.info(
            "HUB init: scorer=%s risk=%s router=%s",
            type(scorer).__name__,
            type(risk).__name__,
            type(router).__name__,
        )

    # --- RiskGate의 옛 인터페이스 호환 (보유: 필요시 사용) ---
    def _risk_apply_legacy(self, score, snapshot):
        """RiskGate의 다양한 메서드 명을 호환해서 호출한다(구버전 지원)."""
        for name in ("apply", "decide", "__call__", "process", "evaluate", "run", "filter", "gate"):
            if hasattr(self.risk, name):
                fn = getattr(self.risk, name)
                try:
                    return fn(score, snapshot)
                except TypeError:
                    for args in ((score,), (snapshot,), tuple()):
                        try:
                            return fn(*args)
                        except TypeError:
                            continue
        # 최후 기본값
        sym = snapshot.get("symbol", "NA")
        if score > 0:
            return {"action": "BUY", "symbol": sym, "qty": 1, "order_type": "MKT", "price": None, "tag": "fallback"}
        elif score < 0:
            return {"action": "SELL", "symbol": sym, "qty": 1, "order_type": "MKT", "price": None, "tag": "fallback"}
        else:
            return {"action": "HOLD", "symbol": sym, "qty": 0}

    # --- 내부 포트폴리오 스냅샷 (RiskGate용) ---
    def _portfolio_snapshot(self) -> Dict[str, dict]:
        pf: Dict[str, dict] = {}
        # pos/avg_px는 DRY_RUN에서 우리가 관리
        for s, q in self.pos.items():
            if q <= 0:
                continue
            pf[s] = {"qty": float(q), "avg_px": float(self.avg_px.get(s, self.last_px.get(s, 0.0)))}
        return pf

    def on_tick(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """하나의 틱 데이터를 받아 스코어링, 리스크 판단, 주문 실행"""
        sym = snapshot.get("symbol", "NA")
        price = float(snapshot.get("price") or 0.0)
        self.last_px[sym] = price
        self.log.info("HUB on_tick: symbol=%s price=%s", sym, price)

        # ① 스코어 평가
        score = self.scorer.evaluate(snapshot)
        self.log.info("HUB score: %.3f", score)

        # ② 기본 의사결정(스코어→액션) : 간단 매핑
        #   * 점수>0 → BUY 후보, 점수<0 → SELL 후보, 0 → HOLD
        if score > 0:
            decision = {"action": "BUY", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score>0"}
        elif score < 0:
            decision = {"action": "SELL", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score<0"}
        else:
            decision = {"action": "HOLD", "symbol": sym, "qty": 0, "order_type": "MKT", "price": None, "tag": "score=0"}

        # ②.5 쿨다운/포지션 가드
        cd = self.cooldown[sym]
        if cd > 0 and decision.get("action") in ("BUY", "SELL"):
            self.log.info("HUB cooldown(%s): %s → HOLD", sym, cd)
            decision = {**decision, "action": "HOLD", "qty": 0, "tag": "cooldown"}
        else:
            if decision.get("action") == "SELL" and self.pos[sym] <= 0:
                self.log.info("HUB pos_guard: no position → HOLD")
                decision = {**decision, "action": "HOLD", "qty": 0, "tag": "no_pos"}

        # ③ RiskGate (신규: allow_entry/size_for) — BUY일 때만 적용
        if decision.get("action") == "BUY":
            portfolio = self._portfolio_snapshot()
            # 3-1) 진입 허용 여부
            if not self.risk.allow_entry(sym, portfolio, price):
                self.log.warning(f"[RISK BLOCK] entry denied for {sym}")
                decision = {**decision, "action": "HOLD", "qty": 0, "tag": "risk_block"}
            else:
                # 3-2) 수량 산정 (총노출/심볼캡 잔여 기반)
                qty = self.risk.size_for(sym, price)
                if qty <= 0:
                    self.log.info(f"[RISK SIZE=0] {sym} skipped")
                    decision = {**decision, "action": "HOLD", "qty": 0, "tag": "risk_size0"}
                else:
                    decision = {**decision, "qty": int(qty)}

        self.log.info("HUB decision: %s", decision)

        # ④ 주문 라우팅 (BUY/SELL & qty>0 에서만 실행)
        act = decision.get("action")
        qty = int(decision.get("qty", 0) or 0)
        routed = None
        if act in ("BUY", "SELL") and qty > 0:
            routed = self.router.route(decision)
            if routed is not None:
                decision = {**decision, "route_result": routed}

        # ⑤ 포지션/쿨다운/평단 업데이트 (DRY_RUN용 낙관적 업데이트)
        if act == "BUY" and qty > 0:
            old_qty = self.pos[sym]
            old_avg = self.avg_px[sym] if old_qty > 0 else 0.0
            new_qty = old_qty + qty
            # 단순 가중평균으로 평단 갱신
            self.avg_px[sym] = ((old_avg * old_qty) + (price * qty)) / max(1, new_qty)
            self.pos[sym] = new_qty
            self.cooldown[sym] = self.COOLDOWN_TICKS
        elif act == "SELL" and qty > 0 and self.pos[sym] >= qty:
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
    dry_run: Optional[bool] = None  # router가 지원하는 경우 우선 사용


class HubTrade:
    """run_daytrade.py 가 기대하는 실행 어댑터

    - __init__(real_mode, budget, **kwargs)
    - run_session(symbols=[...], max_ticks=...)
    - start / run : run_session의 별칭(호환성)
    """

    def __init__(self, real_mode: bool = False, budget: Optional[float] = None, **kwargs):
        self.log = get_logger("hubtrade")
        self.opts = _RunnerOpts(real_mode=real_mode, budget=budget)

        # ① 의존성 준비 (프로젝트 실제 엔진이 없으면 더미로 fallback)
        scorer, risk = self._make_scorer_risk()
        router = self._make_router()

        self.hub = Hub(scorer, risk, router)

    # --- 구성 요소 생성 ---
    def _make_scorer_risk(self) -> tuple[ScoreEngine, RiskGate]:
        try:
            scorer = ScoreEngine()
        except Exception:
            class _DummyScorer(ScoreEngine):
                def evaluate(self, snapshot):
                    return 1.0 if snapshot.get("price", 0) <= 10 else -1.0
            scorer = _DummyScorer()

        try:
            risk = RiskGate()
        except Exception:
            class _DummyRisk(RiskGate):
                def apply(self, score, snapshot):
                    sym = snapshot.get("symbol", "NA")
                    if score > 0:
                        return {"action": "BUY", "symbol": sym, "qty": 1, "order_type": "MKT", "price": None, "tag": "smoke"}
                    return {"action": "HOLD", "symbol": sym, "qty": 0}
            risk = _DummyRisk()
        return scorer, risk

    def _make_router(self) -> OrderRouter:
        router = OrderRouter(get_logger("router"))
        try:
            if hasattr(router, "set_mode"):
                mode = "REAL" if self.opts.real_mode else "DRY"
                router.set_mode(mode, budget=self.opts.budget)
        except Exception:
            pass
        try:
            ok = router.connect()
            self.log.info("router.connect() -> %s", ok)
        except Exception as e:
            self.log.warning("router.connect 예외: %s (계속 진행)", e)
        return router

    # --- 피드 호환 유틸 ---
    def _fetch_snapshot(self, feed, sym: str, ticks: int):
        """다양한 Feed 인터페이스 스펙을 호환해서 스냅샷을 얻어온다."""
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

    # --- 실행 루프 ---
    def run_session(self, symbols: List[str], max_ticks: int) -> Dict[str, Any]:
        started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log.info("run_session start: symbols=%s max_ticks=%s real_mode=%s budget=%s",
                      symbols, max_ticks, self.opts.real_mode, self.opts.budget)

        feed = None
        try:
            from market.price import PriceFeedMock  # type: ignore
            feed = PriceFeedMock(symbols)
            self.log.info("PriceFeedMock 사용")
        except Exception:
            self.log.info("PriceFeedMock 없음 — synthetic feed 사용")

        ticks = 0
        decisions: List[Dict[str, Any]] = []

        while ticks < max_ticks:
            for sym in symbols:
                snap = self._fetch_snapshot(feed, sym, ticks) if feed is not None else {"symbol": sym, "price": 10.0 + (ticks % 5) * 0.1}
                decision = self.hub.on_tick(snap)
                decisions.append(decision)
                ticks += 1
                if ticks >= max_ticks:
                    break
            time.sleep(0.001)  # 너무 빠른 루프 방지 (mock 환경)

        ended_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log.info("run_session end: ticks=%s", ticks)
        return {
            "status": "ok",
            "ticks": ticks,
            "symbols": symbols,
            "real_mode": self.opts.real_mode,
            "budget": self.opts.budget,
            "started_at": started_at,
            "ended_at": ended_at,
            "decisions": decisions[-10:],  # 마지막 10개만 요약으로 반환
        }

    # 호환용 별칭
    def start(self, **kwargs):
        return self.run_session(**kwargs)

    def run(self, **kwargs):
        return self.run_session(**kwargs)


# =========================
# 단독 실행 테스트 (DRY_RUN)
# =========================
if __name__ == "__main__":
    from common import config

    # DRY_RUN 설정 힌트
    config.BROKER = "KIWOOM"
    config.DRY_RUN = True
    config.ACCOUNT_NO = "00000000"

    # 허브 초기화 및 테스트
    hubtrade = HubTrade(real_mode=False, budget=1_000_000)
    out = hubtrade.run_session(["005930", "000660"], max_ticks=10)
    print("decision_out(last10):", out.get("decisions"))


