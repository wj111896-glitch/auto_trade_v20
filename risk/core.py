# -*- coding: utf-8 -*-
"""
risk/core.py — RiskGate (policies orchestrator, adaptive sizing)

- 단일 RiskGate 정의(중복 제거)
- evaluate(): 확장형 정책(evaluate) 병합 집계 (allow/scale/force_flatten)
- 구 스타일(check_entry/size_hint) 정책도 어댑터로 지원
- on_fill_realized(): 체결 손익을 DayDD 등에 전달(record_fill)
- size_for(): 모든 정책의 size_hint를 모아 보수적(최소) 수량 채택
- apply(): 레거시 호환 (score → BUY/HOLD/SELL)
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# ---------- logger (fallback) ----------
try:
    from obs.log import get_logger  # type: ignore
except Exception:
    class _L:
        def info(self, *a, **k): print("[INFO]", *a)
        def warning(self, *a, **k): print("[WARN]", *a)
        def error(self, *a, **k): print("[ERROR]", *a)
    def get_logger(name):  # type: ignore
        return _L()

log = get_logger("risk")

# ---------- budget 기본값 ----------
try:
    from common import config  # type: ignore
    _BUDGET = float(getattr(config, "BUDGET", 0.0) or 0.0)
except Exception:
    _BUDGET = 0.0

# ---------- 정책 import ----------
try:
    from .policies.base import BasePolicy as Policy, PolicyResult  # type: ignore
except Exception:
    class Policy:  # type: ignore
        pass
    @dataclass
    class PolicyResult:  # type: ignore
        ok: bool
        reason: Optional[str] = None

from .policies.exposure import ExposurePolicy, ExposureParams  # type: ignore

# DayDD는 “랩퍼”를 통해 주입 (risk/day_dd.py의 make_daydd)
try:
    from .day_dd import make_daydd  # type: ignore
except Exception:
    make_daydd = None  # type: ignore


# ---------- 유틸 ----------
def _norm_policy_output(res: Any) -> Dict[str, Any]:
    """다양한 정책 출력을 표준 dict로 정규화.
    표준 키: allow(bool), scale(float), force_flatten(bool), reason(str)
    """
    out = {"allow": True, "scale": 1.0, "force_flatten": False, "reason": None}

    if isinstance(res, dict):
        out["allow"] = bool(res.get("allow", True))
        out["scale"] = float(res.get("scale", 1.0))
        out["force_flatten"] = bool(res.get("force_flatten", False))
        r = res.get("reason")
        out["reason"] = str(r) if r is not None else None
        return out

    if hasattr(res, "ok") or hasattr(res, "allow"):  # PolicyResult 호환
        ok = getattr(res, "ok", None)
        if ok is None:
            ok = getattr(res, "allow", True)
        out["allow"] = bool(ok)
        out["reason"] = getattr(res, "reason", None)
        return out

    out["allow"] = bool(res)  # truthy 최후 처리
    return out


# ======================== RiskGate ========================
class RiskGate:
    """
    Primary API:
      - evaluate(context) -> {allow, scale, force_flatten, reason}

    Adapter API (구 정책 호환):
      - allow_entry(symbol, portfolio, price, ctx=None) -> bool
      - size_for(symbol, price, portfolio, ctx=None) -> int

    Legacy:
      - apply(score, snapshot) -> decision(dict)
    """
    def __init__(self, policies: Optional[List[Policy]] = None, budget: Optional[float] = None) -> None:
        self.budget = float(budget or _BUDGET or 10_000_000.0)

        if policies is None:
            policies = [ExposurePolicy(ExposureParams(budget=self.budget))]
            # DayDD 랩퍼가 있으면 실거래 파라미터로 자동 주입
            if make_daydd is not None:
                try:
                    policies.append(make_daydd())
                except Exception as e:
                    log.warning(f"[RiskGate] make_daydd() 실패: {e}")

        self.policies: List[Policy] = policies

    # ---------- 공통 컨텍스트 병합 ----------
    @staticmethod
    def _merge_ctx(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return dict(ctx or {})

    # ---------- 확장형: evaluate 병합 ----------
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agg_allow = True
        agg_scale = 1.0
        agg_force = False
        reasons: List[str] = []

        for p in self.policies:
            try:
                if hasattr(p, "evaluate"):
                    res = _norm_policy_output(p.evaluate(context))  # type: ignore
                elif hasattr(p, "check_entry"):  # 구 스타일
                    sym = context.get("symbol") or context.get("sym") or "NA"
                    price = float(context.get("price", 0.0) or 0.0)
                    pf = context.get("portfolio") or {}
                    res = _norm_policy_output(p.check_entry(sym, price, pf, context))  # type: ignore
                else:
                    continue
            except Exception as e:
                log.warning(f"[RiskGate] policy error {p.__class__.__name__}: {e}")
                res = {"allow": False, "scale": 0.0, "force_flatten": False, "reason": f"error:{e}"}

            agg_allow = agg_allow and bool(res.get("allow", True))
            agg_scale = min(agg_scale, float(res.get("scale", 1.0)))
            agg_force = agg_force or bool(res.get("force_flatten", False))
            r = res.get("reason")
            if r:
                reasons.append(str(r))

        out = {
            "allow": bool(agg_allow),
            "scale": max(0.0, min(1.0, float(agg_scale))),
            "force_flatten": bool(agg_force),
            "reason": " | ".join(reasons) if reasons else None,
        }
        log.info(
            f"[RiskGate] allow={out['allow']} scale={out['scale']} "
            f"force_flatten={out['force_flatten']} reason={out['reason']}"
        )
        return out

    # ---------- 체결 손익 전달 훅 ----------
    def on_fill_realized(self, realized_pnl_delta: float) -> None:
        for p in self.policies:
            try:
                if hasattr(p, "record_fill"):
                    p.record_fill(float(realized_pnl_delta))  # type: ignore
            except Exception as e:
                log.warning(f"[RiskGate] on_fill_realized error {p.__class__.__name__}: {e}")

    # ---------- 어댑터: 구 정책 호환 ----------
    def allow_entry(self, symbol: str, portfolio: Dict[str, dict], price: float,
                    ctx: Optional[Dict[str, Any]] = None) -> bool:
        cx = self._merge_ctx(ctx)
        ev = self.evaluate({**cx, "is_entry": True, "symbol": symbol, "price": price, "portfolio": portfolio})
        return bool(ev.get("allow", True))

    def size_for(self, symbol: str, price: float, portfolio: Dict[str, dict],
                 ctx: Optional[Dict[str, Any]] = None) -> int:
        cx = self._merge_ctx(ctx)
        hints: List[int] = []
        for p in self.policies:
            if hasattr(p, "size_hint"):
                try:
                    q = p.size_hint(symbol, price, portfolio, cx)  # type: ignore
                    if q is not None and int(q) > 0:
                        hints.append(int(q))
                except Exception as e:
                    log.warning(f"[RiskGate] size_hint error {p.__class__.__name__}: {e}")
        if hints:
            qty = max(0, min(hints))  # 가장 보수적인 수량
            log.info(f"[RiskGate] SIZE hints={hints} -> qty={qty}")
            return qty

        # fallback: evaluate의 scale 이용
        ev = self.evaluate({**cx, "is_entry": True, "symbol": symbol, "price": price, "portfolio": portfolio})
        scale = float(ev.get("scale", 1.0))
        base_qty = 1  # 필요시 config로 이동/계산
        qty = int(max(0, round(base_qty * scale)))
        log.info(f"[RiskGate] SIZE (fallback) scale={scale:.2f} -> qty={qty}")
        return qty

    # ---------- 레거시 ----------
    def apply(self, score: float, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sym = str(snapshot.get("symbol", "NA"))
        price = float(snapshot.get("price", 0.0) or 0.0)
        pf = snapshot.get("_portfolio", {})

        if score > 0:
            ev = self.evaluate({"is_entry": True, "symbol": sym, "price": price, "portfolio": pf, **snapshot})
            if ev["allow"]:
                qty = self.size_for(sym, price, pf, snapshot)
                if qty > 0:
                    return {"action": "BUY", "symbol": sym, "qty": int(qty),
                            "order_type": "MKT", "price": None, "tag": "risk-legacy"}
            return {"action": "HOLD", "symbol": sym, "qty": 0}

        if score < 0:
            pos = pf.get(sym)
            if pos and int(pos.get("qty", 0)) > 0:
                return {"action": "SELL", "symbol": sym, "qty": int(pos.get("qty", 1)),
                        "order_type": "MKT", "price": None, "tag": "risk-legacy-exit"}
            return {"action": "HOLD", "symbol": sym, "qty": 0}

        return {"action": "HOLD", "symbol": sym, "qty": 0}
