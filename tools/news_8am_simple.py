# tools/news_8am_simple.py
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from obs.alert import send_telegram

now = dt.datetime.now()
msg = (
    f"🗞️ 뉴스 알림(테스트)\n"
    f"날짜: {now:%Y-%m-%d} (요일: {['월','화','수','목','금','토','일'][now.weekday()]})\n"
    f"시간: {now:%H:%M:%S}\n"
    f"상태: 파이프 OK ✅"
)

print("send:", send_telegram(msg))
