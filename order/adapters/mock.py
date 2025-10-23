class MockAdapter:
    def buy(self, decision):
        print("[MOCK BUY]", decision.symbol, decision.size, decision.reason)
    def sell(self, decision):
        print("[MOCK SELL]", decision.symbol, decision.size, decision.reason)
