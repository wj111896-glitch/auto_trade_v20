# -*- coding: utf-8 -*-
# obs/alert.py — Telegram helper (secret.json + env 모두 지원, secret 우선)
import os, json
import requests

# 프로젝트 루트
BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# 1) 기본값 (비어있게 시작)
TELEGRAM_TOKEN = "7645214310:AAFPWJQvL3pv-ZJydKeX8eKv7XQzPY03gfU"
CHAT_ID = "8489429622"

# 2) secret.json 먼저 읽기 (권장 경로)
secret_path = os.path.join(ROOT_DIR, "secret.json")
if os.path.exists(secret_path):
    try:
        with open(secret_path, "r", encoding="utf-8") as f:
            s = json.load(f) or {}
        TELEGRAM_TOKEN = (s.get("TG_BOT_TOKEN") or "").strip()
        CHAT_ID        = (s.get("TG_CHAT_ID") or "").strip()
    except Exception:
        # 파일이 깨졌거나 JSON 오류면 빈 값 유지
        TELEGRAM_TOKEN = TELEGRAM_TOKEN or ""
        CHAT_ID = CHAT_ID or ""

# 3) 환경변수가 있으면 마지막에 덮어쓰기(임시 테스트용)
_env_token = os.getenv("TG_BOT_TOKEN", "").strip()
_env_chat  = os.getenv("TG_CHAT_ID", "").strip()
if _env_token:
    TELEGRAM_TOKEN = _env_token
if _env_chat:
    CHAT_ID = _env_chat

def send_telegram(msg: str) -> bool:
    """텔레그램 텍스트 전송. 성공 True, 실패 False"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True}
    try:
        r = requests.post(url, data=data, timeout=8)
        return r.ok
    except Exception:
        return False

# ---- backward-compat alias (old code calls send_message) ----
def send_message(text: str) -> bool:
    return send_telegram(text)


__all__ = ["send_telegram", "TELEGRAM_TOKEN", "CHAT_ID"]

# ---- backward-compat alias (old demos use send_message) ----
def send_message(text: str) -> bool:
    return send_telegram(text)

