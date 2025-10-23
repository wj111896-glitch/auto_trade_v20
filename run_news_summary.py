# -*- coding: utf-8 -*-
import os, datetime, urllib.request, xml.etree.ElementTree as ET
from collections import Counter, defaultdict
import re

FEEDS = [
    ("Top",  "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"),
    ("Biz",  "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"),
    ("Tech", "https://news.google.com/rss/headlines/section/technology?hl=ko&gl=KR&ceid=KR:ko"),
]

SAVE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "NewsLogs")
os.makedirs(SAVE_DIR, exist_ok=True)
today = datetime.datetime.now().strftime("%Y-%m-%d")
path = os.path.join(SAVE_DIR, f"오늘 뉴스 요약_{today}.txt")

# ---------------- 관심 키워드 (화이트리스트) ----------------
# ---------------- 관심 키워드 (화이트리스트) ----------------
FOCUS_TERMS = [
    # 거시경제
    "금리","기준금리","환율","달러","엔화","위안화","원화","물가","인플레이션","유가","원유","WTI","브렌트",
    "국채","국채10년","채권","연준","연방준비","GDP","CPI","PPI","PCE","고용","실업","소비","경상수지","무역수지",

    # 주식/지수
    "코스피","코스닥","나스닥","다우","S&P","MSCI","VIX","선물","옵션","ETF","리츠","공매도","기관","외국인","개인",

    # 산업/테마
    "반도체","메모리","파운드리","AI","엔비디아","삼성전자","하이닉스","TSMC","인텔","테슬라","전기차","배터리","2차전지",
    "태양광","풍력","수소","원자력","신재생에너지","로봇","바이오","제약","리튬","희토류","디스플레이","모바일",

    # 자산/금융시장
    "부동산","주택","청약","전세","리츠","금","은","비트코인","가상자산","원자재","달러인덱스","환헤지","유동성",

    # 글로벌 경제
    "미국","중국","일본","유럽","한국","ECB","BOJ","BOE","OPEC","IMF","MSCI","무역전쟁","관세","경제제재","수출규제",
]


# ---------------- 불용어/매체/도메인 필터 + 가중치 ----------------
STOPWORDS_KR = {
    "오늘","내일","오전","오후","속보","단독","종합","영상","사진","포토","인터뷰","전문",
    "기자","앵커","칼럼","사설","오피니언","이슈","논란","추가","관련","전체","현장",
    "한국","대한민국","정부","정치","사회","국내","해외",
}
BAD_SUFFIXES = ("신문","일보","경제","방송","뉴스","TV","데일리","연합뉴스","저널","투데이","타임즈","미디어","코리아")
BAD_PUBLISHERS = {
    "한겨레","경향신문","조선일보","중앙일보","동아일보","매일경제","한국경제","서울경제","머니투데이",
    "세계일보","한국일보","국민일보","연합뉴스","지디넷코리아","ZDNet","ZDNET","KBS","MBC","SBS","JTBC","YTN","MBN","채널A","조선비즈"
}
# 도메인/URL 파편 제거용
DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9-]+\.(?:co|com|kr|net|org|biz|news)(?:\.[a-z]{2})?", re.I)

# 영어 토큰: 화이트리스트만 통과
EN_WHITELIST = {"ai","gdp","cpi","pce","ppi","fed","opec","wti","brent","nasdaq","dow","s&p","kopsi","kospi","kosdaq"}
def is_allowed_en(word: str) -> bool:
    w = word.lower()
    return w in EN_WHITELIST

BOOST_TERMS = {
    "금리","기준금리","환율","달러","원화","인플레이션","물가","유가","국채","채권","연준",
    "코스피","코스닥","나스닥","다우","S&P","지수","상승","하락","급등","급락",
    "반도체","메모리","파운드리","AI","엔비디아","테슬라","전기차","배터리","2차전지",
    "수출","무역수지","경상수지","GDP","고용","실업","부동산","주택","청약",
}

