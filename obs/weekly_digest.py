# -*- coding: utf-8 -*-
# obs/weekly_digest.py
"""
사용 예)
  python -m obs.weekly_digest                  # 기본 7일
  python -m obs.weekly_digest --days 5         # 최근 5일
  python -m obs.weekly_digest --glob "day_report_2025-10-*.json"  # 특정 기간만
"""
import os, sys, json, glob
from datetime import datetime
from typing import List, Dict, Any

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
TEMPLATE  = os.path.join(BASE_DIR, "obs", "templates", "weekly_digest.md.tmpl")

def _load_json(p: str) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _render_template(text: str, data: dict) -> str:
    out = text
    for k, v in data.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out

def _collect(paths: List[str]) -> Dict[str, Any]:
    days = []
    total_pnl = 0.0
    total_avg_pnl = 0.0
    total_bias_avg = 0.0
    sym_acc: Dict[str, Dict[str, float]] = {}  # sym -> {sum, hits}

    for p in paths:
        d = _load_json(p)
        days.append({
            "file": os.path.basename(p),
            "buys": d.get("buys", 0),
            "sells": d.get("sells", 0),
            "realized_pnl_sum_pct": float(d.get("realized_pnl_sum_pct", 0.0)),
            "avg_pnl_pct_per_trade": float(d.get("avg_pnl_pct_per_trade", 0.0)),
            "news_bias_avg_applied": float(d.get("news_bias_avg_applied", 0.0)),
        })
        total_pnl += float(d.get("realized_pnl_sum_pct", 0.0))
        total_avg_pnl += float(d.get("avg_pnl_pct_per_trade", 0.0))
        total_bias_avg += float(d.get("news_bias_avg_applied", 0.0))

        # 심볼별 평균(일평균의 평균) 집계
        sym_map = d.get("news_bias_symbols", {}) or {}
        for sym, v in sym_map.items():
            acc = sym_acc.setdefault(sym, {"sum": 0.0, "hits": 0})
            acc["sum"]  += float(v)
            acc["hits"] += 1

    n = len(days) if days else 1
    sym_avg = {s: round(v["sum"] / v["hits"], 4) for s, v in sym_acc.items() if v["hits"] > 0}

    # Top/Bottom 3 by news bias (주간 평균)
    top_syms = sorted(sym_avg.items(), key=lambda x: x[1], reverse=True)[:3]
    bot_syms = sorted(sym_avg.items(), key=lambda x: x[1])[:3]

    return {
        "sessions": len(days),
        "files": [d["file"] for d in days],
        "total_realized_pnl_pct": round(total_pnl, 3),
        "avg_daily_pnl_pct": round(total_pnl / n, 3),
        "avg_daily_trade_pnl_pct": round(total_avg_pnl / n, 3),
        "avg_daily_news_bias": round(total_bias_avg / n, 4),
        "symbol_bias_weekly_avg": sym_avg,         # {'005930': 0.028, ...}
        "symbol_bias_top3": top_syms,              # [('005930', 0.04), ...]
        "symbol_bias_bottom3": bot_syms,
        "days_detail": days,                        # 일자별 요약 행
    }

def _save(data: Dict[str, Any]) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jpath = os.path.join(REPORT_DIR, f"weekly_{tag}.json")
    with open(jpath, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    # 템플릿이 있으면 txt를 예쁘게 렌더
    tpath = os.path.join(REPORT_DIR, f"weekly_{tag}.txt")
    if os.path.exists(TEMPLATE):
        with open(TEMPLATE, "r", encoding="utf-8") as tf:
            tmpl = tf.read()
        # 템플릿용 핵심 키만 전달
        render_ctx = {
            "week_range": ", ".join(data["files"][:1] + ["..."] + data["files"][-1:]) if data["files"] else "",
            "sessions": data["sessions"],
            "total_pnl": data["total_realized_pnl_pct"],
            "avg_daily_pnl": data["avg_daily_pnl_pct"],
            "avg_trade_pnl": data["avg_daily_trade_pnl_pct"],
            "avg_news_bias": data["avg_daily_news_bias"],
            "top_syms": ", ".join([f"{s}:{v:+.4f}" for s, v in data["symbol_bias_top3"]]),
            "bot_syms": ", ".join([f"{s}:{v:+.4f}" for s, v in data["symbol_bias_bottom3"]]),
        }
        body = _render_template(tmpl, render_ctx)
    else:
        lines = [
            "=== WEEKLY DIGEST ===",
            f"sessions: {data['sessions']}",
            "files: " + ", ".join(data["files"]),
            f"total_realized_pnl_pct : {data['total_realized_pnl_pct']}",
            f"avg_daily_pnl_pct     : {data['avg_daily_pnl_pct']}",
            f"avg_trade_pnl_pct     : {data['avg_daily_trade_pnl_pct']}",
            f"avg_daily_news_bias   : {data['avg_daily_news_bias']}",
            "",
            "-- top syms by news bias --",
        ]
        lines += [f"{s}:{v:+.4f}" for s, v in data["symbol_bias_top3"]]
        lines += ["", "-- bottom syms by news bias --"]
        lines += [f"{s}:{v:+.4f}" for s, v in data["symbol_bias_bottom3"]]
        body = "\n".join(lines)
    with open(tpath, "w", encoding="utf-8") as tf:
        tf.write(body)

    # latest 파일도 갱신
    with open(os.path.join(REPORT_DIR, "weekly_latest.json"), "w", encoding="utf-8") as lf:
        json.dump(data, lf, ensure_ascii=False, indent=2)
    with open(os.path.join(REPORT_DIR, "weekly_latest.txt"), "w", encoding="utf-8") as lf:
        lf.write(body)

    print(f"[OK] 주간 다이제스트 저장 → {tpath}")
    return tpath

def _find_report_paths(glob_pat: str, days: int) -> List[str]:
    paths = sorted(glob.glob(os.path.join(REPORT_DIR, glob_pat)))
    return paths[-days:] if days and len(paths) > days else paths

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Weekly digest from day_report JSONs")
    ap.add_argument("--days", type=int, default=7, help="최근 N개 일일 리포트 사용(기본 7)")
    ap.add_argument("--glob", default="day_report_*.json", help="대상 파일 glob 패턴")
    args = ap.parse_args(argv)

    paths = _find_report_paths(args.glob, args.days)
    if not paths:
        print("[WARN] 주간 요약에 사용할 day_report JSON이 없습니다.")
        return 1

    data = _collect(paths)
    _save(data)
    return 0

if __name__ == "__main__":
    sys.exit(main())
