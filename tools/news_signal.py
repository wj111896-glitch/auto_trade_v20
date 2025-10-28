# -*- coding: utf-8 -*-
# tools/news_signal.py
import os, glob, re
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# 간단 키워드 사전 (원하면 여기에 계속 추가)
POS_WORDS: List[str] = [
    "호재", "상승", "수주", "실적 개선", "증설", "수익성 개선", "목표가 상향", "수주 소식",
]
NEG_WORDS: List[str] = [
    "악재", "하락", "적자", "리콜", "감산", "가이던스 하향", "목표가 하향", "소송",
]

class NewsSignal:
    """
    news_logs/ 및 news_logs/digests/의 '최근 N일' 파일에서
    심볼/키워드별 감정 점수(-1.0~+1.0)를 추출.
    - 파일에 해당 키워드가 없으면 0.0
    - 간단한 빈도 기반이므로 안전하고 가볍습니다.
    """

    def __init__(self, base_dir: str, recency_days: int = 3, keyword_map: Optional[Dict[str, str]] = None):
        self.base_dir = base_dir
        self.recency_days = recency_days
        self.keyword_map = keyword_map or {}
        self.cache: Dict[str, float] = {}
        self._blob: str = ""

    def _latest_files(self) -> List[str]:
        paths: List[str] = []
        for pat in (
            os.path.join(self.base_dir, "news_logs", "*.txt"),
            os.path.join(self.base_dir, "news_logs", "digests", "*.md"),
        ):
            paths.extend(glob.glob(pat))
        cutoff = datetime.now() - timedelta(days=self.recency_days)

        def is_recent(p: str) -> bool:
            try:
                ts = datetime.fromtimestamp(os.path.getmtime(p))
                return ts >= cutoff
            except Exception:
                return False

        return [p for p in paths if is_recent(p)]

    def _score_text(self, text: str) -> float:
        def count_terms(terms: List[str]) -> int:
            c = 0
            for w in terms:
                pat = re.escape(w)
                c += len(re.findall(pat, text, flags=re.IGNORECASE))
            return c

        pos = count_terms(POS_WORDS)
        neg = count_terms(NEG_WORDS)
        if pos == 0 and neg == 0:
            return 0.0
        raw = (pos - neg) / max(1, pos + neg)   # -1~+1
        return max(-1.0, min(1.0, float(raw)))

    def load(self) -> None:
        files = self._latest_files()
        blob_parts: List[str] = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    blob_parts.append(fh.read())
            except Exception:
                # 파일 인코딩/락 문제는 조용히 무시
                pass
        self._blob = "\n".join(blob_parts)

    def score_for(self, sym_or_keyword: str) -> float:
        """
        심볼(예: '005930') 또는 키워드(예: '삼성전자') 점수 반환.
        매핑이 있으면 매핑 후 검색. 캐시됨.
        """
        key = sym_or_keyword
        if key in self.cache:
            return self.cache[key]

        if not self._blob:
            self.load()

        # 심볼 → 키워드 매핑
        query = self.keyword_map.get(sym_or_keyword, sym_or_keyword)

        pat = re.escape(query)
        ctxs = re.findall(rf".{{0,80}}{pat}.{{0,80}}", self._blob, flags=re.IGNORECASE)
        if not ctxs:
            self.cache[key] = 0.0
            return 0.0

        joined = "\n".join(ctxs)
        s = self._score_text(joined)
        self.cache[key] = s
        return s
