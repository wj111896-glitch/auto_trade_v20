# -*- coding: utf-8 -*-
"""
run_daytrade.py — v2 final
허브(HubTrade) 연결 + 일자별 로그 + CLI 인자 처리 + Calibrator 옵션 + 세션 리포트 CSV(+수수료/세금/FIFO)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import signal
from datetime import datetime
from typing import List, Optional
import csv
from pathlib import Path

# === ① 경로 세팅 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# === ② 로거 ===
import logging

def _fallback_logger(name: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(sh)
    return logger

def get_project_logger(name: str, log_file: str) -> logging.Logger:
    try:
        from obs.log import get_logger as project_get_logger  # type: ignore
        logger = project_get_logger(name)
        # 파일핸들 없으면 추가
        for h in logger.handlers:
            if isinstance(h, logging.FileHandler):
                break
        else:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s - %(message)s'))
            logger.addHandler(fh)
        return logger
    except Exception:
        return _fallback_logger(name, log_file)

# === ③ 설정 로딩 ===
class RunnerConfig:
    def __init__(self):
        self.real_mode: bool = False
        self.budget: Optional[float] = None

def load_project_config(logger: logging.Logger) -> RunnerConfig:
    cfg = RunnerConfig()
    try:
        from common.config import DAYTRADE  # type: ignore
        # dict 또는 객체 모두 허용
        if isinstance(DAYTRADE, dict):
            cfg.budget = DAYTRADE.get("budget")
            cfg.real_mode = bool(DAYTRADE.get("REAL_MODE", False))
        else:
            cfg.budget = getattr(DAYTRADE, "BUDGET", None)
            cfg.real_mode = bool(getattr(DAYTRADE, "REAL_MODE", False))
        logger.info(f"Loaded common.config.DAYTRADE (budget={cfg.budget}, real_mode={cfg.real_mode})")
    except Exception:
        logger.warning("common.config.DAYTRADE 를 찾을 수 없어 기본값으로 진행합니다.")
    return cfg

# === 리포트 작성 유틸(전역) ===
def write_session_report(
    decisions: List[dict],
    logger: logging.Logger,
    fee_bps_buy: float = 0.0,
    fee_bps_sell: float = 0.0,
    tax_bps_sell: float = 0.0,
) -> str:
    """
    BUY/SELL를 FIFO로 매칭하여 실현손익을 계산하고 CSV로 저장.
    - bps 단위 수수료/세금 반영 (1 bps = 0.01%)
    - BUY 수수료는 원가에 포함, SELL 시 분배 차감
    - SELL 수수료/거래세는 체결가치 기준 차감
    """
    try:
        b2 = 1.0 / 10000.0  # bps → 비율
        date_str = datetime.now().strftime("%Y%m%d")
        out_dir = Path(BASE_DIR) / "logs" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"daytrade_{date_str}_report.csv"

        cols = ["time","symbol","action","qty","price","reason","pnl_gross","fee_value","tax_value","pnl_net"]
        now_ts = datetime.now().strftime("%H:%M:%S")

        # 심볼별 FIFO 재고: 각 lot = {"qty": int, "price": float, "buy_fee": float}
        inv: dict[str, list[dict]] = {}

        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()

            for d in decisions or []:
                act = str(d.get("action", "")).upper()
                if act not in ("BUY", "SELL"):
                    continue

                sym = str(d.get("symbol"))
                qty = int(d.get("qty") or 0)
                px  = float(d.get("price") or 0.0)
                reason = d.get("reason")

                if qty <= 0 or px <= 0:
                    wr.writerow({
                        "time": now_ts,"symbol": sym,"action": act,"qty": qty,"price": px,"reason": reason,
                        "pnl_gross": "", "fee_value": "", "tax_value": "", "pnl_net": ""
                    })
                    continue

                if act == "BUY":
                    # 매수 수수료(원가 포함)
                    buy_val = qty * px
                    buy_fee = buy_val * (fee_bps_buy * b2)
                    inv.setdefault(sym, []).append({"qty": qty, "price": px, "buy_fee": buy_fee})
                    wr.writerow({
                        "time": now_ts,"symbol": sym,"action": act,"qty": qty,"price": px,"reason": reason,
                        "pnl_gross": "", "fee_value": round(buy_fee,2), "tax_value": "", "pnl_net": ""
                    })
                    continue

                # SELL: FIFO 소진하며 실현손익
                sell_val = qty * px
                sell_fee = sell_val * (fee_bps_sell * b2)
                sell_tax = sell_val * (tax_bps_sell * b2)

                remain = qty
                pnl_gross = 0.0
                buy_fee_consumed = 0.0

                lots = inv.get(sym, [])
                while remain > 0 and lots:
                    lot = lots[0]
                    use = min(remain, lot["qty"])

                    # 수수료 비례 차감량(현재 lot 잔량 기준)
                    if lot["qty"] > 0:
                        proportion = use / lot["qty"]
                    else:
                        proportion = 0.0
                    fee_cons = float(lot.get("buy_fee", 0.0)) * proportion

                    # 손익 및 수수료 소비 누적
                    pnl_gross += (px - float(lot["price"])) * use
                    buy_fee_consumed += fee_cons

                    # lot 잔여 수수료/수량 업데이트 (← 핵심!)
                    lot["buy_fee"] = max(0.0, float(lot.get("buy_fee", 0.0)) - fee_cons)
                    lot["qty"] -= use
                    remain -= use

                    if lot["qty"] == 0:
                        lots.pop(0)

                # 남은 수량(음수 매도) 방어
                if remain > 0:

                    logger.warning(f"FIFO 부족: {sym} sell qty {qty} 중 {remain}는 미매칭 (재고 부족).")

                fee_value = sell_fee + buy_fee_consumed
                tax_value = sell_tax
                pnl_net = pnl_gross - fee_value - tax_value

                wr.writerow({
                    "time": now_ts,"symbol": sym,"action": act,"qty": qty,"price": px,"reason": reason,
                    "pnl_gross": round(pnl_gross,2),
                    "fee_value": round(fee_value,2),
                    "tax_value": round(tax_value,2),
                    "pnl_net": round(pnl_net,2),
                })

        logger.info(f"세션 리포트 저장: {out_path}")
        return str(out_path)
    except Exception as e:
        logger.warning(f"세션 리포트 작성 실패: {e}")
        return ""

# === ④ 허브 어댑터 ===
class HubAdapter:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        from hub.hub_trade import HubTrade  # type: ignore
        self.hub_cls = HubTrade
        self.hub = None

    def init(self, **kwargs):
        self.logger.info("HubTrade 초기화 중... kwargs=%s", kwargs)
        self.hub = self.hub_cls(**kwargs)
        return self

    def run(self, symbols: List[str], max_ticks: int) -> dict:
        if self.hub is None:
            raise RuntimeError("Hub not initialized")
        for meth in ("run_session", "start", "run"):
            if hasattr(self.hub, meth):
                fn = getattr(self.hub, meth)
                self.logger.info("허브 실행: %s(symbols=%s, max_ticks=%s)", meth, symbols, max_ticks)
                result = fn(symbols=symbols, max_ticks=max_ticks)  # type: ignore
                return result if isinstance(result, dict) else {"result": str(result)}
        raise AttributeError("HubTrade에 실행 메서드(run_session/start/run)가 없습니다.")

# === ⑤ CLI ===
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run daytrade hub runner")
    p.add_argument('--symbols', nargs='+', required=True, help='거래 심볼(코드) 리스트')
    p.add_argument('--max-ticks', type=int, default=2000, help='세션 최대 틱 수(기본 2000)')
    p.add_argument('--mode', choices=['dry','real'], default=None, help='실행 모드 강제 지정')
    p.add_argument('--budget', type=float, default=None, help='총 예산(옵션)')
    p.add_argument('--note', type=str, default='', help='세션 메모')
    # Calibrator
    p.add_argument('--use-calibrator', action='store_true', help='EMA 기반 온라인 보정 활성화')
    p.add_argument('--calib-lr', type=float, default=0.02)
    p.add_argument('--calib-hist', type=int, default=100)
    p.add_argument('--calib-clip', type=float, default=0.05)
    # Fees & Taxes (basis points: 1 bps = 0.01%)
    p.add_argument('--fee-bps-buy', type=float, default=0.0, help='매수 수수료(bps, 기본 0)')
    p.add_argument('--fee-bps-sell', type=float, default=0.0, help='매도 수수료(bps, 기본 0)')
    p.add_argument('--tax-bps-sell', type=float, default=0.0, help='매도 거래세(bps, 기본 0)')
    return p.parse_args()

# === ⑥ 실행 진입 ===
RUN_FLAG = {"alive": True}
def _install_signal_handlers(logger: logging.Logger):
    def _handler(signum, frame):
        logger.info(f"신호 수신: {signum} — 그레이스풀 셧다운 시도")
        RUN_FLAG["alive"] = False
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handler)
        except Exception:
            pass

def main():
    today = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(BASE_DIR, 'logs', f'daytrade_{today}.log')
    logger = get_project_logger('run_daytrade', log_file)
    _install_signal_handlers(logger)

    args = parse_args()
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

    # 설정 적용 (config -> CLI override)
    cfg = load_project_config(logger)
    if args.mode == 'dry':
        cfg.real_mode = False
    elif args.mode == 'real':
        cfg.real_mode = True
    if args.budget is not None:
        cfg.budget = args.budget

    logger.info("=== DAYTRADE RUN START ===")
    logger.info("symbols=%s, max_ticks=%s, real_mode=%s, budget=%s, note=%s",
                args.symbols, args.max_ticks, cfg.real_mode, cfg.budget, args.note)

    # 허브 초기화
    hub = HubAdapter(logger).init(
        real_mode=cfg.real_mode,
        budget=cfg.budget,
        calibrator_enabled=bool(args.use_calibrator),
        calib_lr=args.calib_lr,
        calib_hist=args.calib_hist,
        calib_clip=args.calib_clip,
        note=args.note,
    )

    # 실행
    session_result: dict = {}
    try:
        session_result = hub.run(symbols=args.symbols, max_ticks=args.max_ticks)
    except KeyboardInterrupt:
        logger.warning("사용자 중단(KeyboardInterrupt)")
    except Exception as e:
        logger.exception("허브 실행 중 예외: %s", e)

    # 요약 저장
    summary = {
        "date": today,
        "symbols": args.symbols,
        "max_ticks": args.max_ticks,
        "real_mode": cfg.real_mode,
        "budget": cfg.budget,
        "note": args.note,
        "calibrator": {
            "enabled": bool(args.use_calibrator),
            "lr": args.calib_lr,
            "hist": args.calib_hist,
            "clip": args.calib_clip,
        },
        "result": session_result,
        "ended_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    summary_path = os.path.join(BASE_DIR, 'logs', f'daytrade_{today}.summary.json')
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("세션 요약 저장: %s", summary_path)
    except Exception as e:
        logger.warning("세션 요약 저장 실패: %s", e)

    # CSV 리포트도 저장 (BUY/SELL만) — 수수료/거래세 반영
    try:
        decisions = session_result.get("decisions") or []
        if isinstance(decisions, list):
            _ = write_session_report(
                decisions, logger,
                fee_bps_buy=float(getattr(args, "fee_bps_buy", 0.0)),
                fee_bps_sell=float(getattr(args, "fee_bps_sell", 0.0)),
                tax_bps_sell=float(getattr(args, "tax_bps_sell", 0.0)),
            )
    except Exception as e:
        logger.warning(f"세션 리포트 저장 예외: {e}")

    logger.info("=== DAYTRADE RUN END ===")

if __name__ == '__main__':
    main()
