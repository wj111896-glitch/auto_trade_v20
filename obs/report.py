# -*- coding: utf-8 -*-
# obs/report.py
import os, json
from datetime import datetime

def save_day_report(summary: dict, base_dir: str):
    """
    세션 요약(summary)을 JSON과 텍스트 리포트로 저장합니다.
    C:\...\auto_trade_v20\reports\day_report_YYYY-MM-DD_HHMMSS.{json,txt}
    """
    rep_dir = os.path.join(base_dir, "reports")
    os.makedirs(rep_dir, exist_ok=True)

    date_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(rep_dir, f"day_report_{date_tag}.json")
    txt_path  = os.path.join(rep_dir, f"day_report_{date_tag}.txt")

    try:
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(summary, jf, ensure_ascii=False, indent=2)

        with open(txt_path, "w", encoding="utf-8") as tf:
            tf.write("=== DAYTRADE REPORT ===\n")
            tf.write(f"생성시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            for k, v in summary.items():
                tf.write(f"{k:25s}: {v}\n")

        # 콘솔에 간단 표시
        print(f"[OK] 리포트 저장 완료 → {json_path}")
    except Exception as e:
        print(f"[ERR] 리포트 저장 실패: {e}")
