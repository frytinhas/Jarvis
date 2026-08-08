from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex

from jarvis.agent.prompts import default_context_path, default_persona_path
from jarvis.config import ConfigFileError, JarvisConfig, config_path, load_config, save_config
from jarvis.security.policy import Decision, Risk
from jarvis.settings import DisplayLogLevel, MessageMode, UserSettings, project_root


CATEGORIES = (Risk.READ, Risk.CREATE, Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)
CATEGORY_LABELS = {
    Risk.READ: "Leitura e consulta",
    Risk.CREATE: "Criação de arquivos e diretórios",
    Risk.MODIFY: "Alteração, movimentação e renomeação",
    Risk.DELETE: "Exclusão",
    Risk.EXECUTE: "Execução de aplicações/processos futuros",
}
COMMAND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class CommandReplacement:
    path: Path
    link_target: str


@dataclass(frozen=True)
class ConfigurationResult:
    config: JarvisConfig
    previous_command: str
    reset_persona: bool
    reset_context: bool
    command_replacement: CommandReplacement | None = None

    @property
    def settings(self) -> UserSettings:
        return self.config.settings


def discover_models(directory: Path) -> list[Path]:
    root = directory.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("O local do LLM precisa ser uma pasta")
    models: list[Path] = []
    for candidate in root.rglob("*"):
        try:
            if (
                candidate.is_file()
                and candidate.suffix.lower() == ".gguf"
                and "mmproj" not in candidate.name.lower()
            ):
                models.append(candidate.resolve(strict=True))
        except (OSError, RuntimeError):
            continue
    return sorted(set(models), key=lambda item: str(item).lower())


def normalize_command_name(display_name: str) -> str:
    command = display_name.strip().lower()
    if not COMMAND_PATTERN.fullmatch(command):
        raise ValueError("Use somente letras sem acento, números, hífen ou underscore; comece por letra")
    if command == "jarvis-config":
        raise ValueError("Esse nome é reservado pelo configurador")
    return command


