# -*- coding: utf-8 -*-
# risk/policies/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Protocol

@dataclass
class PolicyResult:
    allow: bool
    reason: str = ""
    max_qty_hint: Optional[int] = None  # 정책이 권고/상한 수량을 제시할 때

class Policy(Protocol):
    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult: ...
    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]: ...

class BasePolicy:
    """편의 기본 정책 베이스 (필요시 상속)"""
    def check_entry(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> PolicyResult:
        return PolicyResult(True)
    def size_hint(self, symbol: str, price: float, portfolio: Dict[str, dict], ctx: Dict[str, Any]) -> Optional[int]:
        return None
