from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import shlex

from jarvis.agent.orchestrator import Orchestrator
from jarvis.config import ConfigFileError, JarvisConfig, config_path, load_config, save_config
from jarvis.configurator import REASONING_LABELS, discover_models
from jarvis.hardware import recommended_context_size
from jarvis.legal import license_text, schedule_license_notice
from jarvis.profiles import profile_locations
from jarvis.security.policy import Decision, Risk
from jarvis.settings import state_directory


REASONING_LEVELS = {label.lower(): index for index, label in enumerate(REASONING_LABELS)}
PERMISSION_RISKS = {
    "read": Risk.READ,
    "create": Risk.CREATE,
    "modify": Risk.MODIFY,
    "write": Risk.MODIFY,
    "delete": Risk.DELETE,
    "exec": Risk.EXECUTE,
    "execute": Risk.EXECUTE,
}
PERMISSION_DECISIONS = {
    "allow": Decision.ALLOW,
    "confirm": Decision.CONFIRM,
    "confirmation": Decision.CONFIRM,
    "deny": Decision.DENY,
}
CONFIGURABLE_RISKS = (Risk.READ, Risk.CREATE, Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)
EXIT_COMMANDS = {"/exit", "/sair"}
LICENSE_COMMANDS = {"/license", "/licenca", "/licença"}
COMMANDS = (
    "/help", "/reasoning", "/model", "/context", "/permissions", "/config", "/clear",
    "/learning", "/finish", "/license", "/exit", "/quit"
)


class SessionExit(StrEnum):
    CONTINUE = "continue"
    EXIT = "exit"
    RESTART_MODEL = "restart_model"
    FULL_STOP = "full_stop"
    SWITCH_PROFILE = "switch_profile"


