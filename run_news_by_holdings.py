import os, datetime, re

BASE = os.path.dirname(__file__)
NEWS_DIR = os.path.join(BASE, "news_logs")
HOLDINGS_FILE = os.path.join(BASE, "holdings.txt")

def load_holdings(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            items.append(s)
    return items

def today_news_path() -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    fname = f"오늘_뉴스_요약_{today}.txt"
    return os.path.join(NEWS_DIR, fname)

def extract_for_holdings(holdings: list[str], news_path: str) -> dict[str, list[str]]:
    res = {h: [] for h in holdings}
    if not os.path.exists(news_path):
        return res
    with open(news_path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    for h in holdings:
        # 대소문자 구분 없이, 부분 일치(한글/영문/티커) 매칭
        pat = re.compile(re.escape(h), re.IGNORECASE)
        for ln in lines:
            if pat.search(ln):
                res[h].append(ln.strip())
    return res

def save_digest(matches: dict[str, list[str]]) -> str:
    os.makedirs(os.path.join(NEWS_DIR, "digests"), exist_ok=True)
    today = datetime.date.today().strftime("%Y-%m-%d")
    out = os.path.join(NEWS_DIR, "digests", f"holdings_{today}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 보유종목 뉴스 매칭 ({today})\n\n")
        empty = True
        for h, lines in matches.items():
            f.write(f"## {h}\n")
            if lines:
                empty = False
                for ln in lines:
                    f.write(f"- {ln}\n")
            else:
                f.write("- (오늘 매칭 없음)\n")
            f.write("\n")
        if empty:
            f.write("\n> 오늘은 보유종목 키워드와 매칭된 뉴스 문장이 없습니다.\n")
    return out

if __name__ == "__main__":
    holdings = load_holdings(HOLDINGS_FILE)
    if not holdings:
        print("[WARN] holdings.txt에 종목 키워드를 추가하세요 (한 줄에 하나).")
    news_path = today_news_path()
    matches = extract_for_holdings(holdings, news_path)
    out = save_digest(matches)
    print("[OK] digest ->", out)

py run_news_search.py 금리 환율 --since 1 --out search_%DATE%.md 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
