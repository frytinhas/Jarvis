from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex

from jarvis.agent.prompts import default_context_path, default_persona_path
from jarvis.config import ConfigFileError, JarvisConfig, config_path, load_config, save_config
from jarvis.hardware import recommended_context_size
from jarvis.legal import schedule_license_notice
from jarvis.resources import ensure_private_resources
from jarvis.security.policy import Decision, Risk
from jarvis.settings import ColorMode, DisplayLogLevel, MessageMode, UserSettings, project_root, runtime_path
from jarvis.ui.selector import select_option, supports_arrow_selection


CATEGORIES = (Risk.READ, Risk.CREATE, Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)
CATEGORY_LABELS = {
    Risk.READ: "Leitura e consulta",
    Risk.CREATE: "Criação de arquivos e diretórios",
    Risk.MODIFY: "Alteração, movimentação e renomeação",
    Risk.DELETE: "Exclusão",
    Risk.EXECUTE: "Execução de scripts e binários por path",
}
COMMAND_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
REASONING_LABELS = ("Off", "Low", "Medium", "High", "Max")
MENU_OPTIONS = (
    "Modelo, contexto e reasoning",
    "Identidade",
    "Comportamento",
    "Timeouts",
    "Permissões",
    "Logs e painel",
    "Aparência",
    "Persona e contexto",
    "Salvar e sair",
    "Sair sem salvar",
)


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
    if supports_arrow_selection():
        default_choice = 1 if default else 2
        return select_option(prompt, ("Sim", "Não"), default_choice) == 1
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
    if supports_arrow_selection():
        return select_option(prompt, choices, default)
    print(f"\n{prompt}:")
    for index, label in enumerate(choices, 1):
        print(f"  {index}) {label}")
    while True:
        raw = input(f"Escolha [{default}]: ").strip()
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
        default_index = 1
        labels: list[str] = []
        for index, model in enumerate(models, 1):
            if current.model_path and model == current.model_path:
                default_index = index
            size_gib = model.stat().st_size / (1024**3)
            labels.append(f"{model.name} ({size_gib:.1f} GiB)")
        choice = ask_choice("Modelos encontrados", labels, default_index)
        return directory, models[choice - 1]


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
    # The administrative installation is exposed through /usr/local/bin.  It must
    # not own, replace, or reject a root-local launcher left by an older release.
    if os.geteuid() == 0:
        return None
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


def _full_summary(settings: UserSettings, reset_persona: bool, reset_context: bool) -> None:
    print("\nResumo da configuração")
    print(f"  Pasta de modelos: {settings.model_directory}")
    print(f"  Modelo: {settings.model_path}")
    print(f"  Contexto do modelo: {settings.context_size} tokens")
    print(
        "  Reasoning padrão: "
        f"{REASONING_LABELS[settings.default_reasoning_level]} "
        f"(nível {settings.default_reasoning_level})"
    )
    print("  Permissões:")
    for risk in CATEGORIES:
        print(f"    {risk}: {settings.permissions.get(risk, Decision.DENY)}")
    persona_status = "será restaurada" if reset_persona else "mantida"
    print(f"  Persona: {settings.persona_path} ({persona_status})")
    context_status = "será restaurado" if reset_context else "mantido"
    print(f"  Contexto: {settings.context_path} ({context_status})")
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
    print(f"  Painel de atividade: {settings.display_log_level.value}")
    print(f"  Cores do terminal: {_color_mode_label(settings.color_mode)}")
    size = "sem limite" if settings.log_max_size_mb <= 0 else f"{settings.log_max_size_mb} MB"
    retention = "sem limite" if settings.log_retention_days <= 0 else f"{settings.log_retention_days} dias"
    print(f"  Logs de conversa: tamanho {size}; retenção {retention}")
    print(f"  Notas de perfil para IA: limite {settings.notes_max_size_mb} MB")
    if any(settings.permissions.get(risk) is Decision.ALLOW for risk in (Risk.MODIFY, Risk.DELETE, Risk.EXECUTE)):
        print("  AVISO: existem ações sensíveis liberadas sem confirmação.")


def _boolean_label(value: bool) -> str:
    return "ativado" if value else "desativado"


def _reasoning_label(value: int) -> str:
    return f"{REASONING_LABELS[value]} (nível {value})"


def _message_mode_label(value: MessageMode) -> str:
    return "continuar no chat" if value is MessageMode.INTERACTIVE else "responder e sair"


def _log_size_label(value: int) -> str:
    return "sem limite" if value <= 0 else f"{value} MB"


def _retention_label(value: int) -> str:
    return "sem limite" if value <= 0 else f"{value} dias"


