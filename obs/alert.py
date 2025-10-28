# -*- coding: utf-8 -*-
# obs/alert.py — Telegram helper (secret.json + env 모두 지원, secret 우선)
import os, json
import requests

# 프로젝트 루트
BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# 1) 기본값 (빈 값으로 시작 — 하드코딩 금지!)
TELEGRAM_TOKEN = ""
CHAT_ID = ""

# 2) secret.json 먼저 읽기 (권장 경로: <repo>/secret.json)
# {
#   "TG_BOT_TOKEN": "123:ABC...",
#   "TG_CHAT_ID":   "123456789"
# }
secret_path = os.path.join(ROOT_DIR, "secret.json")
if os.path.exists(secret_path):
    try:
        with open(secret_path, "r", encoding="utf-8") as f:
            s = json.load(f) or {}
        TELEGRAM_TOKEN = (s.get("TG_BOT_TOKEN") or "").strip() or TELEGRAM_TOKEN
        CHAT_ID        = (s.get("TG_CHAT_ID") or "").strip()   or CHAT_ID
    except Exception:
        # 파일이 깨졌으면 그냥 지나감(빈 값 유지)
        pass

# 3) 환경변수가 있으면 마지막에 덮어쓰기(로컬/임시 테스트용)
#   set TG_BOT_TOKEN=...
#   set TG_CHAT_ID=...
_env_token = os.getenv("TG_BOT_TOKEN", "").strip()
_env_chat  = os.getenv("TG_CHAT_ID", "").strip()
if _env_token:
    TELEGRAM_TOKEN = _env_token
if _env_chat:
    CHAT_ID = _env_chat

def send_telegram(msg: str) -> bool:
    """텔레그램 텍스트 전송. 성공 True, 실패 False"""
    token = (TELEGRAM_TOKEN or "").strip()
    chat  = (CHAT_ID or "").strip()
    if not token or not chat:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat, "text": msg, "disable_web_page_preview": True}
    try:
        r = requests.post(url, data=data, timeout=8)
        return bool(r.ok)
    except Exception:
        return False

# 과거 코드 호환 (alias)
def send_message(text: str) -> bool:
    return send_telegram(text)

__all__ = ["send_telegram", "send_message", "TELEGRAM_TOKEN", "CHAT_ID"]

