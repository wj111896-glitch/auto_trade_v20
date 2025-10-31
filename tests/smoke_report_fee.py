# -*- coding: utf-8 -*-
import csv
import os
import logging
from math import isclose

# run_daytrade.py 안의 write_session_report를 직접 테스트
from run_daytrade import write_session_report

def test_fee_tax_fifo_report():
    logger = logging.getLogger("smoke_fee")
    logger.propagate = False

    # 샘플 거래: BUY 100 @100 → SELL 60 @105, SELL 40 @110
    # 수수료/세금(bps): 매수 2, 매도 2, 거래세 23
    decisions = [
        {"action": "BUY",  "symbol": "AAA", "qty": 100, "price": 100.0, "reason": "test buy"},
        {"action": "SELL", "symbol": "AAA", "qty":  60, "price": 105.0, "reason": "test sell1"},
        {"action": "SELL", "symbol": "AAA", "qty":  40, "price": 110.0, "reason": "test sell2"},
    ]

    out_path = write_session_report(
        decisions, logger,
        fee_bps_buy=2,   # 0.02%
        fee_bps_sell=2,  # 0.02%
        tax_bps_sell=23  # 0.23%
    )

    # 1) 파일 생성 확인
    assert out_path and os.path.exists(out_path), "리포트 파일이 생성되어야 합니다"

    # 2) CSV 로드 → SELL 행만 수집
    sells = []
    with open(out_path, "r", encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if (row.get("action") or "").upper() == "SELL":
                sells.append(row)

    # SELL 두 건이 있어야 함
    assert len(sells) == 2, "SELL 행이 2개여야 합니다"

    # 기대값(소수점 2자리 반올림 기준)
    # 1차 SELL(60 @105):
    #   gross = (105-100)*60 = 300
    #   buy_fee_consumed = 2.0 * (60/100) = 1.2
    #   sell_fee = (60*105)*0.0002 = 1.26
    #   tax      = (60*105)*0.0023 = 14.49
    #   net = 300 - (1.2+1.26) - 14.49 = 283.05
    expected_sell1_net = 283.05

    # 2차 SELL(40 @110):
    #   gross = (110-100)*40 = 400
    #   buy_fee_consumed = 남은 0.8
    #   sell_fee = (40*110)*0.0002 = 0.88
    #   tax      = (40*110)*0.0023 = 10.12
    #   net = 400 - (0.8+0.88) - 10.12 = 388.20
    expected_sell2_net = 388.20

    got1 = float(sells[0]["pnl_net"])
    got2 = float(sells[1]["pnl_net"])

    print(f"[SMOKE] SELL#1 pnl_net={got1:.2f}, SELL#2 pnl_net={got2:.2f}")  # ← 추가

    assert isclose(got1, expected_sell1_net, abs_tol=0.01), f"1차 매도 순손익 불일치: {got1} != {expected_sell1_net}"
    assert isclose(got2, expected_sell2_net, abs_tol=0.01), f"2차 매도 순손익 불일치: {got2} != {expected_sell2_net}"