def _color_mode_label(value: ColorMode) -> str:
    return {
        ColorMode.AUTO: "automático",
        ColorMode.ALWAYS: "sempre ligado",
        ColorMode.NEVER: "desligado",
    }[value]


def _print_change(label: str, previous: object, current: object) -> None:
    print(f"  {label}: {previous} → {current}")


def _changes_summary(
    previous: UserSettings,
    current: UserSettings,
    reset_persona: bool,
    reset_context: bool,
    command_replacement: CommandReplacement | None,
) -> bool:
    print("\nAlterações da configuração")
    changed = False
    fields: tuple[tuple[str, str, object], ...] = (
        ("Pasta de modelos", "model_directory", str),
        ("Modelo", "model_path", str),
        ("Contexto do modelo", "context_size", lambda value: f"{value} tokens"),
        ("Reasoning padrão", "default_reasoning_level", _reasoning_label),
        ("Nome", "assistant_name", str),
        ("Comando", "command_name", str),
        ("Início automático", "autostart", _boolean_label),
        ("Manter modelo ativo", "keep_llm_running", _boolean_label),
        ("Modo da mensagem inicial", "message_mode", _message_mode_label),
        ("Ciclos máximos de tools", "max_tool_rounds", str),
        ("Timeout total", "interaction_timeout_seconds", lambda value: f"{value} segundos"),
        ("Timeout do LLM", "llm_request_timeout_seconds", lambda value: f"{value} segundos"),
        ("Painel de atividade", "display_log_level", lambda value: value.value),
        ("Cores", "color_mode", _color_mode_label),
        ("Limite dos logs", "log_max_size_mb", _log_size_label),
        ("Retenção dos logs", "log_retention_days", _retention_label),
        ("Limite das notas de perfil", "notes_max_size_mb", lambda value: f"{value} MB"),
    )
    for label, attribute, formatter in fields:
        old_value = getattr(previous, attribute)
        new_value = getattr(current, attribute)
        if old_value != new_value:
            _print_change(label, formatter(old_value), formatter(new_value))
            changed = True
    for risk in CATEGORIES:
        old_decision = previous.permissions.get(risk, Decision.DENY)
        new_decision = current.permissions.get(risk, Decision.DENY)
        if old_decision != new_decision:
            _print_change(f"Permissão {risk.value}", old_decision.value, new_decision.value)
            changed = True
    if reset_persona:
        _print_change("Persona", "personalizada", "padrão restaurada")
        changed = True
    if reset_context:
        _print_change("Contexto", "personalizado", "padrão restaurado")
        changed = True
    if command_replacement is not None:
        _print_change(
            "Launcher",
            command_replacement.link_target,
            str(_launcher_path()),
        )
        changed = True
    if not changed:
        print("  Nenhuma configuração foi modificada.")
    return changed


