@echo off
setlocal enabledelayedexpansion

REM 1) 리포 루트 기준 확인
cd /d "%~dp0"

REM 2) 폴더 준비
if not exist "common" mkdir "common"
if not exist "logs" mkdir "logs"

REM 3) preset 파일 생성 (common/config_daytrade_preset.py)
(
echo # -*- coding: utf-8 -*-
echo # 단타 프리셋 (기존 common/config.py 를 수정하지 않기 위해 분리)
echo DAYTRADE = {
echo ^"weights^": {
echo     ^"volume^":   0.45,
echo     ^"tickflow^": 0.35,
echo     ^"ta^":       0.20,
echo },
echo ^"thresholds^": {
echo     ^"buy^":   0.45,
echo     ^"sell^": -0.45,
echo },
echo ^"exits^": {
echo     ^"tp_pct^":        0.012,
echo     ^"sl_pct^":       -0.008,
echo     ^"trailing_pct^":  0.010,
echo },
echo ^"risk^": {
echo     ^"budget^":                 100000000,
echo     ^"intraday_exposure_max^":  0.60,
echo     ^"per_symbol_cap_min^":     0.10,
echo     ^"per_symbol_cap_max^":     0.15,
echo     ^"day_dd_kill^":            0.03,
echo },
echo ^"ops^": {
echo     ^"cooldown_sec_after_fill^": 20,
echo     ^"session_only^": True,
echo }
echo }
) > "common\config_daytrade_preset.py"

