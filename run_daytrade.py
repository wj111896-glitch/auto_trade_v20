# -*- coding: utf-8 -*-
"""
run_daytrade.py - 단타 전략 메인 러너 (경로 자동 세팅 + 일자별 로그 + 세션 요약/CSV)
사용 예:
    python run_daytrade.py --symbols 005930 000660 035420 --max-ticks 2000
"""
import os
import sys
import time
import argparse
from datetime import datetime

# ==== ① 경로 자동 세팅 ====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ==== ② 모듈 임포트 ====
from common.config import DAYTRADE
from obs.log import get_logger
from market.price import PriceFeedMock
from scoring.core import ScoreEngine
from scoring.weights import Weights
from scoring.rules.take_profit import TakeProfit
from scoring.rules.stop_loss import StopLoss
from scoring.rules.trailing import TrailingStop
from risk.core import RiskGate
from order.router import OrderRouter

# ==== ③ 로거 생성 (일자별 파일 자동 저장) ====
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, f"daytrade_{datetime.now():%Y-%m-%d}.log")
log = get_logger("daytrade", logfile=log_path)

# ==== ④ 컴포넌트 ====
def build_components(cfg: dict):
    weights = Weights(cfg["weights"])
    engine  = ScoreEngine(weights)
    risk    = RiskGate(cfg["risk"])
    router  = OrderRouter(adapter="mock")  # adapter 인자는 무시되도록 router.py 수정됨
    tp      = TakeProfit(cfg["exits"]["tp_pct"])
    sl      = StopLoss(cfg["exits"]["sl_pct"])
    tr      = TrailingStop(cfg["exits"]["trailing_pct"])
    return engine, risk, router, tp, sl, tr

def can_enter_now(pos, now_ts, cooldown_sec):
    if not pos or pos.get("qty", 0) == 0:
        return True
    last = pos.get("last_fill_ts", 0)
    return (now_ts - last) >= cooldown_sec

def on_fill_buy(portfolio, sym, qty, px, now_ts):
    pos = portfolio.get(sym, {"qty": 0, "avg_px": 0.0, "peak_px": 0.0, "last_fill_ts": 0.0})
    total_cost = pos["avg_px"] * pos["qty"] + px * qty
    new_qty    = pos["qty"] + qty
    pos["qty"] = new_qty
    pos["avg_px"] = total_cost / new_qty if new_qty else 0.0
    pos["peak_px"] = max(pos.get("peak_px", 0.0), px)
    pos["last_fill_ts"] = now_ts
    portfolio[sym] = pos

def on_fill_sell(portfolio, sym, qty, px, now_ts):
    pos = portfolio.get(sym)
    if not pos:
        return
    new_qty = max(0, pos["qty"] - qty)
    pos["qty"] = new_qty
    if new_qty == 0:
        pos["avg_px"] = 0.0
        pos["peak_px"] = 0.0
    pos["last_fill_ts"] = now_ts
    portfolio[sym] = pos

