import os, requests

# secrets.env 로드: 배치(run_daily_news_8am.cmd)에서 환경변수로 주입됨
TELEGRAM_TOKEN = os.getenv("TG_TOKEN", "")
CHAT_ID        = os.getenv("TG_CHAT", "")

def send_message(msg: str):
    """텔레그램으로 간단한 텍스트 메시지 전송 (HTML 지원)."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[WARN] TG_TOKEN/TG_CHAT 없어서 전송 스킵")
        return
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=12)
        if r.status_code != 200:
            print("[ERR] Telegram 응답:", r.text)
    except Exception as e:
        print("[ERR] Telegram 예외:", e)

