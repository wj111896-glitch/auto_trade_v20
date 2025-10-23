import logging, os
from logging.handlers import RotatingFileHandler

_LOGGER = None

def _ensure_logger():
    global _LOGGER
    if _LOGGER:
        return _LOGGER

    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("auto_trade_v20")
    logger.setLevel(logging.INFO)

    # 콘솔
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    # 파일 (logs/app.log, 1MB 로테이션 3개)
    fh = RotatingFileHandler("logs/app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))

    logger.addHandler(ch)
    logger.addHandler(fh)

    _LOGGER = logger
    return _LOGGER

def info(msg: str, *args, **kwargs):
    _ensure_logger().info(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs):
    _ensure_logger().error(msg, *args, **kwargs)

def debug(msg: str, *args, **kwargs):
    _ensure_logger().debug(msg, *args, **kwargs)

