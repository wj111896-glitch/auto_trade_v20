from bus.schema import Tick, Decision
t = Tick("TEST", 1234.5, 10, 0)
d = Decision("TEST", "BUY", 1.0, "demo")
print(type(t).__name__, t.symbol, t.price, t.volume, t.ts)
print(type(d).__name__, d.symbol, d.action, d.size, d.reason)