def ask_yes_no(prompt: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes", "s", "sim"}:
            return True
        if answer in {"n", "no", "não", "nao"}:
            return False
        print("Responda sim ou não.")


def ask_integer(prompt: str, default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Informe somente um número inteiro.")


def ask_positive_integer(prompt: str, default: int) -> int:
    while True:
        value = ask_integer(prompt, default)
        if value > 0:
            return value
        print("Informe um número inteiro maior que zero.")


def ask_choice(prompt: str, choices: list[str], default: int = 1) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        try:
            selected = int(raw) if raw else default
            if 1 <= selected <= len(choices):
                return selected
        except ValueError:
            pass
        print(f"Escolha um número entre 1 e {len(choices)}.")


def _legacy_model() -> Path | None:
    runtime = project_root() / ".runtime"
    if not runtime.is_file():
        return None
    for line in runtime.read_text(encoding="utf-8").splitlines():
        if line.startswith("MODEL_PATH="):
            try:
                value = shlex.split(line.split("=", 1)[1])[0]
                path = Path(value).expanduser().resolve(strict=True)
                return path if path.is_file() else None
            except (IndexError, OSError, ValueError):
                return None
    return None


def _choose_model(current: UserSettings) -> tuple[Path, Path]:
    default_directory = current.model_directory
    if default_directory is None:
        legacy = _legacy_model()
        default_directory = legacy.parent if legacy else None
    while True:
        hint = f" [{default_directory}]" if default_directory else ""
        raw = input(f"Pasta onde estão os modelos GGUF{hint}: ").strip()
        directory = Path(raw).expanduser() if raw else default_directory
        if directory is None:
            print("Informe uma pasta.")
            continue
        try:
            directory = directory.resolve(strict=True)
            models = discover_models(directory)
        except (OSError, ValueError) as error:
            print(f"Pasta inválida: {error}")
            continue
        if not models:
            print("Nenhum modelo GGUF foi encontrado nessa pasta.")
            continue
        print("\nModelos encontrados:")
        default_index = 1
        for index, model in enumerate(models, 1):
            if current.model_path and model == current.model_path:
                default_index = index
            size_gib = model.stat().st_size / (1024**3)
            print(f"  {index}) {model.name} ({size_gib:.1f} GiB)")
        while True:
            raw_choice = input(f"Escolha o modelo [{default_index}]: ").strip()
            try:
                choice = int(raw_choice) if raw_choice else default_index
                return directory, models[choice - 1]
            except (ValueError, IndexError):
                print("Escolha um número válido.")


def _choose_permissions(current: UserSettings) -> dict[Risk, Decision]:
    decisions: dict[Risk, Decision] = {Risk.PRIVILEGED: Decision.DENY}
    enabled: list[Risk] = []
    print("\nPermissões disponíveis:")
    for risk in CATEGORIES:
        default_enabled = current.permissions.get(risk, Decision.DENY) is not Decision.DENY
        if ask_yes_no(f"Permitir {CATEGORY_LABELS[risk]}?", default_enabled):
            enabled.append(risk)
        else:
            decisions[risk] = Decision.DENY
    print("\nAções que podem ocorrer sem confirmação:")
    for risk in enabled:
        default_allow = current.permissions.get(risk) is Decision.ALLOW
        without_confirmation = ask_yes_no(
            f"Permitir {CATEGORY_LABELS[risk]} sem confirmação?", default_allow
        )
        decisions[risk] = Decision.ALLOW if without_confirmation else Decision.CONFIRM
    return decisions


def _choose_identity(current: UserSettings) -> tuple[str, str, CommandReplacement | None]:
    custom_default = current.command_name != "jarvis" or current.assistant_name != "Jarvis"
    while True:
        if ask_yes_no("Usar um nome personalizado?", custom_default):
            hint = f" [{current.assistant_name}]" if custom_default else ""
            display_name = input(f"Novo nome{hint}: ").strip() or current.assistant_name
        else:
            display_name = "Jarvis"
        try:
            command = normalize_command_name(display_name)
            replacement = _inspect_command(command)
            if replacement is not None:
                print(
                    f"O comando {replacement.path} aponta para um launcher antigo "
                    f"ou inexistente: {replacement.link_target}"
                )
                if not ask_yes_no("Substituir esse link pelo launcher atual?", False):
                    print("Escolha outro nome de comando ou autorize a migração do link antigo.")
                    continue
            return display_name, command, replacement
        except ValueError as error:
            print(f"Nome inválido: {error}")


def _launcher_path() -> Path:
    return (project_root() / "scripts/jarvis").resolve()


def _resolved_link_target(path: Path, link_target: str) -> Path:
    target = Path(link_target)
    if not target.is_absolute():
        target = path.parent / target
    return target.resolve(strict=False)


def _inspect_command(command: str) -> CommandReplacement | None:
    target = Path.home() / ".local/bin" / command
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink():
        link_target = os.readlink(target)
        resolved = _resolved_link_target(target, link_target)
        if resolved == _launcher_path():
            return None
        if not target.exists() and resolved.parts[-2:] == ("scripts", "jarvis"):
            return CommandReplacement(path=target, link_target=link_target)
    raise ValueError(f"já existe outro comando em {target}")


def _validate_command_collision(
    command: str, approved_replacement: CommandReplacement | None = None
) -> CommandReplacement | None:
    replacement = _inspect_command(command)
    if replacement == approved_replacement:
        return replacement
    if approved_replacement is not None:
        raise ValueError("o comando mudou desde que a substituição foi confirmada")
    if replacement is not None:
        raise ValueError(f"o link antigo em {replacement.path} precisa de confirmação")
    return None


def _persona_is_default(persona: Path) -> bool:
    try:
        return persona.read_bytes() == default_persona_path().read_bytes()
    except OSError:
        return False


def _context_is_default(context: Path) -> bool:
    try:
        return context.read_bytes() == default_context_path().read_bytes()
    except OSError:
        return False


def _summary(settings: UserSettings, reset_persona: bool, reset_context: bool) -> None:
    print("\nResumo da configuração")
    print(f"  Pasta de modelos: {settings.model_directory}")
    print(f"  Modelo: {settings.model_path}")
    print("  Permissões:")
    for risk in CATEGORIES:
        print(f"    {risk}: {settings.permissions.get(risk, Decision.DENY)}")
    persona_status = "será restaurada" if reset_persona else "mantida"
    print(f"  Persona: {settings.persona_path} ({persona_status})")
    context_status = "será restaurado" if reset_context else "mantido"
    print(f"  Contexto: {project_root() / 'Context.md'} ({context_status})")
    print(f"  Nome: {settings.assistant_name}")
    print(f"  Comando: {settings.command_name}")
    print(f"  Início automático: {'ativado' if settings.autostart else 'desativado'}")
    server_state = "continuará ligado" if settings.keep_llm_running else "encerrará com o último chat"
    print(f"  Ao fechar o chat: o servidor {server_state}")
    message_state = "continuar no chat" if settings.message_mode is MessageMode.INTERACTIVE else "responder e sair"
    print(f"  Mensagem no comando: {message_state}")
    print(f"  Ciclos máximos de tools: {settings.max_tool_rounds}")
    print(f"  Timeout total ativo: {settings.interaction_timeout_seconds} segundos")
    print(f"  Timeout por chamada ao LLM: {settings.llm_request_timeout_seconds} segundos")
    print(f"  Reasoning padrão: nível {settings.default_reasoning_level}")
    print(f"  Painel de atividade: {settings.display_log_level.value}")
    size = "sem limite" if settings.log_max_size_mb <= 0 else f"{settings.log_max_size_mb} MB"
    retention = "sem limite" if settings.log_retention_days <= 0 else f"{settings.log_retention_days} dias"
    print(f"  Logs de conversa: tamanho {size}; retenção {retention}")
    if any(settings.permissions.get(risk) is Decision.ALLOW for risk in (Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)):
        print("  AVISO: existem ações sensíveis liberadas sem confirmação.")


def run_wizard() -> ConfigurationResult | None:
    persona = project_root() / "Persona.md"
    context = project_root() / "Context.md"
    if not persona.is_file():
        persona.write_bytes(default_persona_path().read_bytes())
    if not context.is_file():
        context.write_bytes(default_context_path().read_bytes())
    persisted_config = load_config(allow_legacy=True)
    persisted = persisted_config.settings
    if persisted.model_path is None:
        legacy = _legacy_model()
        if legacy:
            persisted = persisted.model_copy(
                update={"model_directory": legacy.parent, "model_path": legacy}
            )
    draft = persisted
    reset_default = False
    reset_context = False
    command_replacement: CommandReplacement | None = None
    if draft.model_path is None:
        print("\nVamos começar escolhendo o modelo local. Depois você poderá revisar o restante com calma.")
        model_directory, model_path = _choose_model(draft)
        draft = draft.model_copy(update={"model_directory": model_directory, "model_path": model_path})
    while True:
        print("\n=== Jarvis · Configuração ===")
        print(f"Modelo: {draft.model_path.name if draft.model_path else 'não selecionado'}")
        print(f"Reasoning: nível {draft.default_reasoning_level} · Painel: {draft.display_log_level.value}")
        print("\n  1) Modelo")
        print("  2) Identidade")
        print("  3) Comportamento e timeouts")
        print("  4) Permissões")
        print("  5) Logs e painel")
        print("  6) Persona e contexto")
        print("  7) Revisar e salvar")
        print("  8) Sair sem salvar")
        choice = ask_choice("Escolha uma seção", [str(index) for index in range(1, 9)], 7)
        if choice == 1:
            directory, model = _choose_model(draft)
            draft = draft.model_copy(update={"model_directory": directory, "model_path": model})
        elif choice == 2:
            name, command, command_replacement = _choose_identity(draft)
            draft = draft.model_copy(update={"assistant_name": name, "command_name": command})
        elif choice == 3:
            autostart = ask_yes_no("Iniciar o servidor junto com o usuário?", draft.autostart)
            keep_running = ask_yes_no("Manter o modelo pronto após fechar o chat?", draft.keep_llm_running)
            interactive = ask_yes_no(
                "Continuar no chat após uma mensagem passada no comando?",
                draft.message_mode is MessageMode.INTERACTIVE,
            )
            rounds = ask_positive_integer("Máximo de ciclos de tools", draft.max_tool_rounds)
            total_timeout = ask_positive_integer(
                "Timeout total de processamento ativo em segundos", draft.interaction_timeout_seconds
            )
            llm_timeout = ask_positive_integer(
                "Timeout de cada chamada ao LLM em segundos", draft.llm_request_timeout_seconds
            )
            reasoning = ask_choice(
                "Reasoning padrão: 1) Off  2) Low  3) Medium  4) High  5) Max",
                ["Off", "Low", "Medium", "High", "Max"],
                draft.default_reasoning_level + 1,
            ) - 1
            draft = draft.model_copy(update={
                "autostart": autostart,
                "keep_llm_running": keep_running,
                "message_mode": MessageMode.INTERACTIVE if interactive else MessageMode.ONE_SHOT,
                "max_tool_rounds": rounds,
                "interaction_timeout_seconds": total_timeout,
                "llm_request_timeout_seconds": llm_timeout,
                "default_reasoning_level": reasoning,
            })
        elif choice == 4:
            draft = draft.model_copy(update={"permissions": _choose_permissions(draft)})
        elif choice == 5:
            levels = list(DisplayLogLevel)
            print("\nNíveis do painel:")
            for index, level in enumerate(levels, 1):
                print(f"  {index}) {level.value}")
            default_level = levels.index(draft.display_log_level) + 1
            level = levels[ask_choice("Nível", [item.value for item in levels], default_level) - 1]
            size = ask_integer("Tamanho máximo dos logs em MB (<= 0 sem limite)", draft.log_max_size_mb)
            retention = ask_integer("Retenção dos logs em dias (<= 0 sem limite)", draft.log_retention_days)
            draft = draft.model_copy(update={
                "display_log_level": level,
                "log_max_size_mb": size,
                "log_retention_days": retention,
            })
        elif choice == 6:
            print(f"\nPersona: {persona}")
            if not _persona_is_default(persona):
                reset_default = ask_yes_no("Restaurar a personalidade padrão ao salvar?", reset_default)
            print(f"Contexto: {context}")
            if not _context_is_default(context):
                reset_context = ask_yes_no("Restaurar o contexto padrão ao salvar?", reset_context)
        elif choice == 7:
            _summary(draft, reset_default, reset_context)
            if ask_yes_no("Salvar esta configuração?", True):
                return ConfigurationResult(
                    persisted_config.model_copy(update={"settings": draft}),
                    persisted.command_name,
                    reset_default,
                    reset_context,
                    command_replacement,
                )
            print("Tudo bem; nenhuma alteração foi salva ainda.")
        else:
            print("Nenhuma alteração foi salva.")
            return None


def _write_runtime(config: JarvisConfig) -> None:
    settings = config.settings
    runtime = project_root() / ".runtime"
    content = "\n".join(
        (
            f"MODEL_PATH={shlex.quote(str(settings.model_path))}",
            f"MODEL_ALIAS={shlex.quote(config.advanced.llm_model)}",
            f"COMMAND_NAME={shlex.quote(settings.command_name)}",
            f"ASSISTANT_NAME={shlex.quote(settings.assistant_name)}",
            f"AUTOSTART={'true' if settings.autostart else 'false'}",
            f"KEEP_LLM_RUNNING={'true' if settings.keep_llm_running else 'false'}",
            f"MESSAGE_MODE={shlex.quote(settings.message_mode.value)}",
            f"DISPLAY_LOG_LEVEL={shlex.quote(settings.display_log_level.value)}",
        )
    ) + "\n"
    temporary = runtime.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(runtime)


def _apply_command(
    previous: str,
    current: str,
    approved_replacement: CommandReplacement | None = None,
) -> None:
    local_bin = Path.home() / ".local/bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    launcher = _launcher_path()
    new_command = local_bin / current
    replacement = _validate_command_collision(current, approved_replacement)
    if replacement is not None:
        replacement.path.unlink()
        replacement.path.symlink_to(launcher)
    elif not new_command.is_symlink():
        new_command.symlink_to(launcher)
    if previous != current:
        old_command = local_bin / previous
        if old_command.is_symlink() and old_command.resolve(strict=False) == launcher:
            old_command.unlink()


def _desktop_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ").replace("\r", " ")


def _apply_desktop_entry(settings: UserSettings) -> None:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")).expanduser()
    icon_source = project_root() / "jarvis/ui/Icon.png"
    icon_target = data_home / "icons/jarvis-local.png"
    applications = data_home / "applications"
    desktop_file = applications / "jarvis-local.desktop"
    icon_target.parent.mkdir(parents=True, exist_ok=True)
    applications.mkdir(parents=True, exist_ok=True)
    icon_target.write_bytes(icon_source.read_bytes())
    command = Path.home() / ".local/bin" / settings.command_name
    content = "\n".join(
        (
            "[Desktop Entry]",
            "Type=Application",
            f"Name={_desktop_value(settings.assistant_name)}",
            "Comment=Local AI assistant",
            f'Exec="{_desktop_value(str(command))}"',
            f"Icon={_desktop_value(str(icon_target))}",
            "Terminal=true",
            "Categories=Utility;",
            "StartupNotify=false",
            "",
        )
    )
    temporary = desktop_file.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o644)
    temporary.replace(desktop_file)


def commit(result: ConfigurationResult) -> None:
    _validate_command_collision(result.settings.command_name, result.command_replacement)
    old = load_config(allow_legacy=True).settings
    if result.reset_persona:
        result.settings.persona_path.write_bytes(default_persona_path().read_bytes())
    if result.reset_context:
        (project_root() / "Context.md").write_bytes(default_context_path().read_bytes())
    save_config(result.config)
    _write_runtime(result.config)
    _apply_command(
        result.previous_command,
        result.settings.command_name,
        result.command_replacement,
    )
    _apply_desktop_entry(result.settings)
    if old.model_path != result.settings.model_path:
        marker = Path.home() / ".local/state/jarvis/restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()


def main() -> None:
    try:
        result = run_wizard()
        if result is None:
            return
        commit(result)
    except ConfigFileError as error:
        print(error)
        raise SystemExit(1) from error
    print(f"\nConfiguração salva em {config_path()}.")
    print(f"Use: {result.settings.command_name}")


if __name__ == "__main__":
    main()
