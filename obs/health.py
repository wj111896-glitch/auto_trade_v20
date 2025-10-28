# -*- coding: utf-8 -*-
# obs/health.py
import os
from datetime import datetime, timedelta
from typing import Iterable, Optional

def _writable(path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(path)
        return True
    except Exception:
        return False

def _recent_news_files(base_dir: str, days: int = 3) -> list[str]:
    targets = [
        os.path.join(base_dir, "news_logs"),
        os.path.join(base_dir, "news_logs", "digests"),
    ]
    files = []
    cutoff = datetime.now() - timedelta(days=days)
    for d in targets:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                if os.path.isfile(p) and datetime.fromtimestamp(os.path.getmtime(p)) >= cutoff:
                    files.append(p)
            except Exception:
                pass
    return files

def preflight_check(base_dir: str, symbols: Iterable[str], logger=None) -> bool:
    """
    실행 전 필수 경로/쓰기권한/기초 입력 점검.
    - 반드시 True 반환 시에만 메인 루프 진입.
    """
    ok = True
    def log(level: str, msg: str, extra: Optional[dict]=None):
        if logger:
            getattr(logger, level.lower())(msg, extra=extra or {})
        else:
            print(f"[{level}] {msg} | {extra or {}}")

    dirs = [
        os.path.join(base_dir, "logs"),
        os.path.join(base_dir, "reports"),
        os.path.join(base_dir, "news_logs"),
        os.path.join(base_dir, "news_logs", "digests"),
    ]
    for d in dirs:
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            ok = False
            log("ERROR", f"디렉터리 생성 실패: {d}", {"err": str(e)})

    # 쓰기권한 체크 (logs/reports)
    if not _writable(os.path.join(base_dir, "logs", ".write_test.tmp")):
        ok = False
        log("ERROR", "logs 쓰기 실패", {})
    if not _writable(os.path.join(base_dir, "reports", ".write_test.tmp")):
        ok = False
        log("ERROR", "reports 쓰기 실패", {})

    # 심볼 유효성(간단 체크)
    syms = list(symbols or [])
    if not syms:
        ok = False
        log("ERROR", "심볼 목록이 비어있습니다 (--symbols).", {})
    else:
        for s in syms:
            if not isinstance(s, str) or not s.strip():
                ok = False
                log("ERROR", f"심볼 형식 오류: {s}", {})

    # 최근 뉴스 파일 경고 (없어도 실행은 가능)
    news_files = _recent_news_files(base_dir, days=3)
    if not news_files:
        log("WARN", "최근 3일 뉴스 파일이 없어 뉴스 바이어스는 0으로 동작합니다.", {})

    if ok:
        log("INFO", "Preflight passed", {"symbols": syms})
    else:
        log("ERROR", "Preflight failed", {})
    return ok