REM 4) run_daytrade.py 생성 (리포 루트)
(
echo # -*- coding: utf-8 -*-
echo """
echo run_daytrade.py - 단타 전략 메인 러너 (안전 버전: 경로 자동세팅 + 분리 프리셋)
echo 사용: python run_daytrade.py --symbols 005930 000660 035420 --max-ticks 2000
echo """
echo
echo import os, sys, time, argparse
echo from datetime import datetime
echo
echo # === 경로 자동 세팅 ===
echo BASE_DIR = os.path.dirname(os.path.abspath(__file__))
echo if BASE_DIR not in sys.path:
echo ^    sys.path.insert(0, BASE_DIR)
echo os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
echo
echo # === 모듈 임포트 (프리셋은 분리 파일에서 불러옴) ===
echo from common.config_daytrade_preset import DAYTRADE
echo from obs.log import get_logger
echo from market.price import PriceFeedMock
echo from scoring.core import ScoreEngine
echo from scoring.weights import Weights
echo from scoring.rules.take_profit import TakeProfit
echo from scoring.rules.stop_loss import StopLoss
echo from scoring.rules.trailing import TrailingStop
echo from risk.core import RiskGate
echo from order.router import OrderRouter
echo
echo log = get_logger("daytrade")
echo
echo def build_components(cfg: dict):
echo ^    weights = Weights(cfg["weights"])
echo ^    engine  = ScoreEngine(weights)
echo ^    risk    = RiskGate(cfg["risk"])
echo ^    router  = OrderRouter(adapter="mock")
echo ^    tp      = TakeProfit(cfg["exits"]["tp_pct"])
echo ^    sl      = StopLoss(cfg["exits"]["sl_pct"])
echo ^    tr      = TrailingStop(cfg["exits"]["trailing_pct"])
echo ^    return engine, risk, router, tp, sl, tr
echo
echo def can_enter_now(pos, now_ts, cooldown_sec):
echo ^    if not pos or pos.get("qty", 0) == 0:
echo ^        return True
echo ^    last = pos.get("last_fill_ts", 0)
echo ^    return (now_ts - last) >= cooldown_sec
echo
echo def on_fill_buy(portfolio, sym, qty, px, now_ts):
echo ^    pos = portfolio.get(sym, {"qty": 0, "avg_px": 0.0, "peak_px": 0.0, "last_fill_ts": 0.0})
echo ^    total_cost = pos["avg_px"] * pos["qty"] + px * qty
echo ^    new_qty    = pos["qty"] + qty
echo ^    pos["qty"] = new_qty
echo ^    pos["avg_px"] = total_cost / new_qty if new_qty else 0.0
echo ^    pos["peak_px"] = max(pos.get("peak_px", 0.0), px)
echo ^    pos["last_fill_ts"] = now_ts
echo ^    portfolio[sym] = pos
echo
echo def on_fill_sell(portfolio, sym, qty, px, now_ts):
echo ^    pos = portfolio.get(sym)
echo ^    if not pos: return
echo ^    new_qty = max(0, pos["qty"] - qty)
echo ^    pos["qty"] = new_qty
echo ^    if new_qty == 0:
echo ^        pos["avg_px"] = 0.0
echo ^        pos["peak_px"] = 0.0
echo ^    pos["last_fill_ts"] = now_ts
echo ^    portfolio[sym] = pos
echo
echo def main():
echo ^    parser = argparse.ArgumentParser(description="Daytrade runner")
echo ^    parser.add_argument("--symbols", nargs="+", default=["005930","000660","035420"])
echo ^    parser.add_argument("--max-ticks", type=int, default=3000)
echo ^    parser.add_argument("--sleep-ms", type=int, default=5)
echo ^    args = parser.parse_args()
echo
echo ^    cfg = DAYTRADE
echo ^    engine, risk, router, tp, sl, tr = build_components(cfg)
echo ^    feed = PriceFeedMock(symbols=args.symbols)
echo ^    portfolio = {}
echo
echo ^    buy_th, sell_th = cfg["thresholds"]["buy"], cfg["thresholds"]["sell"]
echo ^    cooldown = cfg["ops"]["cooldown_sec_after_fill"]
echo ^    ticks = 0
echo ^    start_ts = datetime.now()
echo
echo ^    for tick in feed.stream():
echo ^        sym, px = tick.symbol, tick.price
echo ^        ts = getattr(tick, "ts", time.time())
echo ^        ticks += 1
echo
echo ^        if not risk.heartbeat_ok():
echo ^            log.warning("RISK_KILL_SWITCH", extra={"ticks": ticks})
echo ^            break
echo
echo ^        score = engine.score(tick)
echo ^        pos = portfolio.get(sym)
echo
echo ^        if score >= buy_th and can_enter_now(pos, ts, cooldown):
echo ^            if risk.allow_entry(sym, portfolio, px):
echo ^                qty = risk.size_for(sym, px)
echo ^                router.buy(sym, qty, px)
echo ^                on_fill_buy(portfolio, sym, qty, px, ts)
echo ^                log.info("BUY", extra={"sym": sym, "px": px, "qty": qty, "score": round(score,4)})
echo
echo ^        pos = portfolio.get(sym)
echo ^        if pos and pos.get("qty", 0) > 0:
echo ^            pos["peak_px"] = max(pos.get("peak_px", 0.0), px)
echo ^            exit_hit = False
echo ^            reason = None
echo
echo ^            if sl.check(sym, pos, px):
echo ^                exit_hit, reason = True, "SL"
echo ^            elif tp.check(sym, pos, px):
echo ^                exit_hit, reason = True, "TP"
echo ^            elif tr.check(sym, pos, px):
echo ^                exit_hit, reason = True, "TRAIL"
echo ^            elif score <= sell_th:
echo ^                exit_hit, reason = True, "SELL_TH"
echo
echo ^            if exit_hit:
echo ^                qty = pos["qty"]
echo ^                router.sell(sym, qty, px)
echo ^                pnl_pct = (px / pos["avg_px"] - 1.0) * 100 if pos.get("avg_px") else 0.0
echo ^                on_fill_sell(portfolio, sym, qty, px, ts)
echo ^                log.info("SELL", extra={"sym": sym, "px": px, "qty": qty, "pnl_pct": round(pnl_pct,3), "reason": reason})
echo
echo ^        if ticks >= args.max_ticks:
echo ^            log.info("MAX_TICKS_REACHED", extra={"ticks": ticks})
echo ^            break
echo
echo ^        time.sleep(args.sleep_ms / 1000.0)
echo
echo ^    dur = (datetime.now() - start_ts).total_seconds()
echo ^    log.info("SESSION_END", extra={"ticks": ticks, "seconds": round(dur,2)})
echo
echo if __name__ == "__main__":
echo ^    main()
) > "run_daytrade.py"

echo.
echo [OK] 설치 완료: run_daytrade.py, common\config_daytrade_preset.py
echo 사용법: python run_daytrade.py --symbols 005930 000660 035420 --max-ticks 2000
pause
