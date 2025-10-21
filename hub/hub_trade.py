from obs.log import log_info
from scoring.core import ScoreEngine
from risk.core import RiskGate
from order.router import OrderRouter
from common.config import CONFIG

def main():
    log_info("Hub starting (dry_run=%s)" % CONFIG["dry_run"])
    # TODO: 버스/시세/체결 이벤트 연결
    # 현재는 mock 데이터로 점수 엔진만 실행
    engine = ScoreEngine()
    score = engine.evaluate({"symbol": "005930", "price": 72000})
    log_info(f"[DECISION] symbol=005930 score={score} → HOLD (mock run)")

if __name__ == "__main__":
    main()
