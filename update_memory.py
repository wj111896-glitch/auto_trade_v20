# -*- coding: utf-8 -*-
"""
update_memory.py — PROJECT_MEMORY.md 자동 감지/수동 갱신 스크립트

기능 요약
- 변경 감지: Git 변경, 주요 파일(스크립트/테스트/허브 등) 변경 시 자동 갱신 제안
- 상태 수집: 최신 뉴스 로그 파일, 배치 스크립트 존재, 스모크 테스트 결과, 허브 DRY_RUN 지표
- 문서 갱신: docs/PROJECT_MEMORY.md 지정된 영역을 안전하게 업데이트(마커 기반)
- 커밋 옵션: 변경 시 자동 커밋 가능 (--commit)
- 수동 트리거: --force 로 강제 업데이트, --run-tests 로 스모크 테스트 실행

Windows/PowerShell에 최적화되어 있지만, 기본적으로 OS 무관하게 동작합니다.
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, List

# ====== 경로 설정 ======
REPO_ROOT = Path(__file__).resolve().parent
DOCS_DIR = REPO_ROOT / "docs"
MEMO_PATH = DOCS_DIR / "PROJECT_MEMORY.md"
NEWS_DIR = REPO_ROOT / "news_logs"
SCRIPTS_DIR = REPO_ROOT / "scripts"
TESTS_DIR = REPO_ROOT / "tests"
HUB_PATH = REPO_ROOT / "hub" / "hub_trade.py"

# ====== 업데이트 마커 ======
# 아래 마커 사이의 내용은 자동으로 대체됩니다. (수동 편집은 피하세요)
MARK_CURRENT = ("<!--AUTO:CURRENT-STATE:BEGIN-->", "<!--AUTO:CURRENT-STATE:END-->")
MARK_NEXT = ("<!--AUTO:NEXT-STEPS:BEGIN-->", "<!--AUTO:NEXT-STEPS:END-->")
MARK_GIT = ("<!--AUTO:GIT-SNAPSHOT:BEGIN-->", "<!--AUTO:GIT-SNAPSHOT:END-->")

DEFAULT_NEXT_STEPS = (
    "1. Kiwoom 실계좌 모드 연결 준비\n"
    "2. run_daytrade.py에 허브 자동 연결 추가\n"
    "3. daily report 자동 요약 템플릿 연동\n"
)

# ====== 유틸 ======

def run(cmd: List[str], cwd: Optional[Path] = None, capture: bool = True) -> Tuple[int, str, str]:
    """서브프로세스 실행 헬퍼 (UTF-8 강제 + 깨진 문자는 무시)."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        encoding="utf-8",   # ✅ Windows 콘솔 cp949 문제 방지
        errors="ignore",    # ✅ 디코딩 불가 문자는 무시
    )
    out, err = proc.communicate()
    return proc.returncode, out or "", err or ""


def git(*args: str) -> Tuple[int, str, str]:
    return run(["git", *args], cwd=REPO_ROOT)


def get_git_head() -> str:
    code, out, _ = git("rev-parse", "--short", "HEAD")
    return out.strip() if code == 0 else "unknown"


def get_git_status_changed() -> List[str]:
    """작업 트리 변경 파일 목록."""
    code, out, _ = git("status", "--porcelain")
    if code != 0:
        return []
    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # 예: ' M docs/PROJECT_MEMORY.md' → 경로만 추출
        path = line[3:]
        files.append(path)
    return files


def get_latest_news_file() -> Optional[Path]:
    if not NEWS_DIR.exists():
        return None
    candidates = sorted(NEWS_DIR.glob("오늘_뉴스_요약_*.txt"))
    return candidates[-1] if candidates else None


def check_bat_exists() -> bool:
    return (SCRIPTS_DIR / "run_news_8am.bat").exists()


def run_smoke_tests() -> Tuple[bool, str]:
    """tests/smoke_news.py 실행 (성공 여부, 로그)."""
    candidate = TESTS_DIR / "smoke_news.py"
    if not candidate.exists():
        return False, "tests/smoke_news.py 없음"
    # venv가 없다고 가정하고, 시스템 파이썬으로 실행
    code, out, err = run([sys.executable, str(candidate)], cwd=REPO_ROOT)
    ok = (code == 0)
    log = (out + "\n" + err).strip()
    return ok, log


