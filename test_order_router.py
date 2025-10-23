from order.router import OrderRouter
from order.adapters.mock import MockAdapter
from bus.schema import Decision

adapter = MockAdapter()
router = OrderRouter(adapter)

router.route(Decision("AAA","BUY",1.0,"test"))
router.route(Decision("BBB","SELL",1.0,"test"))
router.route(Decision("CCC",None,0.0,"hold"))
