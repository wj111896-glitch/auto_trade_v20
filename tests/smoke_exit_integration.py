# -*- coding: utf-8 -*-
"""
smoke_exit_integration.py
ExitRules + HubTrade 통합 동작 확인용 단위 테스트
"""
from hub.hub_trade import HubTrade

def test_smoke_exit_integration():
    hubtrade = HubTrade(real_mode=False, budget=1_000_000)
    out = hubtrade.run_session(["005930"], max_ticks=10)
    assert isinstance(out, dict)
    assert out["status"] == "ok"
    assert "decisions" in out
    print("\n[OK] ExitRules + HubTrade smoke integration test passed.")
