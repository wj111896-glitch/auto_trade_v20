# -*- coding: utf-8 -*-
# obs/compare_reports.py
"""
사용 예)
  python -m obs.compare_reports                 # 최근 2개 리포트 자동 비교
  python -m obs.compare_reports --count 3       # 최근 3개 추세 요약
  python -m obs.compare_reports --files path1 path2  # 두 파일 직접 지정
"""
import os, sys, json, glob
from datetime import datetime
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")

def _load_json(p: str) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _find_latest_reports(count: int = 2) -> List[str]:
    pats = sorted(glob.glob(os.path.join(REPORT_DIR, "day_report_*.json")))
    return pats[-count:] if len(pats) >= count else pats

def _safe_get(d: Dict[str, Any], k: str, default=0.0):
    return d.get(k, default)

def _fmt_pct(x: float) -> str:
    try:
        return f"{float(x):.3f}"
    except Exception:
        return str(x)

def compare_two(a_path: str, b_path: str) -> Dict[str, Any]:
    a = _load_json(a_path)
    b = _load_json(b_path)
    keys = [
        "realized_pnl_sum_pct",
        "avg_pnl_pct_per_trade",
        "buys", "sells",
        "news_bias_hits",
        "news_bias_avg_applied",
        "news_bias_max_applied",
        "news_bias_min_applied",
    ]
    diffs = {k: _safe_get(b, k, 0) - _safe_get(a, k, 0) for k in keys}

    # 심볼별 뉴스 바이어스 평균 차이
    a_sym = a.get("news_bias_symbols", {}) or {}
    b_sym = b.get("news_bias_symbols", {}) or {}
    all_syms = sorted(set(a_sym) | set(b_sym))
    sym_diffs = {s: round(float(b_sym.get(s, 0)) - float(a_sym.get(s, 0)), 4) for s in all_syms}

    return {
        "base": os.path.basename(a_path),
        "target": os.path.basename(b_path),
        "a": a, "b": b,
        "diffs": diffs,
        "sym_diffs": sym_diffs,
    }

def trend_latest(paths: List[str]) -> Dict[str, Any]:
    """최근 N개 경로에 대해 간단 추세(평균/증감 방향)"""
    series = [_load_json(p) for p in paths]
    def avg(key: str):
        vals = [float(_safe_get(s, key, 0)) for s in series]
        return sum(vals) / len(vals) if vals else 0.0
    return {
        "files": [os.path.basename(p) for p in paths],
        "avg_realized_pnl_sum_pct": avg("realized_pnl_sum_pct"),
        "avg_avg_pnl_pct_per_trade": avg("avg_pnl_pct_per_trade"),
        "avg_news_bias_avg_applied": avg("news_bias_avg_applied"),
    }

def _save_result(data: Dict[str, Any]) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jpath = os.path.join(REPORT_DIR, f"compare_{tag}.json")
    tpath = os.path.join(REPORT_DIR, f"compare_{tag}.txt")
    with open(jpath, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    lines = []
    if "comparison" in data:
        c = data["comparison"]
        lines.append(f"=== DAILY REPORT COMPARE ===")
        lines.append(f"A(이전): {c['base']}")
        lines.append(f"B(오늘): {c['target']}\n")
        for k, v in c["diffs"].items():
            lines.append(f"{k:25s}: {_fmt_pct(v)}  (B - A)")
        if c.get("sym_diffs"):
            lines.append("\n-- Symbol news bias delta (B - A) --")
            for s, dv in c["sym_diffs"].items():
                lines.append(f"{s:>6s}: {dv:+.4f}")
    if "trend" in data:
        t = data["trend"]
        lines.append("\n=== LATEST TREND ===")
        lines.append("files: " + ", ".join(t["files"]))
        lines.append(f"avg_realized_pnl_sum_pct   : {_fmt_pct(t['avg_realized_pnl_sum_pct'])}")
        lines.append(f"avg_avg_pnl_pct_per_trade  : {_fmt_pct(t['avg_avg_pnl_pct_per_trade'])}")
        lines.append(f"avg_news_bias_avg_applied  : {_fmt_pct(t['avg_news_bias_avg_applied'])}")
    with open(tpath, "w", encoding="utf-8") as tf:
        tf.write("\n".join(lines))
    print(f"[OK] 비교 리포트 저장 → {tpath}")
    return tpath

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Compare day_report JSONs")
    ap.add_argument("--files", nargs="*", help="비교할 JSON 리포트 2개 경로")
    ap.add_argument("--count", type=int, default=2, help="최근 N개 리포트로 비교/추세 (기본 2)")
    args = ap.parse_args(argv)

    result: Dict[str, Any] = {}

    if args.files and len(args.files) == 2:
        a, b = args.files
        result["comparison"] = compare_two(a, b)
    else:
        paths = _find_latest_reports(args.count)
        if len(paths) >= 2:
            result["comparison"] = compare_two(paths[-2], paths[-1])
        if len(paths) >= 1:
            result["trend"] = trend_latest(paths)

    if not result:
        print("[WARN] 비교할 리포트를 찾지 못했습니다. reports/day_report_*.json 을 확인하세요.")
        return 1

    _save_result(result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
