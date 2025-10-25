import logging
import os

def get_logger(name="app", logfile=None, level=logging.INFO):
    """단순 콘솔+파일 로거 (없으면 자동 생성)"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 이미 세팅된 로거 재사용

    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    # 콘솔 출력
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # 파일 출력 (logs 폴더 자동 생성)
    if logfile:
        os.makedirs(os.path.dirname(logfile), exist_ok=True)
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