def ensure_markers(text: str) -> str:
    """문서에 자동 섹션 마커가 없다면 삽입."""
    def insert_if_missing(t: str, begin: str, end: str, block_title: str) -> str:
        if begin in t and end in t:
            return t
        # 적절한 위치가 없다면 문서 끝에 추가
        block = (
            f"\n\n{block_title}\n{begin}\n(자동 업데이트 영역)\n{end}\n"
        )
        return t.rstrip() + block

    text = insert_if_missing(text, *MARK_CURRENT, "## 📅 현재 상태")
    text = insert_if_missing(text, *MARK_GIT, "## 🌀 Git 스냅샷")
    text = insert_if_missing(text, *MARK_NEXT, "## 🔧 다음 할 일")
    return text


def replace_between(text: str, begin: str, end: str, new_body: str) -> str:
    pattern = re.compile(re.escape(begin) + r"[\s\S]*?" + re.escape(end))
    return pattern.sub(begin + "\n" + new_body.rstrip() + "\n" + end, text)


def format_current_state(now: dt.datetime, news_path: Optional[Path], bat_ok: bool,
                         smoke_ok: Optional[bool], hub_ok: Optional[bool]) -> str:
    lines = [f"- 업데이트 시각: {now.strftime('%Y-%m-%d %H:%M:%S')} ({now.tzname() or 'local'})"]
    if news_path and news_path.exists():
        rel = news_path.relative_to(REPO_ROOT)
        lines.append(f"- 뉴스 자동 요약/저장: ✅ ({rel})")
    else:
        lines.append("- 뉴스 자동 요약/저장: ⚠️ 최근 파일 없음")
    lines.append(f"- scripts/run_news_8am.bat: {'✅ 존재' if bat_ok else '❌ 없음'}")
    if smoke_ok is True:
        lines.append("- tests/smoke_news.py: ✅ 통과")
    elif smoke_ok is False:
        lines.append("- tests/smoke_news.py: ❌ 실패")
    else:
        lines.append("- tests/smoke_news.py: ⏭️ 미실행")
    if hub_ok is True:
        lines.append("- hub/hub_trade.py DRY_RUN: ✅ 체결 로그 발견")
    elif hub_ok is False:
        lines.append("- hub/hub_trade.py DRY_RUN: ❌ 지표 없음")
    else:
        lines.append("- hub/hub_trade.py DRY_RUN: ⏭️ 미확인")
    return "\n".join(lines)


def check_hub_dry_run_hint() -> Optional[bool]:
    """간단히 로그 힌트만 탐색 (심층 파싱은 생략)."""
    # 가장 단순한 구현: news_logs/* 또는 repo 루트의 최근 로그 텍스트에서 키워드 존재 여부
    # 필요시 사용자 환경에 맞게 경로 조정 가능
    patterns = [
        REPO_ROOT.glob("**/*.log"),
        (REPO_ROOT / "news_logs").glob("*.txt"),
    ]
    keywords = ["DRY_RUN", "매수", "체결", "filled", "paper"]
    try:
        for it in patterns:
            for p in it:
                if not p.is_file() or p.stat().st_size > 2_000_000:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
                if any(k in text for k in keywords):
                    return True
        return False
    except Exception:
        return None  # 미확인


def format_git_snapshot(head: str, note: str | None = None) -> str:
    if note:
        return f"- 현재 Git 스냅샷: `{head}` ({note})"
    return f"- 현재 Git 스냅샷: `{head}`"


def load_or_init_memory() -> str:
    if MEMO_PATH.exists():
        return MEMO_PATH.read_text(encoding="utf-8")
    # 기본 템플릿 생성
    base = (
        "# PROJECT MEMORY — auto_trade_v20 (오부장 전용 요약)\n\n"
        "## 📅 현재 상태\n"
        f"{MARK_CURRENT[0]}\n(자동 업데이트 영역)\n{MARK_CURRENT[1]}\n\n"
        "## 🌀 Git 스냅샷\n"
        f"{MARK_GIT[0]}\n(자동 업데이트 영역)\n{MARK_GIT[1]}\n\n"
        "## 📂 폴더 구조\n"
        "- hub/hub_trade.py : 전략 허브\n"
        "- order/router.py : 주문 라우터\n"
        "- scoring/core.py : 스코어링 엔진\n"
        "- risk/core.py : 리스크 게이트\n"
        "- obs/log.py : 로깅 모듈\n"
        "- news_logs/ : 뉴스 결과 및 요약 저장 경로\n"
        "- scripts/ : 자동 실행 배치\n"
        "- tests/ : 스모크 테스트 모듈\n"
        "- common/config.py : 전역 설정 (DAYTRADE 포함)\n\n"
        "## 🔧 다음 할 일\n"
        f"{MARK_NEXT[0]}\n{DEFAULT_NEXT_STEPS}{MARK_NEXT[1]}\n"
    )
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    MEMO_PATH.write_text(base, encoding="utf-8")
    return base


