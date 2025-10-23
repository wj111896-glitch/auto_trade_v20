from market.price import get_snapshot
snap = get_snapshot("AAA")
print("symbol:", snap.get("symbol"), "price:", snap.get("price"))
