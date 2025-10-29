# -*- coding: utf-8 -*-
"""
장외 1주 주문 리허설 (기본: 미발사 프리뷰)
- 실제 주문 발사 조건: (1) --arm 옵션 + (2) config.DRY_RUN == False
"""
import os, sys, argparse
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # project root

from obs.log import get_logger
from order.router import OrderRouter
from common import config

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="005930")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--price", type=float, default=1.0, help="LMT 가격(장외 거부 유도)")
    ap.add_argument("--arm", action="store_true", help="실제 주문 발사(주의!)")
    args = ap.parse_args()

    log = get_logger("order_rehearsal")
    log.info("BROKER=%s DRY_RUN=%s ACCOUNT_NO=%s", config.BROKER, config.DRY_RUN, config.ACCOUNT_NO)
    log.info("Target: %s x%d @ %.2f (LMT)", args.symbol, args.qty, args.price)

    router = OrderRouter(get_logger("router"))
    if hasattr(router, "set_mode"):
        router.set_mode("REAL", budget=None)  # 실제 어댑터로 붙되, 아래에서 발사 여부 통제

    ok = router.connect()
    log.info("router.connect() -> %s", ok)
    if not ok:
        log.error("연결 실패")
        return

    # 안전장치: 기본은 프리뷰
    if not args.arm:
        log.info("PREVIEW ONLY: --arm 없음 → 주문 미발사")
        return
    if config.DRY_RUN:
        log.warning("DRY_RUN=True → 안전차단(주문 미발사). config.DRY_RUN=False 로 바꿔야 발사됩니다.")
        return

    # 여기까지 왔으면 정말 발사
    order = {"action": "BUY", "symbol": args.symbol, "qty": args.qty, "order_type": "LMT", "price": args.price}
    log.info(">>> SENDING ORDER: %s", order)
    res = router.route(order)  # 어댑터가 장외/가격불가로 거부되면 그 코드가 로그로 남음
    log.info("route() -> %s", res)
    log.info("DONE")

if __name__ == "__main__":
    main()
