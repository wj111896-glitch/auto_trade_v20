# -*- coding: utf-8 -*-
# obs/alert.py — Telegram send helper (단일 함수: send_telegram)

import os
import requests

# 1) 환경변수 우선 사용 (없으면 하단의 기본값 사용)
TELEGRAM_TOKEN = os.getenv("7645214310:AAFPWJQvL3pv-ZJydKeX8eKv7XQzPY03gfU", "").strip()
CHAT_ID        = os.getenv("8498429622", "").strip()

# 2) 기본값(원한다면 여기에 직접 채워넣어도 됨)
#    예) TELEGRAM_TOKEN = "123456:ABCDEF..." ; CHAT_ID = "123456789"
# 빈 값이면 아래 함수에서 예외 대신 False 반환
# TELEGRAM_TOKEN = "여기_봇토큰"
# CHAT_ID        = "여기_챗ID"

def send_telegram(msg: str) -> bool:
    """텔레그램으로 텍스트 메시지를 전송. 성공시 True, 실패시 False."""
    token = TELEGRAM_TOKEN
    chat  = CHAT_ID
    if not token or not chat:
        # 설정이 비어 있으면 False 반납 (예외 대신)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat,
        "text": msg,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, data=data, timeout=8)
        return r.ok
    except Exception:
        return False

__all__ = ["send_telegram"]

