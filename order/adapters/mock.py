from obs.log import log_info

class MockOrderAdapter:
    def send_order(self, req):
        log_info(f"[MOCK ORDER] {req}")
        return {"status": "FILLED", "order_id": "MOCK123"}
