import random
import time
from types import SimpleNamespace

class PriceFeedMock:
    """
    모의 가격 피드 (테스트용)
    일정 주기로 가짜 틱 데이터를 생성합니다.
    """
    def __init__(self, symbols=None, base_price=None):
        self.symbols = symbols or ["005930", "000660", "035420"]
        # 각 종목의 기본 가격 설정
        self.base_price = base_price or {s: random.uniform(60000, 120000) for s in self.symbols}

    def stream(self):
        """무한 루프 대신 generator 형태로 가짜 틱 데이터 생성"""
        while True:
            for sym in self.symbols:
                base = self.base_price[sym]
                # ±1% 랜덤 변동
                change = random.uniform(-0.01, 0.01)
                new_price = round(base * (1 + change), 2)
                self.base_price[sym] = new_price
                # tick 객체 모양(SimpleNamespace는 속성 접근 가능하게 함)
                tick = SimpleNamespace(
                    symbol=sym,
                    price=new_price,
                    ts=time.time(),
                    volume=random.randint(100, 1000)
                )
                yield tick
            # 잠시 쉬었다 다음 틱
            time.sleep(0.05)
