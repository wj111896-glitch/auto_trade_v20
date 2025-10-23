# run_news_search.py
import argparse, os, re, glob, datetime
from typing import List, Tuple

BASE = os.path.dirname(__file__)
NEWS_DIR = os.path.join(BASE, "news_logs")

FNAME_PREFIX = "오늘_뉴스_요약_"
FNAME_FMT = FNAME_PREFIX + "%Y-%m-%d.txt"

def parse_args():
    p = argparse.ArgumentParser(
        description="news_logs 폴더에서 다중 키워드로 뉴스 줄 추출"
    )
    p.add_argument("keywords", nargs="+", help="검색 키워드들 (예: 금리 환율 삼성전자)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--any", action="store_true", help="키워드 중 하나라도 포함(OR, 기본)")
    mode.add_argument("--all", action="store_true", help="모든 키워드 포함(AND)")
    date = p.add_mutually_exclusive_group()
    date.add_argument("--today", action="store_true", help="오늘 파일만 검색")
    date.add_argument("--since", type=int, help="최근 N일 간 파일만 검색")
    p.add_argument("--from", dest="date_from", type=str, help="시작일 YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", type=str, help="종료일 YYYY-MM-DD")
    p.add_argument("--whole-word", action="store_true", help="단어 경계 일치")
    p.add_argument("--case-sensitive", action="store_true", help="대소문자 구분")
    p.add_argument("--out", type=str, help="결과를 파일로 저장(.txt/.md)")
    return p.parse_args()

def list_news_files() -> List[str]:
    return sorted(glob.glob(os.path.join(NEWS_DIR, f"{FNAME_PREFIX}*.txt")))

def extract_date_from_name(path: str) -> datetime.date | None:
    bn = os.path.basename(path)
    try:
        s = bn.replace(FNAME_PREFIX, "").replace(".txt", "")
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def in_range(d: datetime.date, args) -> bool:
    today = datetime.date.today()
    if args.today:
        return d == today
    if args.since is not None:
        return d >= (today - datetime.timedelta(days=args.since))
    d0 = datetime.date.fromisoformat(args.date_from) if args.date_from else None
    d1 = datetime.date.fromisoformat(args.date_to) if args.date_to else None
    if d0 and d < d0: return False
    if d1 and d > d1: return False
    return True

def build_patterns(keywords: List[str], whole_word: bool, case_sensitive: bool) -> List[re.Pattern]:
    flags = 0 if case_sensitive else re.IGNORECASE
    pats = []
    for kw in keywords:
        esc = re.escape(kw)
        if whole_word:
            # 한글/영문/숫자 경계를 넓게: \b 대체
            pat = rf"(?<!\w){esc}(?!\w)"
        else:
            pat = esc
        pats.append(re.compile(pat, flags))
    return pats

def line_matches(line: str, patterns: List[re.Pattern], require_all: bool) -> Tuple[bool, List[Tuple[int,int,re.Pattern]]]:
    hits = []
    for p in patterns:
        m = list(p.finditer(line))
        if m:
            hits.extend([(mm.start(), mm.end(), p) for mm in m])
        elif require_all:
            return False, []
    return (True if (hits or not require_all) else False), hits

def highlight(line: str, hits: List[Tuple[int,int,re.Pattern]]) -> str:
    # 겹치는 하이라이트 정리 후 **굵게**
    if not hits: return line
    hits = sorted(hits, key=lambda x: x[0])
    out, last = [], 0
    for s, e, _ in hits:
        if s < last:  # overlap skip
            continue
        out.append(line[last:s])
        out.append("**" + line[s:e] + "**")
        last = e
    out.append(line[last:])
    return "".join(out)

def main():
    args = parse_args()
    files = list_news_files()
    if not files:
        print("[WARN] news_logs 폴더에 파일이 없습니다.")
        return

    pats = build_patterns(args.keywords, args.whole_word, args.case_sensitive)
    require_all = args.all and not args.any

    results = []
    for path in files:
        d = extract_date_from_name(path)
        if not d or not in_range(d, args): 
            continue
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]
        matched_lines = []
        for ln in lines:
            ok, hits = line_matches(ln, pats, require_all)
            if ok and hits:
                matched_lines.append(highlight(ln, hits))
        if matched_lines:
            results.append((path, matched_lines))

    if not results:
        print("[INFO] 매칭 결과가 없습니다.")
        return

    # 콘솔 출력
    for path, lines in results:
        print(f"\n=== {os.path.basename(path)} ===")
        for ln in lines:
            print(" -", ln)

    # 파일 저장 옵션
    if args.out:
        out_path = args.out
        if not os.path.isabs(out_path):
            out_path = os.path.join(NEWS_DIR, "digests", out_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# 키워드 검색 결과\n\n")
            f.write(f"- 검색 키워드: {', '.join(args.keywords)}\n")
            f.write(f"- 모드: {'ALL' if require_all else 'ANY'}\n\n")
            for path, lines in results:
                f.write(f"## {os.path.basename(path)}\n")
                for ln in lines:
                    f.write(f"- {ln}\n")
                f.write("\n")
        print("[OK] 저장:", out_path)

if __name__ == "__main__":
    main()
