# -*- coding: utf-8 -*-
"""
scoring/calibrator.py - 온라인 가중치 보정기(v0)
- 최근 성과(PnL%)를 누적해 작은 학습률로 feature 가중치를 미세 조정
- 안전장치: 1회 변경폭 클리핑, 음수 방지, 총합=1 정규화
"""
from __future__ import annotations
from typing import Dict
from collections import deque

class Calibrator:
    def __init__(self, lr: float = 0.02, hist: int = 100, clip: float = 0.05):
        self.lr = lr
        self.hist = hist
        self.clip = clip
        self._pnl = deque(maxlen=hist)

    # 전략이 실현 손익(%)을 알게 되는 시점마다 호출
    def record_pnl(self, pnl_pct: float) -> None:
        self._pnl.append(pnl_pct)

    def _signal(self) -> float:
        if not self._pnl:
            return 0.0
        avg = sum(self._pnl) / len(self._pnl)   # 최근 평균 수익률(%)
        # 대략 ±0.05(=±5%) 평균이면 ±1 근처 신호로 압축
        s = max(-1.0, min(1.0, avg * 20.0))
        return s

    def adjust(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        성과 좋음(+): 추세 민감(feature) ↑, 방어(feature) ↓ (소폭)
        성과 나쁨(-): 방어 ↑, 추세 ↓ (소폭)
        """
        s = self._signal()
        if s == 0.0:
            return weights

        w = dict(weights)
        delta = {
            "volume":   -0.5 * s,  # 방어(거래량) 가중
            "tickflow":  0.3 * s,  # 체결강도/흐름
            "ta":        0.2 * s,  # 기술지표
        }
        for k, d in delta.items():
            if k in w:
                change = self.lr * d
                # 1회 변경폭 제한(±clip)
                change = max(-self.clip, min(self.clip, change))
                w[k] += change

        # 음수 방지 + 총합 1.0로 정규화
        for k in w:
            w[k] = max(0.0, w[k])
        total = sum(w.values()) or 1.0
        for k in w:
            w[k] /= total
        return w
