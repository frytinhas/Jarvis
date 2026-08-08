from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import shlex

from jarvis.agent.orchestrator import Orchestrator
from jarvis.config import JarvisConfig, config_path, save_config
from jarvis.configurator import REASONING_LABELS, discover_models
from jarvis.legal import license_text, schedule_license_notice
from jarvis.settings import state_directory


REASONING_LEVELS = {label.lower(): index for index, label in enumerate(REASONING_LABELS)}
EXIT_COMMANDS = {"/exit", "/quit", "/sair"}
LICENSE_COMMANDS = {"/license", "/licenca", "/licença"}
COMMANDS = (
    "/help", "/reasoning", "/model", "/config", "/clear", "/license", "/exit"
)


class SessionExit(StrEnum):
    CONTINUE = "continue"
    EXIT = "exit"
    RESTART_MODEL = "restart_model"


@dataclass(frozen=True)
class CommandResult:
    handled: bool
    text: str = ""
    action: SessionExit = SessionExit.CONTINUE
    clear_screen: bool = False
    ask_model_restart: bool = False


class LocalCommands:
    def __init__(self, orchestrator: Orchestrator, config: JarvisConfig) -> None:
        self.orchestrator = orchestrator
        self.config = config

    def handle(self, user_text: str) -> CommandResult:
        stripped = user_text.strip()
        if not stripped.startswith("/"):
            return CommandResult(False)
        command, _, raw_argument = stripped.partition(" ")
        command = command.lower()
        argument = raw_argument.strip()
        if command in EXIT_COMMANDS:
            return CommandResult(True, action=SessionExit.EXIT)
        if command in LICENSE_COMMANDS:
            return CommandResult(True, license_text())
        if command == "/help":
            return CommandResult(True, self._help())
        if command == "/clear":
            return CommandResult(True, clear_screen=True)
        if command == "/config":
            return CommandResult(True, self._config_summary())
        if command == "/reasoning":
            return self._reasoning(argument)
        if command == "/model":
            return self._model(argument)
        suggestion = next((item for item in COMMANDS if item.startswith(command)), None)
        suffix = f" Você quis dizer `{suggestion}`?" if suggestion else " Use `/help`."
        return CommandResult(True, f"Comando local desconhecido: `{command}`.{suffix}")

    def completion_candidates(self, buffer: str) -> list[str]:
        lowered = buffer.lower()
        candidates: list[str]
        if lowered.startswith("/reasoning "):
            candidates = [f"/reasoning {level}" for level in REASONING_LEVELS]
        elif lowered.startswith("/model "):
            candidates = [f"/model {label}" for label, _ in self._models()]
        else:
            candidates = list(COMMANDS)
        return [candidate for candidate in candidates if candidate.lower().startswith(lowered)]

    def _persist_settings(self, **updates: object) -> None:
        settings = self.config.settings.model_copy(update=updates)
        updated = self.config.model_copy(update={"settings": settings})
        save_config(updated)
        schedule_license_notice()
        self.config = updated

    def _reasoning(self, argument: str) -> CommandResult:
        if not argument:
            level = self.config.settings.default_reasoning_level
            return CommandResult(True, f"Reasoning atual: {REASONING_LABELS[level]} (nível {level}).")
        normalized = argument.lower()
        if normalized not in REASONING_LEVELS:
            accepted = ", ".join(REASONING_LEVELS)
            return CommandResult(True, f"Nível inválido. Use: {accepted}.")
        level = REASONING_LEVELS[normalized]
        self._persist_settings(default_reasoning_level=level)
        self.orchestrator.set_thinking_budget_tokens((0, 512, 1024, 2048, -1)[level])
        return CommandResult(
            True,
            f"Reasoning alterado para **{REASONING_LABELS[level]}** e salvo em `{config_path()}`.",
        )

    def _models(self) -> list[tuple[str, Path]]:
        directory = self.config.settings.model_directory
        if directory is None:
            return []
        try:
            models = discover_models(directory)
        except (OSError, ValueError):
            return []
        return [(str(model.relative_to(directory)), model) for model in models]

    def _model(self, argument: str) -> CommandResult:
        models = self._models()
        current = self.config.settings.model_path
        if not argument:
            choices = "\n".join(
                f"- {'**' if path == current else ''}{label}{'**' if path == current else ''}"
                for label, path in models
            ) or "- Nenhum GGUF encontrado na pasta configurada."
            return CommandResult(True, f"Modelo atual: `{current}`\n\nModelos disponíveis:\n{choices}")
        try:
            parsed = shlex.split(argument)
        except ValueError as error:
            return CommandResult(True, f"Nome de modelo inválido: {error}")
        requested = " ".join(parsed)
        exact = [(label, path) for label, path in models if label == requested]
        if not exact:
            by_name = [(label, path) for label, path in models if path.name == requested]
            exact = by_name if len(by_name) == 1 else []
        if not exact:
            return CommandResult(True, "Modelo não encontrado ou nome ambíguo. Use `/model` para listar.")
        label, selected = exact[0]
        if selected == current:
            return CommandResult(True, f"`{label}` já é o modelo configurado.")
        self._persist_settings(model_path=selected)
        marker = state_directory() / "restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return CommandResult(
            True,
            f"Modelo **{label}** salvo. A troca só será aplicada após reiniciar o servidor.",
            ask_model_restart=True,
        )

    def _help(self) -> str:
        return """## Comandos locais

- `/reasoning off|low|medium|high|max` — altera e salva o reasoning.
- `/model [modelo]` — lista ou seleciona um GGUF.
- `/config` — mostra a configuração atual.
- `/clear` — limpa a tela sem apagar o contexto.
- `/license` — mostra a licença completa.
- `/exit` — encerra a sessão."""

    def _config_summary(self) -> str:
        settings = self.config.settings
        return (
            "## Configuração atual\n\n"
            f"- Modelo: `{settings.model_path}`\n"
            f"- Reasoning: **{REASONING_LABELS[settings.default_reasoning_level]}**\n"
            f"- Timeout do LLM: {settings.llm_request_timeout_seconds}s\n"
            f"- Timeout total: {settings.interaction_timeout_seconds}s\n"
            f"- Painel: {settings.display_log_level.value}\n"
            f"- Cores: {settings.color_mode.value}\n"
            f"- Configuração: `{config_path()}`\n"
            f"- Paleta: `{config_path().parent / 'colors.toml'}`"
        )
