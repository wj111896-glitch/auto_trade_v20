# scripts/auto_mem_update.py
# -*- coding: utf-8 -*-
import os, sys, subprocess, datetime, json, textwrap, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "PROJECT_MEMORY.md"
BAK = ROOT / "docs" / f"PROJECT_MEMORY.bak.md"
TZ = datetime.timezone(datetime.timedelta(hours=9))  # KST

SECTIONS_WATCH = [
    "hub/hub_trade.py", "run_daytrade.py",
    "scoring/core.py", "risk/core.py",
    "order/router.py", "market/price.py",
    "obs/log.py", "scripts", "news_logs", "logs"
]

def sh(cmd, check=True):
    result = subprocess.run(cmd, cwd=ROOT, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and result.returncode != 0:
        print(result.stdout)
        raise SystemExit(result.returncode)
    return result.stdout.strip()

def git_info():
    try:
        head = sh("git rev-parse --short HEAD")
        branch = sh("git rev-parse --abbrev-ref HEAD")
        dt = sh("git show -s --format=%ci HEAD")
    except SystemExit:
        head, branch, dt = "unknown", "unknown", ""
    return head, branch, dt

def changed_files():
    out = sh("git status --porcelain", check=False)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    return lines

def tree_preview():
    lines = []
    for p in SECTIONS_WATCH:
        path = ROOT / p
        if path.is_dir():
            files = sorted([str(Path(p)/f.name) for f in path.iterdir() if f.is_file()])
            lines.append(f"├─ {p}/")
            for f in files[:20]:
                lines.append(f"│  └─ {Path(f).name}")
            if len(files) > 20:
                lines.append(f"│  └─ ... (+{len(files)-20})")
        elif path.exists():
            lines.append(f"├─ {p}")
    return "\n".join(lines)

def now_kst():
    return datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

def generate(note=""):
    head, branch, dt = git_info()
    changed = changed_files()
    file_tree = tree_preview()

    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")

    body = f"""# PROJECT MEMORY — auto_trade_v20

> 마지막 업데이트: {today} (KST)

## ✅ 현재 상태 (자동 생성 요약)

* Git: `{head}` on `{branch}` (HEAD: {dt})
* 변경 대기: {len(changed)} files
* 생성시각: {now_kst()}

## 📂 주요 파일/폴더 스냅샷
