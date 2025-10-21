from obs.log import log_info
from common.config import CONFIG

class RiskGate:
    def check(self, context):
        log_info("[RISK] check OK (mock)")
        return True
