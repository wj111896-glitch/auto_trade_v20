# -*- coding: utf-8 -*-
"""
risk/core.py — RiskGate (policies orchestrator)

- evaluate(): 각 정책 결과 병합 (allow/scale/force_flatten/reason)
- allow_entry()/size_for(): 구 정책 어댑터
- check(): Hub 호환 (allow, reason, size_hint) 반환
- on_fill_realized(): 체결 손익을 정책에 전달(record_fill)
- apply(): 레거시 호환
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# ---------- logger fallback ----------
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

# ---------- 정책 import ----------
try:
    from .policies.base import BasePolicy as Policy, PolicyResult  # type: ignore
except Exception:
    class Policy:  # type: ignore
        pass
    @dataclass
    class PolicyResult:  # type: ignore
        allow: bool
        reason: str = ""
        max_qty_hint: Optional[int] = None

# Exposure (총액/심볼 한도)
from .policies.exposure import ExposurePolicy, ExposureConfig  # type: ignore

# DayDD (있으면 사용)
DayDDPolicy = None
try:
    from .policies.day_dd import DayDDPolicy as _DD  # type: ignore
    DayDDPolicy = _DD
except Exception:
    DayDDPolicy = None

# 프로젝트 래퍼 (make_daydd) 지원
try:
    from .day_dd import make_daydd  # type: ignore
except Exception:
    make_daydd = None  # type: ignore

# ✅ SectorCapPolicy 추가
try:
    from .policies.sector_cap import SectorCapPolicy, SectorParams  # type: ignore
except Exception:
    SectorCapPolicy = None
    SectorParams = None


# ---------- 유틸 ----------
def _norm(res: Any) -> Dict[str, Any]:
    """
    다양한 정책 출력을 표준 dict로 정규화.
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

    if hasattr(res, "allow") or hasattr(res, "ok"):
        ok = getattr(res, "allow", getattr(res, "ok", True))
        out["allow"] = bool(ok)
        out["reason"] = getattr(res, "reason", None)
        return out

    out["allow"] = bool(res)
    return out


# ======================== RiskGate ========================
class RiskGate:
    """
    정책 병합 게이트웨이
    - evaluate(context) -> {allow, scale, force_flatten, reason}
    - allow_entry(), size_for(), check() 제공
    """

    def __init__(self, policies: Optional[List[Policy]] = None, budget: Optional[float] = None) -> None:
        self.budget = budget
        if policies is None:
            pols: List[Policy] = []

            # (1) DayDD
            if make_daydd is not None:
                try:
                    pols.append(make_daydd())
                except Exception as e:
                    log.warning(f"[RiskGate] make_daydd() 실패: {e}")
            elif DayDDPolicy is not None:
                try:
                    pols.append(DayDDPolicy())
                except Exception as e:
                    log.warning(f"[RiskGate] DayDDPolicy 생성 실패: {e}")

            # (2) Exposure
            try:
                pols.append(ExposurePolicy(ExposureConfig()))
            except Exception as e:
                log.warning(f"[RiskGate] ExposurePolicy 생성 실패: {e}")

            # ✅ (3) SectorCap — 섹터 집중도 제한
            if SectorCapPolicy is not None and SectorParams is not None:
                try:
                    pols.append(SectorCapPolicy(SectorParams(sector_cap_pct=0.35)))
                    log.info("[RiskGate] SectorCapPolicy 활성화 (max 35%)")
                except Exception as e:
                    log.warning(f"[RiskGate] SectorCapPolicy 생성 실패: {e}")
            else:
                log.warning("[RiskGate] SectorCapPolicy 미탑재")

            self.policies = pols
        else:
            self.policies = policies

    # ---------- 컨텍스트 병합 ----------
    @staticmethod
    def _merge_ctx(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return dict(ctx or {})

    # ---------- evaluate ----------
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agg_allow = True
        agg_scale = 1.0
        agg_force = False
        reasons: List[str] = []

        for p in self.policies:
            try:
                if hasattr(p, "evaluate"):
                    res = _norm(p.evaluate(context))  # type: ignore
                elif hasattr(p, "check_entry"):
                    sym = context.get("symbol") or context.get("sym") or "NA"
                    price = float(context.get("price", 0.0) or 0.0)
                    pf = context.get("portfolio") or {}
                    res = _norm(p.check_entry(sym, price, pf, context))  # type: ignore
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
            f"[RiskGate] allow={out['allow']} scale={out['scale']:.2f} "
            f"force_flatten={out['force_flatten']} reason={out['reason']}"
        )
        return out

    # ---------- 체결 손익 전달 ----------
    def on_fill_realized(self, realized_pnl_delta: float) -> None:
        for p in self.policies:
            try:
                if hasattr(p, "record_fill"):
                    p.record_fill(float(realized_pnl_delta))  # type: ignore
            except Exception as e:
                log.warning(f"[RiskGate] on_fill_realized error {p.__class__.__name__}: {e}")

    # ---------- 어댑터 ----------
    def allow_entry(self, symbol: str, price: float, portfolio: Dict[str, dict],
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
            qty = max(0, min(hints))
            log.info(f"[RiskGate] SIZE hints={hints} -> qty={qty}")
            return qty

        ev = self.evaluate({**cx, "is_entry": True, "symbol": symbol, "price": price, "portfolio": portfolio})
        scale = float(ev.get("scale", 1.0))
        base_qty = 1
        qty = int(max(0, round(base_qty * scale)))
        log.info(f"[RiskGate] SIZE (fallback) scale={scale:.2f} -> qty={qty}")
        return qty

    # ---------- Hub 호환 ----------
    def check(self, symbol: str, price: float, portfolio: Dict[str, dict],
              ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Optional[int]]:
        cx = self._merge_ctx(ctx)
        ev = self.evaluate({**cx, "is_entry": True, "symbol": symbol, "price": price, "portfolio": portfolio})
        allow = bool(ev.get("allow", True))
        reason = str(ev.get("reason") or "ok")

        hints: List[int] = []
        for p in self.policies:
            if hasattr(p, "size_hint"):
                try:
                    q = p.size_hint(symbol, price, portfolio, cx)  # type: ignore
                    if q is not None and int(q) >= 0:
                        hints.append(int(q))
                except Exception as e:
                    log.warning(f"[RiskGate] size_hint error {p.__class__.__name__}: {e}")

        size_hint = None
        if hints:
            hints = [int(q) for q in hints if q is not None and q >= 0]
            if hints:
                size_hint = min(hints)

        return allow, reason, size_hint

    # ---------- 레거시 ----------
    def apply(self, score: float, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sym = str(snapshot.get("symbol", "NA"))
        price = float(snapshot.get("price", 0.0) or 0.0)
        pf = snapshot.get("_portfolio", {}) or {}

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
