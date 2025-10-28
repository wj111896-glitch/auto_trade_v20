# -*- coding: utf-8 -*-
import os, datetime
base = r"C:\Users\kimta\auto_trade_v20\news_logs"
os.makedirs(base, exist_ok=True)
fname = f"오늘_뉴스_요약_{datetime.date.today().isoformat()}.txt"
path = os.path.join(base, fname)
with open(path, "a", encoding="utf-8") as f:
    f.write(f"[SMOKE] {datetime.datetime.now()} 생성 테스트\n")
print("[OK] news file:", path)
