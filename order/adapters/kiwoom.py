# -*- coding: utf-8 -*-
"""
KiwoomAdapter v1 (order/adapters/kiwoom.py)

목표:
- 실제 주문 연동을 위한 어댑터 스켈레톤 (DRY_RUN 우선 정상 동작)
- router.py에서 동일 인터페이스로 호출 가능하도록 설계
- Kiwoom OpenAPI+ 환경(ActiveX/QAxWidget) 의존부는 안전하게 분리

사용 예 (router에서):
    from order.adapters.kiwoom import KiwoomAdapter
    adapter = KiwoomAdapter(account_no="12345678", dry_run=True)
    adapter.connect()
    oid = adapter.place_order(symbol="005930", side="BUY", qty=10, order_type="MKT")
    adapter.cancel_order(oid)

주의:
- 실제 Kiwoom 연동은 Windows 32-bit Python + PyQt5 QAxWidget 이벤트 루프가 필요합니다.
- 본 파일은 이벤트 핸들러/요청 포맷을 정의하고, DRY_RUN 로직은 즉시 사용 가능하도록 구현합니다.
- 실제 연동 부분(TODO) 표기: 향후 hub_live에서 Qt 이벤트 루프와 함께 구동.
"""
from __future__ import annotations
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

# ===== 공통 타입 =====
@dataclass
class OrderResult:
    ok: bool
    order_id: Optional[str]
    message: str
    raw: Optional[Dict[str, Any]] = None

@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float

