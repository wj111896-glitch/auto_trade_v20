# -*- coding: utf-8 -*-
# obs/metrics.py
from typing import Dict

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

class BiasMeter:
    """
    뉴스 바이어스를 점수에 보정하고, 세션 통계를 집계하는 훅.
    - adjust()는 (보정된 점수, 이번 틱 적용값) 을 반환합니다.
    - summary_dict()는 전체/심볼별 평균 적용값을 제공합니다.
    """
    def __init__(self, gain: float = 0.10, logger=None):
        self.gain = float(gain)
        self.log = logger

        # 전체 집계
        self.hits = 0
        self.sum_applied = 0.0
        self.max_applied = 0.0
        self.min_applied = 0.0

        # 심볼별 집계
        # sym -> {"hits":int, "sum":float, "max":float, "min":float}
        self.per_symbol: Dict[str, Dict[str, float]] = {}

    def adjust(self, score_raw: float, sym: str, news) -> tuple[float, float]:
        """return: (score_final, bias_applied)"""
        try:
            raw = float(news.score_for(sym))  # -1.0 ~ +1.0
        except Exception:
            raw = 0.0

        applied = self.gain * raw
        score = _clamp01(score_raw + applied)

        if raw != 0.0:
            # 전체 집계
            self.hits += 1
            self.sum_applied += applied
            if self.hits == 1:
                self.max_applied = applied
                self.min_applied = applied
            else:
                self.max_applied = max(self.max_applied, applied)
                self.min_applied = min(self.min_applied, applied)

            # 심볼별 집계
            ps = self.per_symbol.get(sym)
            if ps is None:
                ps = {"hits": 0, "sum": 0.0, "max": applied, "min": applied}
                self.per_symbol[sym] = ps
            ps["hits"] += 1
            ps["sum"] += applied
            ps["max"] = max(ps["max"], applied)
            ps["min"] = min(ps["min"], applied)

            # 로깅(선택)
            if self.log:
                try:
                    self.log.info(
                        "NEWS_BIAS",
                        extra={
                            "sym": sym,
                            "bias_applied": round(applied, 4),
                            "score_before": round(score_raw, 4),
                            "score_after": round(score, 4),
                        },
                    )
                except Exception:
                    pass

        return score, applied

    def summary_dict(self) -> dict:
        avg = (self.sum_applied / self.hits) if self.hits > 0 else 0.0
        # 심볼별 평균 적용값만 간단 노출
        sym_avg = {}
        for sym, stat in self.per_symbol.items():
            if stat["hits"] > 0:
                sym_avg[sym] = round(stat["sum"] / stat["hits"], 4)

        return {
            "news_bias_hits": self.hits,
            "news_bias_avg_applied": round(avg, 4),
            "news_bias_max_applied": round(self.max_applied, 4) if self.hits else 0.0,
            "news_bias_min_applied": round(self.min_applied, 4) if self.hits else 0.0,
            "news_bias_symbols": sym_avg,  # {"005930": 0.028, ...}
        }
