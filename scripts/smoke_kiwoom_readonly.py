# -*- coding: utf-8 -*-
"""
scripts/smoke_kiwoom_readonly.py
Kiwoom 실계좌 '조회만' 스모크 테스트 (주문 없음)
"""

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # ← 이 줄 추가!

from obs.log import get_logger
from order.router import OrderRouter
from common import config

def main():
    log = get_logger("smoke_readonly")
    log.info("BROKER=%s, DRY_RUN=%s, ACCOUNT_NO=%s",
             config.BROKER, config.DRY_RUN, config.ACCOUNT_NO)

    router = OrderRouter(get_logger("router"))

    # REAL 모드로 연결만 시도 (주문 호출 안 함)
    try:
        if hasattr(router, "set_mode"):
            router.set_mode("REAL", budget=None)
    except Exception as e:
        log.warning("set_mode 예외: %s", e)

    try:
        ok = router.connect()
        log.info("router.connect() -> %s", ok)
    except Exception as e:
        log.error("연결 예외: %s", e)
        return

    if not ok:
        log.error("연결 실패")
        return

    adapter = getattr(router, "adapter", None)

    # 계좌 조회
    try:
        accounts = adapter.get_accounts() if hasattr(adapter, "get_accounts") else None
        log.info("accounts: %s", accounts)
    except Exception as e:
        log.warning("get_accounts 예외: %s", e)

    # 예수금 조회
    try:
        cash = adapter.get_cash(config.ACCOUNT_NO) if hasattr(adapter, "get_cash") else None
        log.info("cash: %s", cash)
    except Exception as e:
        log.warning("get_cash 예외: %s", e)

    # 보유 종목 조회
    try:
        positions = adapter.get_positions(config.ACCOUNT_NO) if hasattr(adapter, "get_positions") else None
        log.info("positions: %s", positions)
    except Exception as e:
        log.warning("get_positions 예외: %s", e)

    log.info("✅ READONLY SMOKE DONE — 주문 없음, 조회만 수행 완료.")

if __name__ == "__main__":
    main()