def update_memory(run_tests: bool, note: Optional[str], commit: bool, dry_run: bool) -> bool:
    tz = dt.datetime.now().astimezone()
    head = get_git_head()
    changed = get_git_status_changed()

    news_file = get_latest_news_file()
    bat_ok = check_bat_exists()

    smoke_ok: Optional[bool] = None
    if run_tests:
        smoke_ok, smoke_log = run_smoke_tests()
        print("[smoke]", "PASS" if smoke_ok else "FAIL", "\n" + smoke_log[:1000])

    hub_ok = check_hub_dry_run_hint()

    # 문서 로드/마커 확보
    text = load_or_init_memory()
    text = ensure_markers(text)

    current_block = format_current_state(tz, news_file, bat_ok, smoke_ok, hub_ok)
    git_block = format_git_snapshot(head, note)

    new_text = text
    new_text = replace_between(new_text, *MARK_CURRENT, current_block)
    new_text = replace_between(new_text, *MARK_GIT, git_block)

    # 다음 할 일은 자동으로는 건드리지 않음. (원하면 --reset-next 로 기본값 복구)

    if dry_run:
        print("[dry-run] preview:\n" + new_text)
        return False

    # 변경 사항이 있을 때만 기록
    if new_text != text:
        # 백업
        backup = MEMO_PATH.with_suffix(".bak.md")
        MEMO_PATH.rename(backup) if MEMO_PATH.exists() else None
        MEMO_PATH.write_text(new_text, encoding="utf-8")
        print(f"[OK] PROJECT_MEMORY.md 업데이트 완료 → {MEMO_PATH}")
        if commit:
            code, out, err = git("add", str(MEMO_PATH.relative_to(REPO_ROOT)))
            if code != 0:
                print("[git] add 실패:", err)
            msg = f"chore(memory): auto update {tz.strftime('%Y-%m-%d %H:%M:%S')} ({head})"
            code, out, err = git("commit", "-m", msg)
            if code == 0:
                print("[git] commit:", out.strip())
            else:
                print("[git] commit 실패:", err.strip())
        return True
    else:
        print("[SKIP] 변경 없음")
        return False


def should_prompt_auto(changed_files: List[str]) -> bool:
    # 주요 파일 변화시 제안
    triggers = [
        "hub/", "order/", "scoring/", "risk/", "scripts/", "tests/", "common/", "news_logs/"
    ]
    return any(any(f.startswith(t) for t in triggers) for f in changed_files)


def main():
    ap = argparse.ArgumentParser(description="PROJECT_MEMORY.md 자동/수동 갱신")
    ap.add_argument("--force", action="store_true", help="강제 업데이트(변경 감지 무시)")
    ap.add_argument("--run-tests", action="store_true", help="스모크 테스트 실행 후 반영")
    ap.add_argument("--commit", action="store_true", help="갱신 후 자동 git commit")
    ap.add_argument("--note", type=str, default=None, help="Git 스냅샷 설명 메모")
    ap.add_argument("--dry-run", action="store_true", help="파일 변경 없이 결과 미리보기")
    args = ap.parse_args()

    changed = get_git_status_changed()
    if args.force:
        print("[force] 수동 트리거로 갱신 수행")
        update_memory(run_tests=args.run_tests, note=args.note, commit=args.commit, dry_run=args.dry_run)
        return

    if should_prompt_auto(changed):
        print("[auto] 주요 변경을 감지했습니다. PROJECT_MEMORY.md 갱신을 제안합니다.")
        update_memory(run_tests=args.run_tests, note=args.note, commit=args.commit, dry_run=args.dry_run)
    else:
        print("[idle] 주요 변경 없음 — 필요 시 --force 로 수동 갱신하세요.")


if __name__ == "__main__":
    main()
