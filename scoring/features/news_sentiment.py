# -*- coding: utf-8 -*-
"""
뉴스 감정 피처 (초기 버전)
- 원리: news_logs 폴더의 최신 파일(또는 sentiment_index.json)을 읽어
        심볼(코드/별칭)과 매칭되는 문장의 감정을 -1.0 ~ +1.0로 산출.
- 의존: 외부 라이브러리 없음 (키워드 기반 간단 감정 사전)
- 없으면 0.0(중립) 반환 → 안전한 기본값
"""
from __future__ import annotations
import json, re
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[2]   # project root
NEWS_DIR = ROOT / "news_logs"
SENTI_FILE = NEWS_DIR / "sentiment_index.json"   # 선택 사항(있으면 최우선)
ALIASES_FILE = NEWS_DIR / "aliases.json"         # 선택 사항(티커-명칭 매핑)

# --- 간단 감정 사전 (초기 버전: 필요시 자유 추가/수정) ---
POS = {"호재","반등","상향","증익","상승","강세","수주","최대","신고가","확대","돌파","개선","好"}
NEG = {"악재","하향","감익","하락","약세","적자","부진","최저","경고","축소","추락","리스크","불확실"}

# --- 유틸 ---
_WHITESPACE = re.compile(r"\s+")

def _load_aliases() -> dict:
    """심볼 코드 → 이름/별칭 세트. (없으면 빈 dict)"""
    try:
        if ALIASES_FILE.exists():
            data = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
            # {"005930":["삼성전자","삼성"]} 형태 기대
            return {k: set(v if isinstance(v, list) else [v]) for k, v in data.items()}
    except Exception:
        pass
    return {}

def _latest_news_text() -> str:
    """news_logs 폴더에서 가장 최근 텍스트 파일 내용을 통으로 읽음."""
    if not NEWS_DIR.exists():
        return ""
    txts = sorted(NEWS_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not txts:
        return ""
    try:
        return txts[0].read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _from_sentiment_index(symbol: str, now: datetime) -> float:
    """
    sentiment_index.json이 있을 경우 우선사용.
    포맷 예:
      {
        "005930": [{"ts": "2025-10-28T07:55:00", "score": 0.6}, ...],
        "000660": [...]
      }
    점수는 시간감쇠를 적용(최근일수록 가중).
    """
    if not SENTI_FILE.exists():
        return 0.0
    try:
        data = json.loads(SENTI_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0.0
    items = data.get(symbol) or []
    if not items:
        return 0.0

    # 간단 시간감쇠: 6시간 half-life
    def decay(dt: datetime) -> float:
        hours = max(0.0, (now - dt).total_seconds() / 3600.0)
        return 0.5 ** (hours / 6.0)

    acc, wsum = 0.0, 0.0
    for it in items:
        try:
            ts = datetime.fromisoformat(it.get("ts"))
            sc = float(it.get("score", 0.0))
            w = decay(ts)
            acc += sc * w
            wsum += w
        except Exception:
            continue
    return acc / wsum if wsum > 0 else 0.0

def _kw_sentiment_for_symbol(symbol: str, text: str, aliases: set[str]) -> float:
    """
    키워드 방식 감정: 심볼/별칭이 포함된 문장만 스캔하여
    (POS-NEG)/(POS+NEG) 로 점수화. 문장 없으면 0.
    """
    if not text:
        return 0.0

    # 간단 문장 분리 (마침표/개행 기준)
    sentences = re.split(r"[.\n\r]+", text)
    target_sents = []
    for s in sentences:
        s2 = _WHITESPACE.sub(" ", s).strip()
        if not s2:
            continue
        # 심볼 코드 또는 별칭이 포함된 문장만 취합
        if symbol in s2 or any(alias in s2 for alias in aliases):
            target_sents.append(s2)

    if not target_sents:
        return 0.0

    pos, neg = 0, 0
    for s in target_sents:
        u = s.upper()
        # 영문 대소문자 무시, 한글은 그대로
        pos += sum(1 for k in POS if k in s)
        neg += sum(1 for k in NEG if k in s)
        # 보너스: + / - 기호가 포함된 %변화 문구
        if re.search(r"\+\d+(\.\d+)?\%", s):
            pos += 1
        if re.search(r"-\d+(\.\d+)?\%", s):
            neg += 1

    if pos == 0 and neg == 0:
        return 0.0
    score = (pos - neg) / float(pos + neg)
    # 범위 클램프
    return max(-1.0, min(1.0, score))

# === 공개 API ===
def score(symbol: str, now: datetime | None = None) -> float:
    """
    공개 스코어 함수: -1.0(매우 부정) ~ +1.0(매우 긍정)
    우선순위: sentiment_index.json → 최신 뉴스 텍스트 키워드 매칭
    """
    now = now or datetime.now()
    # 1) 인덱스 우선
    s = _from_sentiment_index(symbol, now)
    if s != 0.0:
        return float(max(-1.0, min(1.0, s)))

    # 2) 키워드 추론
    text = _latest_news_text()
    aliases_map = _load_aliases()
    aliases = aliases_map.get(symbol, set())
    return _kw_sentiment_for_symbol(symbol, text, aliases)

def score_with_decay(symbol: str, ts: datetime, now: datetime | None = None) -> float:
    """
    이벤트 시각(ts) 기준 감쇠 반영 스코어. (옵션)
    최근일수록 영향↑, 오래되면 영향↓
    """
    base = score(symbol, now)
    now = now or datetime.now()
    hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    decay = 0.5 ** (hours / 6.0)  # half-life 6h
    return base * decay
