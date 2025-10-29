# -*- coding: utf-8 -*-
"""
run_daytrade.py — v2 final
허브(HubTrade) 연결 + 일자별 로그 + CLI 인자 처리 + Calibrator 옵션
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import signal
from datetime import datetime
from typing import List, Optional

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
        cfg.budget = getattr(DAYTRADE, 'BUDGET', None)
        cfg.real_mode = bool(getattr(DAYTRADE, 'REAL_MODE', False))
        logger.info(f"Loaded common.config.DAYTRADE (budget={cfg.budget}, real_mode={cfg.real_mode})")
    except Exception:
        logger.warning("common.config.DAYTRADE 를 찾을 수 없어 기본값으로 진행합니다.")
    return cfg

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

    logger.info("=== DAYTRADE RUN END ===")

if __name__ == '__main__':
    main()
