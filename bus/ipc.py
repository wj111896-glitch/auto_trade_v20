# simple in-process bus (placeholder)
from obs.log import log_info

def publish(evt):
    log_info(f"[BUS] {evt}")