def fetch_rss(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        items = []
        for it in root.findall(".//item"):
            title = (it.findtext("title") or "").strip()
            # 매체명이 뒤에 붙는 " - 지디넷코리아" 같은 패턴 제거
            title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
            # 드문 경우 제목 내 url/도메인 제거
            title = DOMAIN_RE.sub("", title).strip()
            link  = (it.findtext("link") or "").strip()
            items.append((title, link))
        return items
    except Exception as e:
        return [("[수집 실패] " + str(e), "")]

def clean_text(txt: str) -> str:
    txt = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def token_filter(w: str) -> bool:
    if len(w) < 2 or w.isdigit():
        return False
    if DOMAIN_RE.fullmatch(w):          # 도메인 토큰 제거
        return False
    if w in STOPWORDS_KR or w in BAD_PUBLISHERS:
        return False
    for suf in BAD_SUFFIXES:
        if w.endswith(suf):
            return False
    # 영어 토큰은 허용 목록만
    if re.fullmatch(r"[A-Za-z&]+", w) and not is_allowed_en(w):
        return False
    return True

def tokenize(title: str):
    toks0 = clean_text(title).split()
    toks = [w for w in toks0 if token_filter(w)]
    # 빅그램 생성
    bigrams = []
    for i in range(len(toks) - 1):
        a, b = toks[i], toks[i+1]
        if token_filter(a) and token_filter(b):
            bigrams.append(f"{a} {b}")
    return toks, bigrams

def extract_keywords(titles, top_n=10):
    uni = Counter(); bi = Counter()
    for t, _ in titles:
        toks, bigs = tokenize(t)
        uni.update(toks); bi.update(bigs)
    # 가중치
    for term in BOOST_TERMS:
        if term in uni:
            uni[term] += 2
    mix = Counter(uni)
    for k, v in bi.items():
        mix[k] += int(v * 2)  # 빅그램 가중
    common = mix.most_common(top_n)
    return ", ".join([f"{w}({c})" for w, c in common]) if common else "(키워드 없음)"

def norm(s: str) -> str:
    return clean_text(s).lower().replace(" ", "")

def extract_focus_hits(titles, top_per_term=2):
    hits = defaultdict(list)
    titles_norm = [(t, l, norm(t)) for t, l in titles]
    focus_norm = [(term, norm(term)) for term in FOCUS_TERMS]
    for term, nterm in focus_norm:
        if not nterm:
            continue
        for t_raw, link, tnorm in titles_norm:
            if nterm in tnorm:
                hits[term].append((t_raw, link))
                if len(hits[term]) >= top_per_term:
                    break
    lines = []
    for term in FOCUS_TERMS:
        if term in hits:
            samples = "\n    ".join([f"- {t}\n      {l}" for t, l in hits[term][:top_per_term]])
            lines.append(f"{term} ({len(hits[term])}건)\n    {samples}")
    return "\n".join(lines) if lines else "(관심 키워드 기사 없음)"

def summarize_titles(titles, k=8):
    seen, out = set(), []
    for title, link in titles:
        if title in seen:
            continue
        seen.add(title)
        out.append(f"- {title}\n  {link}")
        if len(out) >= k:
            break
    return "\n".join(out) if out else "- (헤드라인 없음)"

def main():
    sections = []
    all_titles = []
    for name, url in FEEDS:
        items = fetch_rss(url)
        all_titles.extend(items)
        sections.append(f"◆ {name}\n{summarize_titles(items)}")

    focus_block = extract_focus_hits(all_titles, top_per_term=2)
    keywords = extract_keywords(all_titles)

    header  = f"=== 오늘 뉴스 요약 ({today}) ===\n생성시각: {datetime.datetime.now():%H:%M:%S}\n"
    focus   = f"\n🎯 관심 키워드 (건수 + 대표 기사)\n{focus_block}\n"
    summary = f"\n🧠 주요 키워드 TOP 10\n{keywords}\n\n"
    body    = "\n\n".join(sections)

    mode = "x" if not os.path.exists(path) else "a"
    with open(path, mode, encoding="utf-8") as f:
        if mode == "x":
            f.write(header)
        else:
            f.write("\n\n--- 추가 기록 ---\n")
            f.write(f"(갱신시각: {datetime.datetime.now():%H:%M:%S})\n")
        f.write(focus)
        f.write(summary)
        f.write(body)
        f.write("\n")

    print("[NEWS] 파일 생성/갱신:", path)

if __name__ == "__main__":
    main()
