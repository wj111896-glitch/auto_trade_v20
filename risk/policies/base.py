# -*- coding: utf-8 -*-
# risk/policies/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Protocol

@dataclass
class PolicyResult:
    """정책 판정 표준 결과."""
    allow: bool
    reason: str = ""
    # 정책이 권고/상한 수량을 제시할 때 사용 (없으면 None)
    max_qty_hint: Optional[int] = None

    # 호환성: res.ok 를 res.allow 와 동일하게 사용 가능
    @property
    def ok(self) -> bool:
        return self.allow

    # if res: 처럼 진리값 평가가 가능하게
    def __bool__(self) -> bool:
        return bool(self.allow)

class Policy(Protocol):
    """정책 프로토콜 — check_entry/size_hint를 제공하면 RiskGate가 어댑트합니다."""
    def check_entry(
        self,
        symbol: str,
        price: float,
        portfolio: Dict[str, dict],
        ctx: Dict[str, Any],
    ) -> PolicyResult: ...

    def size_hint(
        self,
        symbol: str,
        price: float,
        portfolio: Dict[str, dict],
        ctx: Dict[str, Any],
    ) -> Optional[int]: ...

class BasePolicy:
    """편의 베이스 클래스 (선택적으로 상속). 기본은 '허용/사이즈 제시 없음'."""
    def check_entry(
        self,
        symbol: str,
        price: float,
        portfolio: Dict[str, dict],
        ctx: Dict[str, Any],
    ) -> PolicyResult:
        return PolicyResult(True)

    def size_hint(
        self,
        symbol: str,
        price: float,
        portfolio: Dict[str, dict],
        ctx: Dict[str, Any],
    ) -> Optional[int]:
        return None

