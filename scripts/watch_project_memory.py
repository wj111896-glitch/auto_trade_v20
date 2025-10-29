# -*- coding: utf-8 -*-
"""
scripts/watch_project_memory.py
- docs/PROJECT_MEMORY.md 변경 감지 시 자동 git add/commit (간단 폴링 버전)
- 별도 라이브러리 불필요. 윈도우/맥/리눅스 공용.
"""
import os, time, subprocess, hashlib, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "docs", "PROJECT_MEMORY.md")
INTERVAL = 2.0  # seconds

def sha1(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()
    except FileNotFoundError:
        return ""

def run(cmd, cwd=None):
    return subprocess.call(cmd, cwd=cwd or ROOT, shell=True)

def main():
    print("[watch] start:", TARGET)
    prev = sha1(TARGET)
    while True:
        time.sleep(INTERVAL)
        cur = sha1(TARGET)
        if cur and cur != prev:
            print("[watch] detected change. committing...")
            run('git add "docs/PROJECT_MEMORY.md"')
            msg = "chore(memory): auto update PROJECT_MEMORY.md"
            run(f'git commit -m "{msg}"')
            prev = cur

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[watch] stopped.")
