# -*- coding: utf-8 -*-
"""
Hub / HubTrade — ExitRules → RiskGate → OrderRouter 통합 루프
- 보유 포지션은 ExitRules 우선평가로 즉시 청산
- 같은 틱에서 막 청산한 심볼은 재진입 쿨다운
- exit_reason 로깅
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import time

from scoring.core import ScoreEngine
from scoring.rules.exit_rules import ExitRules
from risk.core import RiskGate
from risk.policies.exposure import ExposurePolicy
try:
    from risk.policies.day_dd import make_daydd
except ImportError:
    from risk.core import make_daydd

from order.router import OrderRouter
from obs.log import get_logger

logger = get_logger(__name__)


# ========== 데이터 모델 ==========
@dataclass
class Position:
    symbol: str
    qty: int
    avg_price: float
    last_high: float = 0.0
    entry_ts: float = 0.0
    exit_reason: Optional[str] = None


@dataclass
class RiskEvalRes:
    allow: bool
    reason: str = ""
    max_qty_hint: Optional[int] = None


# ========== 유틸 ==========
def _make_default_scorer() -> ScoreEngine:
    """ScoreEngine.default() 유무/시그니처 차이를 흡수하는 방어 생성"""
    if hasattr(ScoreEngine, "default"):
        try:
            return ScoreEngine.default()  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        from common.config import DAYTRADE  # type: ignore
        if isinstance(DAYTRADE, dict):
            weights = DAYTRADE.get("weights", {})
            th = DAYTRADE.get("thresholds", {})
            buy_th = th.get("buy", 0.55)
            sell_th = th.get("sell", -0.55)
        else:
            weights = getattr(DAYTRADE, "weights", {})
            th = getattr(DAYTRADE, "thresholds", {})
            buy_th = th.get("buy", 0.55) if isinstance(th, dict) else 0.55
            sell_th = th.get("sell", -0.55) if isinstance(th, dict) else -0.55
        try:
            return ScoreEngine(weights=weights, buy_threshold=buy_th, sell_threshold=sell_th)  # type: ignore[call-arg]
        except TypeError:
            return ScoreEngine()
    except Exception:
        return ScoreEngine()


def _make_default_router():
    """OrderRouter를 환경에 맞춰 안전하게 생성"""
    try:
        if hasattr(OrderRouter, "dry_run"):
            return OrderRouter.dry_run()
    except Exception:
        pass
    try:
        return OrderRouter()
    except Exception:
        try:
            from order.adapters.mock import MockAdapter
            return OrderRouter(adapter=MockAdapter())
        except Exception:
            raise RuntimeError("OrderRouter 초기화 방법을 찾지 못했습니다. router를 직접 주입해 주세요.")


def _make_exposure_policy_or_none():
    """ExposurePolicy.default() 유무/시그니처 차이를 흡수, 실패 시 None"""
    try:
        if hasattr(ExposurePolicy, "default"):
            return ExposurePolicy.default()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        return ExposurePolicy()
    except Exception:
        return None


# ========== Hub ==========
class Hub:
    def __init__(
        self,
        scorer: ScoreEngine,
        risk: RiskGate,
        router: OrderRouter,
        exit_rules: ExitRules,
        min_reentry_cooldown_ticks: int = 10,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.scorer = scorer
        self.risk = risk
        self.router = router
        self.exit_rules = exit_rules
        self.min_reentry_cooldown_ticks = min_reentry_cooldown_ticks

        self.positions: Dict[str, Position] = {}
        self.recent_exit_tick: Dict[str, int] = {}  # 재진입 쿨다운 기록
        self.tick_idx: int = 0

        # ---- Risk ctx 기본 슬롯
        self.config: Dict[str, Any] = config or {}
        self.sector_map: Dict[str, str] = {}  # 다음 단계(섹터 정책)에서 실제 값 주입
        # equity/sector 노출 계산 스텁 (필요 시 덮어쓰기)
        self._equity_now = lambda: float(self.config.get("budget") or 0.0)  # 예산을 기본 equity로
        self._sector_exposure = lambda: {}

    # --- helper: PnL 기반 상태 업데이트 (trailing 고점 갱신 등)
    def _update_pos_state(self, pos: Position, last_price: float) -> None:
        if last_price > pos.last_high:
            pos.last_high = last_price

    # --- safe scorer wrapper: 다양한 시그니처를 흡수
    def _safe_score(self, sym: str, price: float, ctx: Dict[str, Any]) -> float:
        s = self.scorer
        snap = {sym: price}
        for args in (
            (sym, price, ctx),
            (sym, price),
            (snap, ctx),
            (snap,),
            (price,),
            (sym,),
            tuple(),
        ):
            try:
                val = s.score(*args)  # type: ignore[misc]
                return float(val)
            except TypeError:
                continue
            except Exception:
                return 0.0
        return 0.0

    # --- safe risk wrapper: 다양한 RiskGate 시그니처/반환형 흡수 (portfolio/ctx 우선)
    def _risk_eval(self, symbol: str, price: float, score: float, ctx: Dict[str, Any]) -> RiskEvalRes:
        r = self.risk

        # 1) 현재 포지션 → 간단한 portfolio dict
        portfolio: Dict[str, Dict[str, float]] = {
            s: {"qty": float(p.qty), "avg_price": float(p.avg_price)}
            for s, p in self.positions.items()
        }

        # 2) ctx 보강 (먼저 완성)
        safe_ctx: Dict[str, Any] = {}
        if isinstance(ctx, dict):
            safe_ctx.update(ctx)

        budget_val = float(self.config.get("budget") or 0.0)
        equity_val = float(self._equity_now() or budget_val)

        # ExposurePolicy 호환용 블록/별칭
        account_block = {"equity": equity_val}
        exposure_block = {
            "budget": budget_val,
            "equity": equity_val,
            "equity_now": equity_val,
            "cash": budget_val,               # alias
            "account": account_block,
            "portfolio": portfolio,
            "positions": portfolio,           # alias
            "sector_map": self.sector_map,
            "sector_exposure": self._sector_exposure() or {},
        }

        safe_ctx.update({
            "tick_idx": self.tick_idx,
            "symbol": symbol,
            "price": price,
            "score": score,

            # top-level aliases
            "budget": budget_val,
            "equity": equity_val,
            "equity_now": equity_val,
            "cash": budget_val,
            "account": account_block,
            "portfolio": portfolio,
            "positions": portfolio,
            "sector_map": self.sector_map,
            "sector_exposure": exposure_block["sector_exposure"],

            # nested blocks (여러 구현 호환)
            "exposure": exposure_block,
            "exposure_ctx": exposure_block,
            "risk_ctx": exposure_block,
        })

        # 2.5) RiskGate/Policy 인스턴스 속성에도 컨텍스트 강제 주입
        try:
            for attr in ("ctx", "_ctx", "exposure_ctx", "risk_ctx", "last_ctx", "_last_ctx"):
                setattr(self.risk, attr, safe_ctx)
            policies = getattr(self.risk, "policies", None)
            if isinstance(policies, (list, tuple)):
                for p in policies:
                    for attr in ("ctx", "_ctx", "exposure_ctx", "risk_ctx", "last_ctx", "_last_ctx"):
                        try:
                            setattr(p, attr, safe_ctx)
                        except Exception:
                            pass
                    if hasattr(p, "set_ctx") and callable(getattr(p, "set_ctx")):
                        try:
                            p.set_ctx(safe_ctx)
                        except Exception:
                            pass
            if hasattr(self.risk, "set_ctx") and callable(getattr(self.risk, "set_ctx")):
                try:
                    self.risk.set_ctx(safe_ctx)
                except Exception:
                    pass
        except Exception:
            pass

        # 3) 다양한 구현을 지원하는 호출 시도: kwargs 우선 → 위치인자 폴백
        # 3-1) kwargs 우선
        for meth in ("evaluate_entry", "evaluate", "check_entry", "gate", "allow"):
            fn = getattr(r, meth, None)
            if not callable(fn):
                continue
            try:
                res = fn(symbol=symbol, price=price, portfolio=portfolio, score=score, ctx=safe_ctx)
                # normalize
                if isinstance(res, RiskEvalRes):
                    return res
                if hasattr(res, "allow"):
                    return RiskEvalRes(bool(getattr(res, "allow")),
                                       str(getattr(res, "reason", "")),
                                       getattr(res, "max_qty_hint", None))
                if isinstance(res, dict):
                    return RiskEvalRes(bool(res.get("allow", True)),
                                       str(res.get("reason", "")),
                                       res.get("max_qty_hint"))
                if isinstance(res, tuple) and res:
                    allow = bool(res[0])
                    reason = str(res[1]) if len(res) > 1 else ""
                    hint = res[2] if len(res) > 2 else None
                    return RiskEvalRes(allow, reason, hint)
                if isinstance(res, bool):
                    return RiskEvalRes(res)
            except TypeError:
                pass
            except Exception as e:
                return RiskEvalRes(False, reason=f"{meth}_error:{e}")

        # 3-2) 위치 인자 폴백
        arg_sets = (
            (symbol, price, portfolio, score, safe_ctx),
            (symbol, price, portfolio, safe_ctx),
            (portfolio, safe_ctx),
            (symbol, price, safe_ctx),
            (symbol, price),
            (portfolio,),
            (safe_ctx,),
            tuple(),
        )
        for meth in ("evaluate_entry", "evaluate", "check_entry", "gate", "allow"):
            fn = getattr(r, meth, None)
            if not callable(fn):
                continue
            for args in arg_sets:
                try:
                    res = fn(*args)  # type: ignore[misc]
                except TypeError:
                    continue
                except Exception as e:
                    return RiskEvalRes(False, reason=f"{meth}_error:{e}")

                if isinstance(res, RiskEvalRes):
                    return res
                if hasattr(res, "allow"):
                    return RiskEvalRes(
                        bool(getattr(res, "allow")),
                        str(getattr(res, "reason", "")),
                        getattr(res, "max_qty_hint", None),
                    )
                if isinstance(res, dict):
                    return RiskEvalRes(
                        bool(res.get("allow", True)),
                        str(res.get("reason", "")),
                        res.get("max_qty_hint"),
                    )
                if isinstance(res, tuple) and res:
                    allow = bool(res[0])
                    reason = str(res[1]) if len(res) > 1 else ""
                    hint = res[2] if len(res) > 2 else None
                    return RiskEvalRes(allow, reason, hint)
                if isinstance(res, bool):
                    return RiskEvalRes(res)

        return RiskEvalRes(True)

    def _get_buy_threshold(self) -> float:
        """ScoreEngine의 buy_threshold가 없으면 0.55를 기본 사용"""
        try:
            return float(getattr(self.scorer, "buy_threshold", 0.55))
        except Exception:
            return 0.55

    # --- buy/sell wrappers
    def _buy(self, symbol: str, price: float, qty: int, reason: str) -> None:
        ok, fill_qty, fill_price = self.router.buy(symbol, qty, price, reason)
        if ok and fill_qty > 0:
            self.positions[symbol] = Position(
                symbol=symbol,
                qty=fill_qty,
                avg_price=fill_price,
                last_high=fill_price,
                entry_ts=time.time(),
            )
            logger.info(f"[BUY] {symbol} x{fill_qty} @ {fill_price:.3f} reason={reason}")

    def _sell(self, symbol: str, price: float, qty: int, reason: str) -> None:
        ok, fill_qty, fill_price = self.router.sell(symbol, qty, price, reason)
        if ok and fill_qty > 0:
            logger.info(f"[SELL] {symbol} x{fill_qty} @ {fill_price:.3f} reason={reason}")

    # --- main tick entry
    def on_tick(self, snapshot: Dict[str, float], ctx: Optional[Dict[str, Any]] = None) -> None:
        self.tick_idx += 1

        # 0) 실행 컨텍스트 구성
        safe_ctx: Dict[str, Any] = {}
        if isinstance(ctx, dict):
            safe_ctx.update(ctx)

        budget_val = float(self.config.get("budget") or 0.0)
        equity_val = float(self._equity_now() or budget_val)
        account_block = {"equity": equity_val}

        exposure_block = {
            "budget": budget_val,
            "equity": equity_val,
            "equity_now": equity_val,
            "cash": budget_val,
            "portfolio": {
                s: {"qty": float(p.qty), "avg_price": float(p.avg_price)}
                for s, p in self.positions.items()
            },
            "positions": {
                s: {"qty": float(p.qty), "avg_price": float(p.avg_price)}
                for s, p in self.positions.items()
            },
            "sector_map": self.sector_map,
            "sector_exposure": self._sector_exposure() or {},
            "account": account_block,
        }

        safe_ctx.update({
            "budget": budget_val,
            "equity": equity_val,
            "equity_now": equity_val,
            "cash": budget_val,
            "sector_map": self.sector_map,
            "sector_exposure": exposure_block["sector_exposure"],
            "portfolio": exposure_block["portfolio"],
            "positions": exposure_block["positions"],
            "account": account_block,
            "exposure": exposure_block,
            "exposure_ctx": exposure_block,
            "risk_ctx": exposure_block,
        })

        # 1) 포지션 보유 종목: ExitRules 우선 평가
        if self.positions:
            to_close: List[Tuple[str, Position, object]] = []
            for sym, pos in list(self.positions.items()):
                price = snapshot.get(sym)
                if price is None:
                    continue
                self._update_pos_state(pos, price)

                dec = self.exit_rules.apply_exit(
                    price_now=price,
                    avg_price=pos.avg_price,
                    last_high=pos.last_high,
                    min_hold_ticks=1,
                )
                if getattr(dec, "should_exit", False):
                    to_close.append((sym, pos, dec))

            for sym, pos, dec in to_close:
                self._sell(sym, snapshot[sym], pos.qty, reason=getattr(dec, "reason", "exit"))
                self.recent_exit_tick[sym] = self.tick_idx
                pos.exit_reason = getattr(dec, "reason", None)
                logger.info(f"[EXIT] {sym} reason={pos.exit_reason}")
                del self.positions[sym]

        # 2) 신규 진입: RiskGate → BUY
        for sym, price in snapshot.items():
            # 같은 틱에 막 청산한 심볼은 재진입 차단
            last_exit_tick = self.recent_exit_tick.get(sym, -10**9)
            if self.tick_idx - last_exit_tick < self.min_reentry_cooldown_ticks:
                continue
            # 이미 보유 중이면 skip
            if sym in self.positions:
                continue

            score = self._safe_score(sym, price, safe_ctx)
            risk_res = self._risk_eval(symbol=sym, price=price, score=score, ctx=safe_ctx)
            if not risk_res.allow:
                logger.debug(f"[RISK-HOLD] {sym} reason={risk_res.reason}")
                continue

            qty_hint = risk_res.max_qty_hint or 0
            qty = max(1, qty_hint)

            if score >= self._get_buy_threshold():
                self._buy(sym, price, qty, reason=f"score={score:.3f}")


# ========== HubTrade ==========
class HubTrade:
    def __init__(
        self,
        symbols: List[str],
        scorer: Optional[ScoreEngine] = None,
        risk: Optional[RiskGate] = None,
        router: Optional[OrderRouter] = None,
        exit_rules: Optional[ExitRules] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.symbols = symbols
        self.scorer = scorer if scorer is not None else _make_default_scorer()

        # 정책: DayDD + Exposure 기본 탑재 (ExposurePolicy 생성 실패 시 DayDD만)
        if risk is not None:
            self.risk = risk
        else:
            policies = [make_daydd()]
            _expo = _make_exposure_policy_or_none()
            if _expo is not None:
                policies.append(_expo)
            self.risk = RiskGate(policies=policies)

        self.router = router or _make_default_router()
        self.exit_rules = exit_rules or ExitRules()
        self.config = config or {}

        self.hub = Hub(
            scorer=self.scorer,
            risk=self.risk,
            router=self.router,
            exit_rules=self.exit_rules,
            config=self.config,
        )

    def run_session(self, price_feed_iter, max_ticks: int = 1000):
        ticks = 0
        for snapshot in price_feed_iter:
            self.hub.on_tick(snapshot)
            ticks += 1
            if ticks >= max_ticks:
                break
        logger.info(f"[SESSION END] ticks={ticks}")
