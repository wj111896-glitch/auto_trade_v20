from obs.log import log_info
from order.adapters.mock import MockOrderAdapter

class OrderRouter:
    def __init__(self, adapter=None):
        self.adapter = adapter or MockOrderAdapter()

    def submit(self, order_req):
        log_info(f"Router submitting order: {order_req}")
        return self.adapter.send_order(order_req)