# ==== ⑤ 메인 루프 ====
def main():
    parser = argparse.ArgumentParser(description="Daytrade strategy runner")
    parser.add_argument("--symbols", nargs="+", default=["005930","000660","035420"], help="심볼 목록")
    parser.add_argument("--max-ticks", type=int, default=3000, help="최대 처리 틱 수")
    parser.add_argument("--sleep-ms", type=int, default=5, help="틱 간 슬립(ms)")
    args = parser.parse_args()

    cfg = DAYTRADE
    engine, risk, router, tp, sl, tr = build_components(cfg)
    feed = PriceFeedMock(symbols=args.symbols)

    portfolio: dict[str, dict] = {}

    # === 세션 통계/기록 ===
    trade_buy_cnt = 0
    trade_sell_cnt = 0
    realized_pnl_sum_pct = 0.0
    trades = []  # CSV로 남길 체결 기록

    buy_th, sell_th = cfg["thresholds"]["buy"], cfg["thresholds"]["sell"]
    cooldown = cfg["ops"]["cooldown_sec_after_fill"]
    ticks = 0
    start_ts = datetime.now()

    for tick in feed.stream():
        sym, px = tick.symbol, tick.price
        ts = getattr(tick, "ts", time.time())
        ticks += 1

        # 리스크 킬스위치
        if not risk.heartbeat_ok():
            log.warning("RISK_KILL_SWITCH", extra={"ticks": ticks})
            break

        # 점수 계산
        score = engine.score(tick)
        pos = portfolio.get(sym)

        # ============== 진입 ==============
        if score >= buy_th and can_enter_now(pos, ts, cooldown):
            if risk.allow_entry(sym, portfolio, px):
                qty = risk.size_for(sym, px)
                if qty > 0:
                    router.buy(sym, qty, px)
                    on_fill_buy(portfolio, sym, qty, px, ts)

                    trade_buy_cnt += 1
                    trades.append({
                        "ts": datetime.now().strftime("%H:%M:%S"),
                        "side": "BUY", "sym": sym, "qty": qty, "px": round(px,2),
                        "score": round(score,4), "reason": "score>=buy_th"
                    })
                    log.info(
                        "BUY",
                        extra={
                            "sym": sym, "px": round(px,2), "qty": qty,
                            "score": round(score,4),
                            "exposure": round(getattr(risk, "exposure_now", 0.0), 3)
                        }
                    )

        # ============== 청산 ==============
        pos = portfolio.get(sym)
        if pos and pos.get("qty", 0) > 0:
            # 트레일링 고점 갱신
            pos["peak_px"] = max(pos.get("peak_px", 0.0), px)

            exit_hit = False
            reason = None

            # 우선순위: SL > TP > TRAIL
            if sl.check(sym, pos, px):
                exit_hit, reason = True, "SL"
            elif tp.check(sym, pos, px):
                exit_hit, reason = True, "TP"
            elif tr.check(sym, pos, px):
                exit_hit, reason = True, "TRAIL"
            elif score <= sell_th:
                exit_hit, reason = True, "SELL_TH"

            if exit_hit:
                qty = pos["qty"]
                avg_px = pos.get("avg_px") or 0.0
                pnl_pct = (px / avg_px - 1.0) * 100.0 if avg_px > 0 else 0.0

                router.sell(sym, qty, px)
                on_fill_sell(portfolio, sym, qty, px, ts)

                realized_pnl_sum_pct += pnl_pct
                trade_sell_cnt += 1
                trades.append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "side": "SELL", "sym": sym, "qty": qty, "px": round(px,2),
                    "pnl_pct": round(pnl_pct,3), "reason": reason
                })
                log.info(
                    "SELL",
                    extra={
                        "sym": sym, "px": round(px,2), "qty": qty,
                        "pnl_pct": round(pnl_pct, 3),
                        "reason": reason,
                        "score": round(score,4)
                    }
                )

        # 종료 조건(모의)
        if ticks >= args.max_ticks:
            log.info("MAX_TICKS_REACHED", extra={"ticks": ticks})
            break

        # 틱 슬립
        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000.0)

    dur = (datetime.now() - start_ts).total_seconds()
    log.info("SESSION_END", extra={"ticks": ticks, "seconds": round(dur,2)})

    # === 세션 요약 ===
    avg_pnl = (realized_pnl_sum_pct / trade_sell_cnt) if trade_sell_cnt > 0 else 0.0
    log.info(
        "SESSION_SUMMARY",
        extra={
            "buys": trade_buy_cnt,
            "sells": trade_sell_cnt,
            "realized_pnl_sum_pct": round(realized_pnl_sum_pct, 3),
            "avg_pnl_pct_per_trade": round(avg_pnl, 3),
            "logfile": log_path
        }
    )

    # === CSV 저장 ===
    try:
        csv_path = os.path.join(LOG_DIR, f"trades_{datetime.now():%Y-%m-%d_%H%M%S}.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("ts,side,sym,qty,px,score,pnl_pct,reason\n")
            for t in trades:
                f.write("{ts},{side},{sym},{qty},{px},{score},{pnl},{reason}\n".format(
                    ts=t.get("ts",""),
                    side=t.get("side",""),
                    sym=t.get("sym",""),
                    qty=t.get("qty",""),
                    px=t.get("px",""),
                    score=t.get("score",""),
                    pnl=t.get("pnl_pct",""),
                    reason=t.get("reason",""),
                ))
        log.info("TRADES_SAVED", extra={"csv": csv_path})
    except Exception as e:
        log.info("TRADES_SAVE_FAILED", extra={"err": str(e)})

if __name__ == "__main__":
    main()
