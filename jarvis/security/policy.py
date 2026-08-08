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
    _POLICY = {
        Risk.READ: Decision.ALLOW,
        Risk.CREATE: Decision.CONFIRM,
        Risk.MODIFY: Decision.CONFIRM,
        Risk.DELETE: Decision.CONFIRM,
        Risk.EXECUTE: Decision.CONFIRM,
        Risk.PRIVILEGED: Decision.DENY,
    }

    def decide(self, risk: Risk) -> Decision:
        return self._POLICY[risk]

