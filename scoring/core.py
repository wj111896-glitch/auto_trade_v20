# -*- coding: utf-8 -*-
"""
scoring/core.py — final v2 (feature engine + robust compatibility)

목표:
1) 기존 기능 유지: Weights + volume/tickflow/ta 피처 기반 점수
2) 호환성 강화: 다양한 스냅샷/틱 포맷과 가중치 포맷을 안전 처리
3) 폴백 제공: 피처 모듈이 비어 있거나 예외 시 간단 임계값 룰로 동작

인터페이스:
- ScoreEngine.evaluate(snapshot: dict|obj) -> float
- (호환) ScoreEngine.score(tick) -> float
- (호환) ScoreEngine.score_with_detail(tick) -> (float, dict)
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import os

__all__ = ["ScoreEngine"]

# ===== 안전 임포트 (실제 모듈 없을 때 폴백 스텁) =====
try:
    from .weights import Weights  # type: ignore
except Exception:  # 폴백 Weights
    class Weights:  # type: ignore
        def __init__(self, volume: float = 0.45, tickflow: float = 0.35, ta: float = 0.20):
            self.volume = volume
            self.tickflow = tickflow
            self.ta = ta
        def to_dict(self):
            return {"volume": self.volume, "tickflow": self.tickflow, "ta": self.ta}

# 피처 함수: 각 모듈이 없으면 기본 0.0 반환으로 안전 대체
try:
    from .features.volume import volume_surge  # type: ignore
except Exception:
    def volume_surge(snapshot: Dict[str, Any]) -> float:  # type: ignore
        vol = _get(snapshot, "volume", 0.0)
        base = 500.0
        return max(-1.0, min(1.0, (float(vol) - base) / base)) if vol is not None else 0.0

try:
    from .features.tickflow import tick_flow  # type: ignore
except Exception:
    _last_price_glob: Dict[str, float] = {}
    def tick_flow(snapshot: Dict[str, Any]) -> float:  # type: ignore
        sym = str(_get(snapshot, "symbol", "NA"))
        price = float(_get(snapshot, "price", 0.0) or 0.0)
        prev = _last_price_glob.get(sym)
        _last_price_glob[sym] = price
        if not prev or prev <= 0:
            return 0.0
        mom = (price / prev - 1.0)
        return max(-1.0, min(1.0, mom * 50.0))

try:
    from .features.ta import ma_cross  # type: ignore
except Exception:
    def ma_cross(snapshot: Dict[str, Any]) -> float:  # type: ignore
        # 모멘텀 부호 기반 간단 대체
        sym = str(_get(snapshot, "symbol", "NA"))
        price = float(_get(snapshot, "price", 0.0) or 0.0)
        prev = _state_prev_price.setdefault(sym, price)
        _state_prev_price[sym] = price
        if price > prev:
            return 1.0
        if price < prev:
            return -1.0
        return 0.0

# 내부 상태 저장용(간단)
_state_prev_price: Dict[str, float] = {}

# ===== 유틸 =====
def _get(snapshot: Any, key: str, default: Any = None):
    """dict/obj 모두에서 키/속성 접근을 시도한다."""
    if isinstance(snapshot, dict):
        return snapshot.get(key, default)
    # 객체 속성
    if hasattr(snapshot, key):
        try:
            return getattr(snapshot, key)
        except Exception:
            return default
    # (symbol, price) 같은 튜플 처리
    if key in ("symbol", "price") and isinstance(snapshot, (tuple, list)) and len(snapshot) >= 2:
        return snapshot[0] if key == "symbol" else snapshot[1]
    return default


def _coerce_float(val, default):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except Exception:
            return float(default)
    if hasattr(val, "value"):
        try:
            return float(val.value)
        except Exception:
            return float(default)
    if isinstance(val, dict):
        for k in ("value", "val", "w", "weight", "coef"):
            if k in val:
                try:
                    return float(val[k])
                except Exception:
                    pass
        for v in val.values():
            if isinstance(v, (int, float, str)):
                try:
                    return float(v)
                except Exception:
                    continue
        return float(default)
    return float(default)


def _resolve_weight(wsrc: Any, key: str, default: float) -> float:
    if wsrc is None:
        return float(default)
    if isinstance(wsrc, dict):
        return _coerce_float(wsrc.get(key, default), default)
    if hasattr(wsrc, "to_dict"):
        try:
            d = wsrc.to_dict() or {}
        except Exception:
            d = {}
        return _coerce_float(d.get(key, default), default)
    if hasattr(wsrc, key):
        return _coerce_float(getattr(wsrc, key), default)
    return float(default)


# ===== 본체 =====
class ScoreEngine:
    def __init__(self, weights: Weights | Dict[str, Any] | None = None):
        self.weights = weights or Weights()
        # 임계값 폴백(피처가 모두 0일 때 대비)
        self.BUY_MAX = float(os.getenv("SCORE_BUY_MAX", 10.15))
        self.SELL_MIN = float(os.getenv("SCORE_SELL_MIN", 10.35))

    def evaluate(self, snapshot: Any) -> float:
        """기본: 피처*가중치 합. 예외 시 간단 임계값 폴백.
        snapshot은 dict/obj/tuple(심볼,가격) 모두 허용.
        """
        # 피처 산출은 try-각개 처리(하나 실패해도 나머지는 반영)
        try:
            f_vol = float(volume_surge(snapshot))
        except Exception:
            f_vol = 0.0
        try:
            f_flow = float(tick_flow(snapshot))
        except Exception:
            f_flow = 0.0
        try:
            f_ta = float(ma_cross(snapshot))
        except Exception:
            f_ta = 0.0

        wv = _resolve_weight(self.weights, "volume", 0.45)
        wf = _resolve_weight(self.weights, "tickflow", 0.35)
        wa = _resolve_weight(self.weights, "ta", 0.20)

        score = wv * f_vol + wf * f_flow + wa * f_ta

        # 모든 피처가 0이면 임계값 폴백(테스트 가능성 보장)
        if (f_vol, f_flow, f_ta) == (0.0, 0.0, 0.0):
            sym = str(_get(snapshot, "symbol", "NA"))
            price = float(_get(snapshot, "price", 0.0) or 0.0)
            prev = _state_prev_price.get(sym)
            if prev is not None and prev > 0:
                mom = (price / prev - 1.0)
                # 간단 모멘텀 보강
                score += max(-1.0, min(1.0, mom * 50.0)) * 0.2
            _state_prev_price[sym] = price
            if price <= self.BUY_MAX:
                score += 1.0 * 0.5
            elif price >= self.SELL_MIN:
                score -= 1.0 * 0.5

        # 정규화(과도치 방지)
        if score > 1.0:
            score = 1.0
        if score < -1.0:
            score = -1.0
        return float(score)

    # ===== 호환 메서드 =====
    def score(self, tick: Any) -> float:
        """백워드 호환: 일부 코드가 .score(tick)을 호출하므로 evaluate를 래핑."""
        # tick이 dict가 아니면 dict로 보강
        if not isinstance(tick, dict):
            snap = {"symbol": _get(tick, "symbol", "NA"), "price": _get(tick, "price", 0.0)}
        else:
            snap = tick
        return self.evaluate(snap)

    def score_with_detail(self, tick: Any) -> Tuple[float, Dict[str, Any]]:
        if not isinstance(tick, dict):
            snap = {"symbol": _get(tick, "symbol", "NA"), "price": _get(tick, "price", 0.0)}
        else:
            snap = tick
        # 상세 피처 계산(예외 안전)
        try:
            f_vol = float(volume_surge(snap))
        except Exception:
            f_vol = 0.0
        try:
            f_flow = float(tick_flow(snap))
        except Exception:
            f_flow = 0.0
        try:
            f_ta = float(ma_cross(snap))
        except Exception:
            f_ta = 0.0
        s = self.evaluate(snap)
        return s, {"volume": f_vol, "tickflow": f_flow, "ta": f_ta}


