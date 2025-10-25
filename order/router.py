# -*- coding: utf-8 -*-
"""
Mock 주문 라우터 — 단타 러너(run_daytrade.py) 호환용
BUY/SELL 명령을 흉내 내며 콘솔/로그로 출력만 수행합니다.
"""

import time
from types import SimpleNamespace
from obs.log import get_logger

log = get_logger("order.router")

class OrderRouter:
    def __init__(self, adapter: str | None = None, **kwargs):
        # adapter 인자는 무시하고 mock로 동작 (호환용)
        self.adapter = adapter or "mock"
        self._orders = []  # 단순 기록용

    def buy(self, sym: str, qty: float, price: float):
        """
        모의 매수 주문 실행 (즉시 체결 가정)
        """
        order = SimpleNamespace(
            side="BUY",
            symbol=sym,
            qty=qty,
            price=price,
            ts=time.time()
        )
        self._orders.append(order)
        # log.info(f"BUY  {sym} qty={qty} px={price:.2f}")
        return order

    def sell(self, sym: str, qty: float, price: float):
        """
        모의 매도 주문 실행 (즉시 체결 가정)
        """
        order = SimpleNamespace(
            side="SELL",
            symbol=sym,
            qty=qty,
            price=price,
            ts=time.time()
        )
        self._orders.append(order)
        # log.info(f"SELL {sym} qty={qty} px={price:.2f}")
        return order

    def cancel(self, sym: str):
        """
        모의 주문 취소 (단순 로그용)
        """
        log.info(f"CANCEL {sym}")
        return True

    def orders(self):
        """기록된 주문 리스트 반환"""
        return list(self._orders)