@dataclass(frozen=True)
class CommandResult:
    handled: bool
    text: str = ""
    action: SessionExit = SessionExit.CONTINUE
    clear_screen: bool = False
    ask_model_restart: bool = False
    ask_profile_switch: bool = False
    target_profile: str | None = None


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
        if command == "/quit":
            return CommandResult(True, action=SessionExit.FULL_STOP)
        if command in LICENSE_COMMANDS:
            return CommandResult(True, license_text())
        if command == "/help":
            return CommandResult(True, self._help())
        if command == "/clear":
            return CommandResult(True, clear_screen=True)
        if command == "/config":
            return CommandResult(True, self._config_summary())
        if command == "/permissions":
            return self._permissions(argument)
        if command == "/reasoning":
            return self._reasoning(argument)
        if command == "/model":
            return self._model(argument)
        if command == "/context":
            return self._context(argument)
        if command == "/finish":
            return CommandResult(True, "`/finish` só é usado durante uma sessão de aprendizado.")
        if command == "/learning":
            return CommandResult(True, "Use `/learning` sem argumentos para iniciar o aprendizado.")
        suggestion = next((item for item in COMMANDS if item.startswith(command)), None)
        suffix = f" Você quis dizer `{suggestion}`?" if suggestion else " Use `/help`."
        return CommandResult(True, f"Comando local desconhecido: `{command}`.{suffix}")

    def completion_candidates(self, buffer: str) -> list[str]:
        lowered = buffer.lower()
        candidates: list[str]
        if lowered.startswith("/reasoning "):
            candidates = [f"/reasoning {level}" for level in REASONING_LEVELS]
        elif lowered.startswith("/model "):
            candidates = [f"/model {label}" for label, _ in self._profiles()]
        elif lowered.startswith("/context "):
            candidates = ["/context reset"]
        elif lowered.startswith("/permissions "):
            candidates = [
                f"/permissions {risk} {decision}"
                for risk in ("read", "create", "modify", "delete", "exec")
                for decision in ("allow", "confirmation", "deny")
            ]
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
        previous_level = self.config.settings.default_reasoning_level
        self._persist_settings(default_reasoning_level=level)
        self.orchestrator.set_thinking_budget_tokens((0, 512, 1024, 2048, -1)[level])
        template_changed = (previous_level == 0) != (level == 0)
        if template_changed:
            marker = state_directory() / "restart-required"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        return CommandResult(
            True,
            f"Reasoning alterado para **{REASONING_LABELS[level]}** e salvo em `{config_path()}`."
            + (
                " O thinking do template será atualizado ao reiniciar o servidor."
                if template_changed else ""
            ),
            ask_model_restart=template_changed,
        )

    def _profiles(self) -> list[tuple[str, Path]]:
        profiles: list[tuple[str, Path]] = []
        for location in profile_locations():
            if location.slug is None:
                continue
            try:
                configured = load_config(location.config_file)
            except ConfigFileError:
                continue
            if configured.settings.model_path is not None:
                profiles.append((location.slug, configured.settings.model_path))
        return profiles

    def _model(self, argument: str) -> CommandResult:
        models = self._profiles()
        current = self.config.settings.model_path
        if not argument:
            choices = "\n".join(
                f"- {'**' if path == current else ''}{label}{'**' if path == current else ''}"
                for label, path in models
            ) or "- Nenhum outro perfil configurado."
            return CommandResult(True, f"Modelo atual: `{current}`\n\nPerfis disponíveis:\n{choices}")
        try:
            parsed = shlex.split(argument)
        except ValueError as error:
            return CommandResult(True, f"Nome de modelo inválido: {error}")
        requested = " ".join(parsed)
        exact = [(label, path) for label, path in models if label == requested.lower()]
        if not exact:
            return CommandResult(True, "Perfil não encontrado. Use `/model` para listar.")
        label, selected = exact[0]
        if selected == current:
            return CommandResult(True, f"`{label}` já é o perfil atual.")
        return CommandResult(
            True,
            f"Trocar para **{label}** (`{selected}`) encerrará esta sessão e poderá carregar outro "
            "modelo em RAM/VRAM. Um resumo transitório da conversa será entregue ao novo perfil.",
            ask_profile_switch=True,
            target_profile=label,
        )

    def _context(self, argument: str) -> CommandResult:
        current = self.config.settings.context_size
        recommended = recommended_context_size()
        if not argument:
            return CommandResult(
                True,
                f"Contexto atual: **{current} tokens**. Recomendação automática: "
                f"**{recommended} tokens**. Use `/context N` ou `/context reset`.",
            )
        if argument.lower() == "reset":
            context_size = recommended
        else:
            try:
                context_size = int(argument)
            except ValueError:
                return CommandResult(True, "Uso: `/context N` ou `/context reset`; N deve ser inteiro.")
            if context_size <= 0 or context_size % 1024:
                return CommandResult(True, "O contexto deve ser um inteiro positivo múltiplo de 1024.")
        if context_size == current:
            return CommandResult(True, f"O contexto já está em **{context_size} tokens**.")
        self._persist_settings(context_size=context_size)
        marker = state_directory() / "restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        source = "automático" if argument.lower() == "reset" else "manual"
        return CommandResult(
            True,
            f"Contexto {source} de **{context_size} tokens** salvo. A mudança só será aplicada "
            "após reiniciar o servidor.",
            ask_model_restart=True,
        )

    def _permissions(self, argument: str) -> CommandResult:
        if not argument:
            rows = "\n".join(
                f"- `{risk.value}`: **{self.config.settings.permissions[risk].value}**"
                for risk in CONFIGURABLE_RISKS
            )
            return CommandResult(
                True,
                "## Permissões globais atuais\n\n"
                f"{rows}\n"
                "- `PRIVILEGED`: **DENY** (fixo)\n\n"
                "A `Blacklist.txt` e os bloqueios internos podem tornar a decisão mais "
                "restritiva para um path específico.",
            )
        try:
            arguments = shlex.split(argument)
        except ValueError as error:
            return CommandResult(True, f"Parâmetros inválidos: {error}")
        if len(arguments) != 2:
            return CommandResult(
                True,
                "Uso: `/permissions read|create|modify|delete|exec "
                "allow|confirmation|deny`.",
            )
        risk_name, decision_name = (value.lower() for value in arguments)
        risk = PERMISSION_RISKS.get(risk_name)
        if risk is None:
            return CommandResult(
                True,
                "Categoria inválida. Use: read, create, modify, delete ou exec.",
            )
        decision = PERMISSION_DECISIONS.get(decision_name)
        if decision is None:
            return CommandResult(
                True,
                "Decisão inválida. Use: allow, confirmation ou deny.",
            )
        if self.config.settings.permissions[risk] is decision:
            return CommandResult(True, f"`{risk.value}` já está como **{decision.value}**.")
        permissions = dict(self.config.settings.permissions)
        permissions[risk] = decision
        self._persist_settings(permissions=permissions)
        self.orchestrator.set_permission_decision(risk, decision)
        return CommandResult(
            True,
            f"Permissão `{risk.value}` alterada para **{decision.value}**, aplicada nesta sessão "
            f"e salva em `{config_path()}`.",
        )

    def _help(self) -> str:
        return """## Comandos locais

- `/reasoning off|low|medium|high|max` — altera e salva o reasoning.
- `/model [modelo]` — lista ou seleciona um GGUF.
- `/context [tokens|reset]` — consulta ou altera o contexto do modelo.
- `/permissions [categoria decisão]` — consulta ou altera permissões.
- `/config` — mostra a configuração atual.
- `/clear` — limpa a tela sem apagar o contexto.
- `/learning` — recria, após confirmação, o contexto privado de aprendizado.
- `/finish` — conclui uma sessão de aprendizado e propõe o resumo para aprovação.
- `/license` — mostra a licença completa.
- `/exit` — encerra a sessão.
- `/quit` — encerra a sessão e desliga o servidor após finalizar a memória."""

    def _config_summary(self) -> str:
        settings = self.config.settings
        return (
            "## Configuração atual\n\n"
            f"- Modelo: `{settings.model_path}`\n"
            f"- Perfil: **{settings.assistant_name}** (`{settings.command_name}`)\n"
            f"- Porta local: **{settings.server_port}**\n"
            f"- Contexto: **{settings.context_size} tokens**\n"
            f"- Reasoning: **{REASONING_LABELS[settings.default_reasoning_level]}**\n"
            f"- Timeout do LLM: {settings.llm_request_timeout_seconds}s\n"
            f"- Timeout total: {settings.interaction_timeout_seconds}s\n"
            f"- Painel: {settings.display_log_level.value}\n"
            f"- Cores: {settings.color_mode.value}\n"
            f"- Configuração: `{config_path()}`\n"
            f"- Aprendizado: **{settings.learning_state}** (`{settings.learning_context_path}`)\n"
            f"- Paleta: `{config_path().parent / 'colors.toml'}`"
        )
