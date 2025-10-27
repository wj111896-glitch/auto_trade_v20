import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from obs.alert import send_telegram
print("send:", send_telegram("✅ telegram_test.py: 연결 테스트"))
