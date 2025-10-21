from obs.log import log_info

class ScoreEngine:
    def evaluate(self, ctx):
        log_info(f"[SCORE] evaluating {ctx}")
        return 5  # dummy score
