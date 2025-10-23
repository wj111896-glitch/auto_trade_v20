import datetime
import os

def save_news_summary(summary_text: str):
    """
    뉴스 요약 텍스트를 프로젝트 내부 news_logs 폴더에 저장.
    매일 날짜별 파일 생성 (예: news_logs/오늘_뉴스_요약_2025-10-23.txt)
    """
    base_dir = os.path.join(os.path.dirname(__file__), "news_logs")
    os.makedirs(base_dir, exist_ok=True)

    today = datetime.date.today().strftime("%Y-%m-%d")
    filename = f"오늘_뉴스_요약_{today}.txt"
    path = os.path.join(base_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print(f"[INFO] 뉴스 요약 저장 완료 → {path}")
    return path


# === 테스트용 코드 ===
if __name__ == "__main__":
    sample = (
        "📅 오늘 주요 뉴스 요약\n\n"
        "- 코스피 2500선 회복, 외국인 순매수 지속\n"
        "- 삼성전자, AI 반도체 수요 호조\n"
        "- 미국 증시 혼조세, 연준 금리 동결 가능성↑"
    )
    save_news_summary(sample)
