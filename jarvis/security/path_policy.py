from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from jarvis.security.policy import Decision, Risk


PATH_RISKS = (Risk.READ, Risk.MODIFY, Risk.CREATE, Risk.DELETE, Risk.EXECUTE)
_RISK_INDEX = {risk: index for index, risk in enumerate(PATH_RISKS)}
_CODE_PATTERN = re.compile(r"^[012-]{1,5}$")
_DIGIT_DECISION = {"0": Decision.DENY, "1": Decision.CONFIRM, "2": Decision.ALLOW}
_DECISION_WEIGHT = {Decision.DENY: 0, Decision.CONFIRM: 1, Decision.ALLOW: 2}


class PathPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PathRule:
    path: Path
    decisions: tuple[Decision | None, ...]
    line_number: int


class PathPolicy:
    def __init__(
        self,
        rules: tuple[PathRule, ...] = (),
        *,
        project_directory: Path,
        whitelist: tuple[Path, ...] | None = None,
        error: str | None = None,
    ) -> None:
        self.rules = rules
        self.project_directory = project_directory.expanduser().resolve(strict=False)
        self.whitelist = whitelist
        self.error = error

    @property
    def valid(self) -> bool:
        return self.error is None

    @classmethod
    def load(
        cls, path: Path, *, project_directory: Path, whitelist_path: Path | None = None,
    ) -> "PathPolicy":
        try:
            text = path.read_text(encoding="utf-8")
            rules = parse_path_rules(text)
            whitelist = (
                parse_whitelist_rules(whitelist_path.read_text(encoding="utf-8"))
                if whitelist_path is not None else None
            )
        except (OSError, UnicodeError, RuntimeError, PathPolicyError) as error:
            return cls(project_directory=project_directory, error=str(error))
        return cls(rules, project_directory=project_directory, whitelist=whitelist)

    @classmethod
    def empty(cls, *, project_directory: Path) -> "PathPolicy":
        return cls(project_directory=project_directory)

    def decide(self, global_decision: Decision, risk: Risk, paths: list[Path]) -> Decision:
        if not paths:
            return global_decision
        if not self.valid:
            return Decision.DENY
        decision = global_decision
        for path in paths:
            decision = more_restrictive(decision, self._path_decision(path, risk))
        return decision

    def _path_decision(self, path: Path, risk: Risk) -> Decision:
        resolved = path.expanduser().resolve(strict=False)
        if self.whitelist is not None and not any(_contains(root, resolved) for root in self.whitelist):
            return Decision.DENY
        project_match = _contains(self.project_directory, resolved)
        if project_match and risk is not Risk.READ:
            return Decision.DENY
        if risk not in _RISK_INDEX:
            return Decision.DENY

        matching = [rule for rule in self.rules if _contains(rule.path, resolved)]
        if not matching:
            return Decision.ALLOW

        # Uma árvore que possui regra começa fechada. Linhas posteriores sobrescrevem
        # somente as posições explicitamente declaradas.
        state = [Decision.DENY] * len(PATH_RISKS)
        for rule in matching:
            for index, value in enumerate(rule.decisions):
                if value is not None:
                    state[index] = value
        return state[_RISK_INDEX[risk]]


def parse_path_rules(text: str) -> tuple[PathRule, ...]:
    rules: list[PathRule] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            raw_path, code = stripped.rsplit(maxsplit=1)
        except ValueError as error:
            raise PathPolicyError(f"Blacklist.txt linha {line_number}: informe um path e um código") from error
        if not _CODE_PATTERN.fullmatch(code) or not any(character.isdigit() for character in code):
            raise PathPolicyError(
                f"Blacklist.txt linha {line_number}: use de 1 a 5 posições contendo 0, 1, 2 ou -"
            )
        expanded = Path(raw_path).expanduser()
        if not expanded.is_absolute():
            raise PathPolicyError(f"Blacklist.txt linha {line_number}: o path deve ser absoluto ou começar com ~")
        padded = code.ljust(len(PATH_RISKS), "-")
        decisions = tuple(_DIGIT_DECISION.get(character) for character in padded)
        rules.append(PathRule(expanded.resolve(strict=False), decisions, line_number))
    return tuple(rules)


def parse_whitelist_rules(text: str) -> tuple[Path, ...]:
    roots: list[Path] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise PathPolicyError(f"Whitelist.txt linha {line_number}: o path deve ser absoluto ou começar com ~")
        roots.append(path.resolve(strict=False))
    if not roots:
        raise PathPolicyError("Whitelist.txt não possui nenhum path permitido")
    return tuple(dict.fromkeys(roots))


def more_restrictive(left: Decision, right: Decision) -> Decision:
    return left if _DECISION_WEIGHT[left] <= _DECISION_WEIGHT[right] else right


def _contains(parent: Path, child: Path) -> bool:
    return child == parent or parent in child.parents
