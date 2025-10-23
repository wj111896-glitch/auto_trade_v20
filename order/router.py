class OrderRouter:
    def __init__(self, adapter):
        self.adapter = adapter

    def route(self, decision):
        if decision.action == "BUY":
            self.adapter.buy(decision)
        elif decision.action == "SELL":
            self.adapter.sell(decision)
        else:
            print("[ROUTER] HOLD:", decision.symbol)
