import os, sys, glob, datetime

BASE = r"C:\Users\kimta\auto_trade_v20"
NEWS = os.path.join(BASE, "news_logs")
DIG  = os.path.join(NEWS, "digests")
LOGO = os.path.join(BASE, "logs", "task_news_summary.out")
LOGE = os.path.join(BASE, "logs", "task_news_summary.err")

today = datetime.date.today().strftime("%Y-%m-%d")

def read_text(path: str, tail_only: int | None = None) -> str:
    if not os.path.exists(path): return ""
    text = ""
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            break
        except Exception:
            pass
    if text == "":
        with open(path, "r", encoding="cp949", errors="ignore") as f:
            text = f.read()
    return text[-tail_only:] if tail_only else text

def latest(pattern: str) -> str | None:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

checks: list[tuple[str, bool, str]] = []

# 1) 오늘 파일들
daily = os.path.join(NEWS, f"오늘_뉴스_요약_{today}.txt")
checks.append(("오늘 요약 파일", os.path.exists(daily), daily))

hold  = os.path.join(DIG,  f"holdings_{today}.md")
checks.append(("보유종목 리포트", os.path.exists(hold), hold))

srch  = os.path.join(DIG,  f"search_{today}.md")
checks.append(("키워드 리포트", os.path.exists(srch), srch))

# 2) 로그 완료(DONE)
log_tail = read_text(LOGO, tail_only=1000)
ok_log   = ("[DONE]" in log_tail) if log_tail else False
checks.append(("작업 로그 완료(DONE)", ok_log, LOGO))

# 3) 최신 커밋 요약
git_info = os.popen(
    f'git -C "{BASE}" log -1 --date=local --pretty="format:%ad %h %s"'
).read().strip()

print("\n=== AutoTradeV20 Health Check ===")
fail = False
for name, ok, path in checks:
    print(f"[{'OK' if ok else 'FAIL'}] {name} -> {path}")
    fail |= (not ok)
print("\n[INFO] 최근 커밋:", git_info or "(없음)")

# 텔레그램 알림
from obs.alert import send_message
summary = "\n".join([f"[{'OK' if ok else 'FAIL'}] {name}" for name, ok, _ in checks])
title   = "✅ AutoTradeV20 정상" if not fail else "⚠️ AutoTradeV20 점검 필요"
send_message(f"<b>{title}</b>\n{summary}")

# 에러 꼬리 필요시 출력
err_tail = read_text(LOGE, tail_only=1000)
if err_tail.strip():
    print("\n[ERR TAIL]\n", err_tail)

sys.exit(1 if fail else 0)

