from __future__ import annotations

from enum import StrEnum


class Risk(StrEnum):
    READ = "READ"
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    PRIVILEGED = "PRIVILEGED"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    CONFIRM = "CONFIRM"
    DENY = "DENY"


class PolicyEngine:
    _DEFAULT_POLICY = {
        Risk.READ: Decision.ALLOW,
        Risk.CREATE: Decision.ALLOW,
        Risk.MODIFY: Decision.CONFIRM,
        Risk.DELETE: Decision.CONFIRM,
        Risk.EXECUTE: Decision.ALLOW,
        Risk.PRIVILEGED: Decision.DENY,
    }

    def __init__(self, decisions: dict[Risk, Decision] | None = None) -> None:
        self._policy = dict(self._DEFAULT_POLICY)
        if decisions:
            self._policy.update(decisions)
        self._policy[Risk.PRIVILEGED] = Decision.DENY

    def decide(self, risk: Risk) -> Decision:
        return self._policy[risk]
