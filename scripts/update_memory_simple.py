# scripts/update_memory_simple.py
import subprocess, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "PROJECT_MEMORY.md"

def sh(cmd):
    return subprocess.run(cmd, cwd=ROOT, shell=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip()

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

text = f"# PROJECT MEMORY — auto_trade_v20\n\n> 자동 업데이트: {now}\n"
DOC.parent.mkdir(parents=True, exist_ok=True)
DOC.write_text(text, encoding="utf-8")

sh(f'git add "{DOC.relative_to(ROOT)}"')
sh('git commit -m "docs: auto update memory"')
sh('git push')

print("[OK] PROJECT_MEMORY.md 갱신 + 커밋 완료!")