def run_wizard(*, full_summary: bool = False) -> ConfigurationResult | None:
    persisted_config = load_config(allow_legacy=True)
    persisted = persisted_config.settings
    template_profiles = dict(persisted_config.advanced.model_template_thinking)
    ensure_private_resources(persisted)
    persona = persisted.persona_path
    context = persisted.context_path
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
        template_profiles.setdefault(str(model_path.resolve(strict=False)), False)
    while True:
        print("\n=== Jarvis · Configuração ===")
        print(f"Modelo: {draft.model_path.name if draft.model_path else 'não selecionado'}")
        print(
            f"Contexto: {draft.context_size} tokens · Reasoning: nível "
            f"{draft.default_reasoning_level} · Painel: {draft.display_log_level.value}"
        )
        choice = ask_choice("Categorias", list(MENU_OPTIONS), 9)
        if choice == 1:
            directory, model = _choose_model(draft)
            recommended_context = recommended_context_size()
            context_size = ask_positive_integer(
                "Contexto do modelo em tokens (múltiplo de 1024)", recommended_context
            )
            while context_size % 1024:
                print("O contexto deve ser múltiplo de 1024.")
                context_size = ask_positive_integer(
                    "Contexto do modelo em tokens (múltiplo de 1024)", recommended_context
                )
            reasoning = ask_choice(
                "Reasoning padrão",
                list(REASONING_LABELS),
                draft.default_reasoning_level + 1,
            ) - 1
            model_key = str(model.resolve(strict=False))
            template_profiles[model_key] = ask_yes_no(
                "Permitir thinking no template deste modelo?", template_profiles.get(model_key, False)
            )
            draft = draft.model_copy(update={
                "model_directory": directory,
                "model_path": model,
                "context_size": context_size,
                "default_reasoning_level": reasoning,
            })
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
            draft = draft.model_copy(update={
                "autostart": autostart,
                "keep_llm_running": keep_running,
                "message_mode": MessageMode.INTERACTIVE if interactive else MessageMode.ONE_SHOT,
                "max_tool_rounds": rounds,
            })
        elif choice == 4:
            total_timeout = ask_positive_integer(
                "Timeout total de processamento ativo em segundos", draft.interaction_timeout_seconds
            )
            llm_timeout = ask_positive_integer(
                "Timeout de cada chamada ao LLM em segundos", draft.llm_request_timeout_seconds
            )
            draft = draft.model_copy(update={
                "interaction_timeout_seconds": total_timeout,
                "llm_request_timeout_seconds": llm_timeout,
            })
        elif choice == 5:
            draft = draft.model_copy(update={"permissions": _choose_permissions(draft)})
        elif choice == 6:
            levels = list(DisplayLogLevel)
            default_level = levels.index(draft.display_log_level) + 1
            level = levels[
                ask_choice("Níveis do painel", [item.value for item in levels], default_level) - 1
            ]
            size = ask_integer("Tamanho máximo dos logs em MB (<= 0 sem limite)", draft.log_max_size_mb)
            retention = ask_integer("Retenção dos logs em dias (<= 0 sem limite)", draft.log_retention_days)
            notes_size = ask_positive_integer(
                "Tamanho máximo das notas de perfil em MB", draft.notes_max_size_mb
            )
            draft = draft.model_copy(update={
                "display_log_level": level,
                "log_max_size_mb": size,
                "log_retention_days": retention,
                "notes_max_size_mb": notes_size,
            })
        elif choice == 7:
            modes = list(ColorMode)
            selected = ask_choice(
                "Cores do terminal",
                ["Automático (TTY e NO_COLOR)", "Sempre ligadas", "Desligadas"],
                modes.index(draft.color_mode) + 1,
            )
            draft = draft.model_copy(update={"color_mode": modes[selected - 1]})
        elif choice == 8:
            print(f"\nPersona: {persona}")
            if not _persona_is_default(persona):
                reset_default = ask_yes_no("Restaurar a personalidade padrão ao salvar?", reset_default)
            print(f"Contexto: {context}")
            if not _context_is_default(context):
                reset_context = ask_yes_no("Restaurar o contexto padrão ao salvar?", reset_context)
        elif choice == 9:
            if full_summary:
                _full_summary(draft, reset_default, reset_context)
            else:
                _changes_summary(
                    persisted,
                    draft,
                    reset_default,
                    reset_context,
                    command_replacement,
                )
            if ask_yes_no("Salvar esta configuração?", True):
                return ConfigurationResult(
                    persisted_config.model_copy(update={
                        "settings": draft,
                        "advanced": persisted_config.advanced.model_copy(
                            update={"model_template_thinking": template_profiles}
                        ),
                    }),
                    persisted.command_name,
                    reset_default,
                    reset_context,
                    command_replacement,
                )
            print("Tudo bem; nenhuma alteração foi salva ainda.")
        elif choice == 10:
            print("Nenhuma alteração foi salva.")
            return None


def _write_runtime(config: JarvisConfig) -> None:
    settings = config.settings
    runtime = runtime_path()
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.parent.chmod(0o700)
    model_key = str(settings.model_path.expanduser().resolve(strict=False)) if settings.model_path else ""
    template_thinking = config.advanced.model_template_thinking.get(model_key, False)
    content = "\n".join(
        (
            f"MODEL_PATH={shlex.quote(str(settings.model_path))}",
            f"CONTEXT_SIZE={settings.context_size}",
            f"MODEL_ALIAS={shlex.quote(config.advanced.llm_model)}",
            f"COMMAND_NAME={shlex.quote(settings.command_name)}",
            f"ASSISTANT_NAME={shlex.quote(settings.assistant_name)}",
            f"AUTOSTART={'true' if settings.autostart else 'false'}",
            f"KEEP_LLM_RUNNING={'true' if settings.keep_llm_running else 'false'}",
            f"MESSAGE_MODE={shlex.quote(settings.message_mode.value)}",
            f"DISPLAY_LOG_LEVEL={shlex.quote(settings.display_log_level.value)}",
            f"TEMPLATE_THINKING={'true' if template_thinking else 'false'}",
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
    if os.geteuid() == 0:
        return
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
        result.settings.context_path.write_bytes(default_context_path().read_bytes())
    ensure_private_resources(result.settings)
    save_config(result.config)
    schedule_license_notice()
    _write_runtime(result.config)
    _apply_command(
        result.previous_command,
        result.settings.command_name,
        result.command_replacement,
    )
    _apply_desktop_entry(result.settings)
    if old.model_path != result.settings.model_path or old.context_size != result.settings.context_size:
        marker = runtime_path().parent / "restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Configuração interativa do Jarvis")
    parser.add_argument("--setup", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    try:
        result = run_wizard(full_summary=options.setup)
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