# ===== 어댑터 본체 =====
class KiwoomAdapter:
    """Kiwoom 주문 어댑터 (v1)

    - dry_run=True: 체결 시뮬레이션 (메모리 내 체결/포지션 관리)
    - dry_run=False: Kiwoom OpenAPI+ 연동 (TODO: QAxWidget 이벤트/조회/주문)
    """

    def __init__(self, account_no: str, dry_run: bool = True, logger=None, rate_limit_ms: int = 120):
        self.account_no = account_no
        self.dry_run = dry_run
        self.logger = logger or self._get_default_logger()
        self.rate_limit_ms = rate_limit_ms
        self._rl_lock = threading.Lock()

        # 내부 상태 (DRY_RUN용)
        self._connected = False
        self._cash = 100_000_000  # 1억원 가정 (DRY_RUN)
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Dict[str, Any]] = {}

        # 실계좌 모드용 핸들 (TODO)
        self._ax = None  # QAxWidget 인스턴스 등

    # ----- 공용 유틸 -----
    def _get_default_logger(self):
        class _L:
            def info(self, *a, **k): print("[INFO]", *a)
            def warn(self, *a, **k): print("[WARN]", *a)
            def warning(self, *a, **k): print("[WARN]", *a)
            def error(self, *a, **k): print("[ERROR]", *a)
            def debug(self, *a, **k): print("[DEBUG]", *a)
        return _L()

    def _rate_limit(self):
        """간단한 주문/조회 레이트리미트 (쓰로틀링)."""
        with self._rl_lock:
            time.sleep(self.rate_limit_ms / 1000.0)

    # ===== 라이프사이클 =====
    def connect(self) -> bool:
        """브로커 연결.
        - DRY_RUN: 즉시 연결 True
        - REAL: QAxWidget 로그인 시도 (TODO)
        """
        if self.dry_run:
            self._connected = True
            self.logger.info("[KiwoomAdapter] DRY_RUN 연결 완료")
            return True
        else:
            # TODO: QAxWidget 초기화 + CommConnect() 비동기 로그인
            # 로그인 완료 이벤트 수신 후 self._connected = True
            self.logger.info("[KiwoomAdapter] REAL 모드 로그인 시도 (TODO)")
            self._connected = False
            return False

    def ensure_ready(self):
        if not self._connected:
            raise RuntimeError("KiwoomAdapter not connected")

    def close(self):
        self.logger.info("[KiwoomAdapter] 종료")
        self._connected = False

    # ===== 계좌/포지션 =====
    def get_cash(self) -> int:
        self.ensure_ready()
        if self.dry_run:
            return self._cash
        # TODO: Kiwoom 계좌조회 TR (ex: opw00001) 처리 후 반환
        self.logger.info("[KiwoomAdapter] REAL get_cash TODO")
        return 0

    def get_positions(self) -> List[Position]:
        self.ensure_ready()
        if self.dry_run:
            return list(self._positions.values())
        # TODO: 보유종목 조회 TR (ex: opw00018) 파싱
        self.logger.info("[KiwoomAdapter] REAL get_positions TODO")
        return []

    # ===== 주문 =====
    def place_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        qty: int,
        price: Optional[float] = None,
        order_type: str = "MKT",  # "MKT" or "LMT"
        user_tag: Optional[str] = None,
    ) -> OrderResult:
        """주문 접수
        - DRY_RUN: 즉시 체결 가정 (시장가), 지정가면 체결 가정/거부 간단 시뮬
        - REAL   : SendOrder 호출 (TODO)
        """
        self.ensure_ready()
        side = side.upper()
        if side not in ("BUY", "SELL"):
            return OrderResult(False, None, f"invalid side: {side}")
        if qty <= 0:
            return OrderResult(False, None, "qty must be > 0")

        self._rate_limit()

        if self.dry_run:
            oid = self._gen_order_id()
            fill_price = self._simulate_fill_price(symbol, price, order_type)
            self._apply_fill(symbol, side, qty, fill_price)
            self._orders[oid] = {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": fill_price,
                "status": "FILLED",
                "ts": time.time(),
                "user_tag": user_tag,
            }
            self.logger.info(f"[DRY_RUN] {side} {symbol} x{qty} @ {fill_price:.2f} → FILLED (oid={oid})")
            return OrderResult(True, oid, "FILLED", raw=self._orders[oid])
        else:
            # TODO: Kiwoom SendOrder 파라미터 구성 및 호출
            # OnReceiveMsg/OnReceiveChejanData 이벤트로 결과 수신 → 상태 갱신
            self.logger.info(f"[REAL] SendOrder TODO: {side} {symbol} x{qty} @ {price} ({order_type})")
            return OrderResult(False, None, "REAL SendOrder TODO")

    def cancel_order(self, order_id: str) -> OrderResult:
        self.ensure_ready()
        self._rate_limit()
        if self.dry_run:
            od = self._orders.get(order_id)
            if not od:
                return OrderResult(False, None, f"order not found: {order_id}")
            if od.get("status") == "FILLED":
                return OrderResult(False, None, "already filled")
            od["status"] = "CANCELED"
            self.logger.info(f"[DRY_RUN] cancel {order_id} → CANCELED")
            return OrderResult(True, order_id, "CANCELED", raw=od)
        else:
            # TODO: SendOrder 취소 전송 (원주문번호 포함)
            self.logger.info(f"[REAL] CancelOrder TODO: {order_id}")
            return OrderResult(False, None, "REAL CancelOrder TODO")

    # ===== 내부 헬퍼 (DRY_RUN) =====
    def _gen_order_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def _simulate_fill_price(self, symbol: str, price: Optional[float], order_type: str) -> float:
        # 아주 단순한 체결 가격 시뮬 (시장가: 임의의 현재가=10, 지정가: 입력값)
        if order_type == "MKT" or price is None:
            return 10.0
        return float(price)

    def _apply_fill(self, symbol: str, side: str, qty: int, price: float):
        if side == "BUY":
            cost = int(price * qty)
            if self._cash < cost:
                raise RuntimeError("[DRY_RUN] not enough cash")
            self._cash -= cost
            pos = self._positions.get(symbol)
            if pos:
                new_qty = pos.qty + qty
                new_avg = (pos.avg_price * pos.qty + price * qty) / new_qty
                pos.qty, pos.avg_price = new_qty, new_avg
            else:
                self._positions[symbol] = Position(symbol=symbol, qty=qty, avg_price=price)
        else:  # SELL
            pos = self._positions.get(symbol)
            if not pos or pos.qty < qty:
                raise RuntimeError("[DRY_RUN] not enough position to sell")
            self._cash += int(price * qty)
            pos.qty -= qty
            if pos.qty == 0:
                del self._positions[symbol]

    # ===== (미래 작업) 실제 이벤트/콜백 골격 =====
    # 아래 메서드들은 hub_live + Qt 루프에서 연결 예정
    def _on_login(self, err_code: int):
        # TODO: 로그인 완료 이벤트 수신 → self._connected = (err_code == 0)
        pass

    def _on_receive_tr_data(self, rqname: str, trcode: str, recordname: str, next: str):
        # TODO: 계좌/잔고/보유종목 TR 결과 파싱
        pass

    def _on_receive_chejan_data(self, gubun: str, item_cnt: int, fid_list: str):
        # TODO: 주문/체결 이벤트 → self._orders 상태 갱신
        pass


# 간단 자가 테스트
if __name__ == "__main__":
    kw = KiwoomAdapter(account_no="00000000", dry_run=True)
    assert kw.connect()
    print("cash:", kw.get_cash())
    r = kw.place_order("005930", "BUY", 10, order_type="MKT")
    print(r)
    print("positions:", kw.get_positions())
