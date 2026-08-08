from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex

from jarvis.agent.prompts import default_context_path, default_persona_path
from jarvis.security.policy import Decision, Risk
from jarvis.settings import MessageMode, UserSettings, load_settings, project_root, save_settings


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
    settings: UserSettings
    previous_command: str
    reset_persona: bool
    reset_context: bool
    command_replacement: CommandReplacement | None = None


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
    print(f"  Tempo máximo por interação: {settings.request_timeout_seconds} segundos")
    size = "sem limite" if settings.log_max_size_mb <= 0 else f"{settings.log_max_size_mb} MB"
    retention = "sem limite" if settings.log_retention_days <= 0 else f"{settings.log_retention_days} dias"
    print(f"  Logs de conversa: tamanho {size}; retenção {retention}")
    if any(settings.permissions.get(risk) is Decision.ALLOW for risk in (Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)):
        print("  AVISO: existem ações sensíveis liberadas sem confirmação.")


def run_wizard() -> ConfigurationResult:
    persona = project_root() / "Persona.md"
    context = project_root() / "Context.md"
    if not persona.is_file():
        persona.write_bytes(default_persona_path().read_bytes())
    if not context.is_file():
        context.write_bytes(default_context_path().read_bytes())
    persisted = load_settings()
    if persisted.model_path is None:
        legacy = _legacy_model()
        if legacy:
            persisted = persisted.model_copy(
                update={"model_directory": legacy.parent, "model_path": legacy}
            )
    draft = persisted
    while True:
        print("\n=== Configuração do Jarvis ===")
        model_directory, model_path = _choose_model(draft)
        permissions = _choose_permissions(draft)
        print(f"\nPersona editável: {persona}")
        print("Edite esse arquivo para personalizar o comportamento do assistente.")
        reset_default = False
        if not _persona_is_default(persona):
            reset_default = ask_yes_no("Restaurar a personalidade padrão?", False)
        print(f"\nContexto editável: {context}")
        print("Edite esse arquivo para ensinar preferências e referências ao assistente.")
        reset_context = False
        if not _context_is_default(context):
            reset_context = ask_yes_no("Restaurar o contexto padrão?", False)
        assistant_name, command_name, command_replacement = _choose_identity(draft)
        autostart = ask_yes_no("Iniciar o servidor automaticamente ao entrar no usuário?", draft.autostart)
        keep_llm_running = ask_yes_no(
            "Manter o servidor da IA ligado depois que o chat for fechado?",
            draft.keep_llm_running,
        )
        continue_after_message = ask_yes_no(
            "Ao chamar o assistente com uma mensagem, continuar no chat após a resposta?",
            draft.message_mode is MessageMode.INTERACTIVE,
        )
        request_timeout_seconds = ask_positive_integer(
            "Tempo máximo de cada interação em segundos",
            draft.request_timeout_seconds,
        )
        log_max_size_mb = ask_integer(
            "Tamanho máximo da pasta de logs em MB (<= 0 significa sem limite)",
            draft.log_max_size_mb,
        )
        log_retention_days = ask_integer(
            "Tempo de retenção dos logs em dias (<= 0 significa sem limite)",
            draft.log_retention_days,
        )
        candidate = UserSettings(
            model_directory=model_directory,
            model_path=model_path,
            permissions=permissions,
            assistant_name=assistant_name,
            command_name=command_name,
            autostart=autostart,
            keep_llm_running=keep_llm_running,
            message_mode=(MessageMode.INTERACTIVE if continue_after_message else MessageMode.ONE_SHOT),
            request_timeout_seconds=request_timeout_seconds,
            log_max_size_mb=log_max_size_mb,
            log_retention_days=log_retention_days,
            persona_path=persona,
        )
        _summary(candidate, reset_default, reset_context)
        if ask_yes_no("Confirmar e salvar essa configuração?", True):
            return ConfigurationResult(
                candidate,
                persisted.command_name,
                reset_default,
                reset_context,
                command_replacement,
            )
        print("Nada foi salvo. O assistente de configuração será reiniciado.")
        draft = candidate


def _write_runtime(settings: UserSettings) -> None:
    runtime = project_root() / ".runtime"
    content = "\n".join(
        (
            f"MODEL_PATH={shlex.quote(str(settings.model_path))}",
            "MODEL_ALIAS=jarvis-model",
            f"COMMAND_NAME={shlex.quote(settings.command_name)}",
            f"ASSISTANT_NAME={shlex.quote(settings.assistant_name)}",
            f"AUTOSTART={'true' if settings.autostart else 'false'}",
            f"KEEP_LLM_RUNNING={'true' if settings.keep_llm_running else 'false'}",
            f"MESSAGE_MODE={shlex.quote(settings.message_mode.value)}",
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
    old = load_settings()
    if result.reset_persona:
        result.settings.persona_path.write_bytes(default_persona_path().read_bytes())
    if result.reset_context:
        (project_root() / "Context.md").write_bytes(default_context_path().read_bytes())
    save_settings(result.settings)
    _write_runtime(result.settings)
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
    result = run_wizard()
    commit(result)
    print(f"\nConfiguração salva. Use: {result.settings.command_name}")


if __name__ == "__main__":
    main()
