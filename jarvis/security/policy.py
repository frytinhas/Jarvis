from __future__ import annotations

from enum import StrEnum


class Risk(StrEnum):
    READ = "READ"
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    NETWORK = "NETWORK"
    CONTROL_DESKTOP = "CONTROL_DESKTOP"
    PRIVILEGED = "PRIVILEGED"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    CONFIRM = "CONFIRM"
    DENY = "DENY"
    ONLY_VIEW = "ONLY_VIEW"


class PolicyEngine:
    _ONLY_VIEW_RISKS = frozenset({Risk.NETWORK, Risk.CONTROL_DESKTOP})
    _DEFAULT_POLICY = {
        Risk.READ: Decision.ALLOW,
        Risk.CREATE: Decision.ALLOW,
        Risk.MODIFY: Decision.CONFIRM,
        Risk.DELETE: Decision.CONFIRM,
        Risk.EXECUTE: Decision.ALLOW,
        Risk.NETWORK: Decision.ALLOW,
        Risk.CONTROL_DESKTOP: Decision.ALLOW,
        Risk.PRIVILEGED: Decision.DENY,
    }

    def __init__(self, decisions: dict[Risk, Decision] | None = None) -> None:
        self._policy = dict(self._DEFAULT_POLICY)
        if decisions:
            self._policy.update(decisions)
        self._policy[Risk.PRIVILEGED] = Decision.DENY
        if any(
            decision is Decision.ONLY_VIEW
            for risk, decision in self._policy.items()
            if risk not in self._ONLY_VIEW_RISKS
        ):
            raise ValueError("ONLY_VIEW só é válido para NETWORK ou CONTROL_DESKTOP")

    def decide(self, risk: Risk) -> Decision:
        return self._policy[risk]

    def set_decision(self, risk: Risk, decision: Decision) -> None:
        if risk is Risk.PRIVILEGED:
            raise ValueError("PRIVILEGED deve permanecer DENY")
        if decision is Decision.ONLY_VIEW and risk not in self._ONLY_VIEW_RISKS:
            raise ValueError("ONLY_VIEW só é válido para NETWORK ou CONTROL_DESKTOP")
        self._policy[risk] = decision

    def is_view_only(self, risk: Risk) -> bool:
        """Whether a tool must restrict itself to public, non-mutating inspection."""
        return self.decide(risk) is Decision.ONLY_VIEW
