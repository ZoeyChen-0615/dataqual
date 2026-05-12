from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from dataqual.models import RuleResult, Schema, ValidationContext

RuleFunction = Callable[[dict[str, Any], Schema, ValidationContext], list[RuleResult]]


@dataclass(slots=True)
class RuleEntry:
    name: str
    severity: str
    description: str
    func: RuleFunction


class RuleRegistry:
    _rules: dict[str, RuleEntry] = {}

    @classmethod
    # make a decorator with metadata
    def register(
        cls, *, name: str, severity: str = "error", description: str = ""
    ) -> Callable[[RuleFunction], RuleFunction]:
        # stash the rule function
        def decorator(func: RuleFunction) -> RuleFunction:
            cls._rules[name] = RuleEntry(
                name=name,
                severity=severity,
                description=description,
                func=func,
            )
            return func

        return decorator

    @classmethod
    # sample ["null_check", "range_check"]
    def get_all_rules(cls) -> list[RuleEntry]:
        return [cls._rules[name] for name in sorted(cls._rules)]

    @classmethod
    # find one rule by name
    def get_rule(cls, name: str) -> RuleEntry | None:
        return cls._rules.get(name)
