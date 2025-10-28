# C:\Users\kimta\auto_trade_v20\order\router.py
from __future__ import annotations
import threading
from typing import Optional
from common import config

if config.BROKER.upper() == "KIWOOM":
    from order.adapters.kiwoom import KiwoomAdapter as Adapter
    _adapter_kwargs = {
        "account_no": config.ACCOUNT_NO,
        "dry_run": config.DRY_RUN,
        "rate_limit_ms": getattr(config, "ORDER_RATE_LIMIT_MS", 120),
    }
else:
    from order.adapters.mock import MockAdapter as Adapter
    _adapter_kwargs = {}

class OrderRouter:
    def __init__(self, logger=None):
        self.logger = logger
        self._lock = threading.RLock()
        self._adapter = Adapter(logger=logger, **_adapter_kwargs)

    def connect(self) -> bool:
        with self._lock:
            ok = self._adapter.connect()
            if ok and self.logger:
                self.logger.info(f"[OrderRouter] connected -> {config.BROKER} (dry_run={getattr(self._adapter,'dry_run',None)})")
            return ok

    def close(self):
        with self._lock:
            self._adapter.close()

    def get_cash(self) -> int:
        with self._lock:
            return self._adapter.get_cash()

    def get_positions(self):
        with self._lock:
            return self._adapter.get_positions()

    def buy(self, symbol: str, qty: int, price: Optional[float]=None, order_type: str="MKT", user_tag: Optional[str]=None):
        with self._lock:
            return self._adapter.place_order(symbol, "BUY", qty, price=price, order_type=order_type, user_tag=user_tag)

    def sell(self, symbol: str, qty: int, price: Optional[float]=None, order_type: str="MKT", user_tag: Optional[str]=None):
        with self._lock:
            return self._adapter.place_order(symbol, "SELL", qty, price=price, order_type=order_type, user_tag=user_tag)

    def cancel(self, order_id: str):
        with self._lock:
            return self._adapter.cancel_order(order_id)

    def route(self, decision: dict):
        action = (decision.get("action") or "HOLD").upper()
        symbol = decision.get("symbol")
        qty    = int(decision.get("qty", 0) or 0)
        order_type = decision.get("order_type", "MKT")
        price  = decision.get("price")
        tag    = decision.get("tag")
        if action == "HOLD" or qty <= 0:
            if self.logger: self.logger.info("[OrderRouter] HOLD %s", decision)
            return None
        if action == "BUY":
            return self.buy(symbol, qty, price=price, order_type=order_type, user_tag=tag)
        if action == "SELL":
            return self.sell(symbol, qty, price=price, order_type=order_type, user_tag=tag)
        if self.logger: self.logger.warning("[OrderRouter] unknown action: %s", action)
        return None

