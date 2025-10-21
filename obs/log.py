from datetime import datetime

def log_info(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
