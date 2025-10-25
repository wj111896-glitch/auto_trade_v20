from .weights import Weights
from .features.volume import volume_surge
from .features.tickflow import tick_flow
from .features.ta import ma_cross

class ScoreEngine:
    def __init__(self, weights: Weights | None = None):
        self.weights = weights or Weights()

    def evaluate(self, snapshot) -> float:
        s = 0.0
        s += self.weights.volume   * volume_surge(snapshot)
        s += self.weights.tickflow * tick_flow(snapshot)
        s += self.weights.ta       * ma_cross(snapshot)
        return s

# ==== Compatibility layer for run_daytrade.py (robust weights) ====
# 일부 버전에서는 ScoreEngine에 .score() / .score_with_detail()가 없거나
# self.weights 구조가 객체형/딕셔너리형/중첩형(예: {"value":0.45})일 수 있음.
# 어떤 형태라도 안전하게 처리하도록 보완.

def _coerce_float(val, default):
    # 숫자면 OK
    if isinstance(val, (int, float)):
        return float(val)
    # 문자열이면 시도
    if isinstance(val, str):
        try:
            return float(val)
        except Exception:
            return float(default)
    # 객체에 value 속성이 있으면 사용
    if hasattr(val, "value"):
        try:
            return float(val.value)
        except Exception:
            return float(default)
    # 딕셔너리면 여러 키 후보 검사
    if isinstance(val, dict):
        for k in ("value", "val", "w", "weight", "coef"):
            if k in val:
                try:
                    return float(val[k])
                except Exception:
                    pass
        # 숫자 하나만 있으면 그걸 쓰기
        for v in val.values():
            if isinstance(v, (int, float, str)):
                try:
                    return float(v)
                except Exception:
                    continue
        return float(default)
    # 모르면 기본값
    return float(default)

def _resolve_weight(self, key, default):
    wsrc = getattr(self, "weights", None)
    if wsrc is None:
        return float(default)
    # 딕셔너리 형태
    if isinstance(wsrc, dict):
        return _coerce_float(wsrc.get(key, default), default)
    # 객체 형태 with to_dict()
    if hasattr(wsrc, "to_dict"):
        try:
            d = wsrc.to_dict() or {}
        except Exception:
            d = {}
        return _coerce_float(d.get(key, default), default)
    # 일반 객체 속성
    if hasattr(wsrc, key):
        return _coerce_float(getattr(wsrc, key), default)
    return float(default)

try:
    ScoreEngine  # noqa: F821
except NameError:
    pass
else:
    if not hasattr(ScoreEngine, "score"):
        def _rt_score(self, tick):
            """
            매우 경량의 fallback 점수:
            - volume: tick.volume을 500 기준으로 정규화
            - tickflow: 직전 가격 대비 변화율을 스케일
            - ta: 모멘텀 부호(+1/0/-1)
            """
            # --- 피처 ---
            vol = getattr(tick, "volume", 500)
            price = float(getattr(tick, "price", 0.0) or 0.0)

            vol_feat = max(-1.0, min(1.0, (float(vol) - 500.0) / 500.0))

            prev = getattr(self, "_prev_price", None)
            if not prev or prev <= 0:
                mom = 0.0
            else:
                mom = (price / prev - 1.0)
            tickflow_feat = max(-1.0, min(1.0, mom * 50.0))
            ta_feat = 1.0 if mom > 0 else (-1.0 if mom < 0 else 0.0)

            self._prev_price = price  # 다음 계산 대비 저장

            # --- 가중치(형태 무관 안전 추출) ---
            wv = _resolve_weight(self, "volume",   0.45)
            wt = _resolve_weight(self, "tickflow", 0.35)
            wa = _resolve_weight(self, "ta",       0.20)

            score = wv * vol_feat + wt * tickflow_feat + wa * ta_feat
            return max(-1.0, min(1.0, score))
        ScoreEngine.score = _rt_score

    if not hasattr(ScoreEngine, "score_with_detail"):
        def _rt_score_with_detail(self, tick):
            s = self.score(tick)
            return s, {"volume": "auto", "tickflow": "auto", "ta": "auto"}
        ScoreEngine.score_with_detail = _rt_score_with_detail
# ==== End of compatibility layer ====
