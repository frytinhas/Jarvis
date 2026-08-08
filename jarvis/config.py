from __future__ import annotations

import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jarvis.security.policy import Decision, Risk
from jarvis.settings import ColorMode, DisplayLogLevel, UserSettings, default_settings, project_root


CONFIG_VERSION = 7


class ConfigFileError(ValueError):
    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"Configuração inválida em {path}: {message}")


class AdvancedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "jarvis-model"
    llm_api_key: str = ""
    confirmation_timeout: int = Field(default=30, gt=0)
    audit_db_path: Path = Field(
        default_factory=lambda: Path("~/.local/state/jarvis/audit.db").expanduser()
    )


class JarvisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = CONFIG_VERSION
    settings: UserSettings
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


def config_path() -> Path:
    override = os.environ.get("JARVIS_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return config_home / "jarvis/config.xml"


def default_config() -> JarvisConfig:
    return JarvisConfig(settings=default_settings())


def load_config(path: Path | None = None, *, allow_legacy: bool = False) -> JarvisConfig:
    target = path or config_path()
    if not target.is_file():
        if allow_legacy:
            return _load_legacy_config(target)
        raise ConfigFileError(target, "arquivo ausente; execute jarvis-config")
    try:
        tree = _parse_tree(target)
        return _config_from_root(tree.getroot(), target)
    except ConfigFileError:
        raise
    except (ET.ParseError, OSError, UnicodeError) as error:
        detail = str(error)
        if isinstance(error, ET.ParseError) and hasattr(error, "position"):
            detail = f"XML malformado na linha {error.position[0]}, coluna {error.position[1]}"
        raise ConfigFileError(target, detail) from error


def save_config(config: JarvisConfig, path: Path | None = None) -> None:
    target = path or config_path()
    if config.version != CONFIG_VERSION:
        raise ConfigFileError(target, f"versão {config.version} não suportada")
    if set(config.settings.permissions) != set(Risk):
        raise ConfigFileError(target, "todas as categorias de permissão devem estar presentes")
    if config.settings.permissions[Risk.PRIVILEGED] is not Decision.DENY:
        raise ConfigFileError(target, "PRIVILEGED deve permanecer DENY")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        existing = _parse_tree(target)
        _config_from_root(existing.getroot(), target)
        tree = existing if existing.getroot().attrib.get("version") == str(CONFIG_VERSION) else _new_tree()
    else:
        tree = _new_tree()
    root = tree.getroot()
    root.set("version", str(CONFIG_VERSION))
    _write_values(root, config)
    _config_from_root(root, target)
    ET.indent(tree, space="  ")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(payload + b"\n")
    temporary.chmod(0o600)
    temporary.replace(target)


def _parse_tree(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def _children(parent: ET.Element) -> list[ET.Element]:
    return [child for child in parent if isinstance(child.tag, str)]


def _validate_children(parent: ET.Element, expected: set[str], path: Path) -> None:
    names = [str(child.tag) for child in _children(parent)]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    unknown = sorted(set(names) - expected)
    missing = sorted(expected - set(names))
    if duplicates:
        raise ConfigFileError(path, f"elementos duplicados em <{parent.tag}>: {', '.join(duplicates)}")
    if unknown:
        raise ConfigFileError(path, f"elementos desconhecidos em <{parent.tag}>: {', '.join(unknown)}")
    if missing:
        raise ConfigFileError(path, f"elementos ausentes em <{parent.tag}>: {', '.join(missing)}")


def _section(root: ET.Element, name: str) -> ET.Element:
    section = root.find(name)
    if section is None:
        raise AssertionError(f"seção validada não encontrada: {name}")
    return section


def _text(parent: ET.Element, name: str) -> str:
    element = parent.find(name)
    if element is None:
        raise AssertionError(f"elemento validado não encontrado: {name}")
    return (element.text or "").strip()


def _boolean(value: str, element: str, path: Path) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ConfigFileError(path, f"<{element}> aceita somente true ou false")


def _integer(value: str, element: str, path: Path) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ConfigFileError(path, f"<{element}> deve conter um número inteiro") from error


def _optional_path(value: str) -> Path | None:
    return Path(value).expanduser() if value else None


def _config_from_root(root: ET.Element, path: Path) -> JarvisConfig:
    if root.tag != "jarvis":
        raise ConfigFileError(path, "o elemento raiz deve ser <jarvis>")
    if set(root.attrib) != {"version"}:
        raise ConfigFileError(path, "<jarvis> deve possuir somente o atributo version")
    try:
        version = int(root.attrib["version"])
    except (KeyError, ValueError) as error:
        raise ConfigFileError(path, "atributo version inválido") from error
    if version not in {5, 6, CONFIG_VERSION}:
        raise ConfigFileError(path, f"versão {version} não suportada; esperada 5, 6 ou {CONFIG_VERSION}")

    sections = {"model", "identity", "behavior", "permissions", "llm", "logs", "paths"}
    if version == CONFIG_VERSION:
        sections.add("appearance")
    _validate_children(root, sections, path)
    expected = {
        "model": {"directory", "path"},
        "identity": {"assistant_name", "command_name"},
        "behavior": ({
            "autostart", "keep_llm_running", "message_mode", "request_timeout_seconds"
        } if version == 5 else {
            "autostart", "keep_llm_running", "message_mode", "max_tool_rounds",
            "interaction_timeout_seconds", "llm_request_timeout_seconds",
            "default_reasoning_level",
        }),
        "permissions": {risk.value for risk in Risk},
        "llm": {"base_url", "model", "api_key", "confirmation_timeout"},
        "logs": ({"max_size_mb", "retention_days", "audit_db_path", "level"}
                 if version == 5 else
                 {"max_size_mb", "retention_days", "audit_db_path", "display_level"}),
        "paths": {"persona"},
    }
    if version == CONFIG_VERSION:
        expected["appearance"] = {"color_mode"}
    for name, children in expected.items():
        section = _section(root, name)
        if section.attrib:
            raise ConfigFileError(path, f"<{name}> não aceita atributos")
        _validate_children(section, children, path)
        for child in _children(section):
            if child.attrib or _children(child):
                raise ConfigFileError(path, f"<{child.tag}> deve conter somente texto")

    model = _section(root, "model")
    identity = _section(root, "identity")
    behavior = _section(root, "behavior")
    permissions_element = _section(root, "permissions")
    llm = _section(root, "llm")
    logs = _section(root, "logs")
    paths = _section(root, "paths")
    try:
        assistant_name = _text(identity, "assistant_name")
        command_name = _text(identity, "command_name")
        base_url = _text(llm, "base_url").rstrip("/")
        llm_model = _text(llm, "model")
        persona = _text(paths, "persona")
        if not assistant_name:
            raise ConfigFileError(path, "<assistant_name> não pode ficar vazio")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", command_name):
            raise ConfigFileError(path, "<command_name> possui formato inválido")
        if not base_url or not llm_model:
            raise ConfigFileError(path, "<base_url> e <llm><model> não podem ficar vazios")
        if not persona:
            raise ConfigFileError(path, "<persona> não pode ficar vazio")
        permissions = {
            risk: Decision(_text(permissions_element, risk.value))
            for risk in Risk
        }
        if permissions[Risk.PRIVILEGED] is not Decision.DENY:
            raise ConfigFileError(path, "<PRIVILEGED> deve permanecer DENY")
        legacy_timeout = (
            _integer(_text(behavior, "request_timeout_seconds"), "request_timeout_seconds", path)
            if version == 5 else None
        )
        settings = UserSettings(
            version=CONFIG_VERSION,
            model_directory=_optional_path(_text(model, "directory")),
            model_path=_optional_path(_text(model, "path")),
            permissions=permissions,
            assistant_name=assistant_name,
            command_name=command_name,
            autostart=_boolean(_text(behavior, "autostart"), "autostart", path),
            keep_llm_running=_boolean(
                _text(behavior, "keep_llm_running"), "keep_llm_running", path
            ),
            message_mode=_text(behavior, "message_mode"),
            max_tool_rounds=(128 if version == 5 else _integer(
                _text(behavior, "max_tool_rounds"), "max_tool_rounds", path
            )),
            interaction_timeout_seconds=(max(600, legacy_timeout or 0) if version == 5 else _integer(
                _text(behavior, "interaction_timeout_seconds"), "interaction_timeout_seconds", path
            )),
            llm_request_timeout_seconds=(120 if version == 5 else _integer(
                _text(behavior, "llm_request_timeout_seconds"), "llm_request_timeout_seconds", path
            )),
            default_reasoning_level=(2 if version == 5 else _integer(
                _text(behavior, "default_reasoning_level"), "default_reasoning_level", path
            )),
            display_log_level=(DisplayLogLevel.ESSENTIAL if version == 5 else DisplayLogLevel(
                _text(logs, "display_level")
            )),
            color_mode=(
                ColorMode.AUTO
                if version < CONFIG_VERSION
                else ColorMode(_text(_section(root, "appearance"), "color_mode"))
            ),
            log_max_size_mb=_integer(_text(logs, "max_size_mb"), "max_size_mb", path),
            log_retention_days=_integer(_text(logs, "retention_days"), "retention_days", path),
            persona_path=Path(persona).expanduser(),
        )
        advanced = AdvancedConfig(
            llm_base_url=base_url,
            llm_model=llm_model,
            llm_api_key=_text(llm, "api_key"),
            confirmation_timeout=_integer(
                _text(llm, "confirmation_timeout"), "confirmation_timeout", path
            ),
            audit_db_path=Path(_text(logs, "audit_db_path")).expanduser(),
        )
        return JarvisConfig(version=CONFIG_VERSION, settings=settings, advanced=advanced)
    except ConfigFileError:
        raise
    except (ValidationError, ValueError) as error:
        raise ConfigFileError(path, str(error)) from error


def _comment(parent: ET.Element, pt_br: str, en: str) -> None:
    parent.append(ET.Comment(f" PT-BR: {pt_br} "))
    parent.append(ET.Comment(f" EN: {en} "))


def _new_tree() -> ET.ElementTree:
    root = ET.Element("jarvis", {"version": str(CONFIG_VERSION)})
    definitions = (
        ("model", "Modelo GGUF local selecionado pelo Jarvis.", "Local GGUF model selected by Jarvis.", ("directory", "path")),
        ("identity", "Nome exibido e comando público do assistente.", "Assistant display name and public command.", ("assistant_name", "command_name")),
        ("behavior", "Comportamento, limites e reasoning padrão do assistente.", "Assistant behavior, limits, and default reasoning.", ("autostart", "keep_llm_running", "message_mode", "max_tool_rounds", "interaction_timeout_seconds", "llm_request_timeout_seconds", "default_reasoning_level")),
        ("permissions", "Valores aceitos: ALLOW, CONFIRM ou DENY. PRIVILEGED deve ser DENY.", "Accepted values: ALLOW, CONFIRM, or DENY. PRIVILEGED must be DENY.", tuple(risk.value for risk in Risk)),
        ("llm", "Endpoint, nome do modelo, chave opcional e timeout de confirmação.", "Endpoint, model name, optional key, and confirmation timeout.", ("base_url", "model", "api_key", "confirmation_timeout")),
        ("logs", "Nível visual: Full, Server-Essential, Essential, Minimal-Essential ou None.", "Display level: Full, Server-Essential, Essential, Minimal-Essential, or None.", ("max_size_mb", "retention_days", "audit_db_path", "display_level")),
        ("paths", "Caminhos podem usar ~ e são expandidos pelo Jarvis.", "Paths may use ~ and are expanded by Jarvis.", ("persona",)),
        ("appearance", "Modo de cores: auto, always ou never.", "Color mode: auto, always, or never.", ("color_mode",)),
    )
    for name, pt_br, en, children in definitions:
        _comment(root, pt_br, en)
        section = ET.SubElement(root, name)
        for child in children:
            ET.SubElement(section, child)
    return ET.ElementTree(root)


def _set(parent: ET.Element, name: str, value: object) -> None:
    element = parent.find(name)
    if element is None:
        raise AssertionError(f"elemento não encontrado ao salvar: {name}")
    if isinstance(value, bool):
        element.text = "true" if value else "false"
    elif value is None:
        element.text = ""
    else:
        element.text = str(value)


def _write_values(root: ET.Element, config: JarvisConfig) -> None:
    settings = config.settings
    advanced = config.advanced
    model = _section(root, "model")
    _set(model, "directory", settings.model_directory)
    _set(model, "path", settings.model_path)
    identity = _section(root, "identity")
    _set(identity, "assistant_name", settings.assistant_name)
    _set(identity, "command_name", settings.command_name)
    behavior = _section(root, "behavior")
    _set(behavior, "autostart", settings.autostart)
    _set(behavior, "keep_llm_running", settings.keep_llm_running)
    _set(behavior, "message_mode", settings.message_mode.value)
    _set(behavior, "max_tool_rounds", settings.max_tool_rounds)
    _set(behavior, "interaction_timeout_seconds", settings.interaction_timeout_seconds)
    _set(behavior, "llm_request_timeout_seconds", settings.llm_request_timeout_seconds)
    _set(behavior, "default_reasoning_level", settings.default_reasoning_level)
    permissions = _section(root, "permissions")
    for risk in Risk:
        _set(permissions, risk.value, settings.permissions.get(risk, Decision.DENY).value)
    llm = _section(root, "llm")
    _set(llm, "base_url", advanced.llm_base_url)
    _set(llm, "model", advanced.llm_model)
    _set(llm, "api_key", advanced.llm_api_key)
    _set(llm, "confirmation_timeout", advanced.confirmation_timeout)
    logs = _section(root, "logs")
    _set(logs, "max_size_mb", settings.log_max_size_mb)
    _set(logs, "retention_days", settings.log_retention_days)
    _set(logs, "audit_db_path", advanced.audit_db_path)
    _set(logs, "display_level", settings.display_log_level.value)
    _set(_section(root, "paths"), "persona", settings.persona_path)
    _set(_section(root, "appearance"), "color_mode", settings.color_mode.value)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_legacy_config(target: Path) -> JarvisConfig:
    settings = default_settings()
    legacy_override = os.environ.get("JARVIS_SETTINGS_PATH")
    legacy_settings = (
        Path(legacy_override).expanduser()
        if legacy_override
        else target.parent / "settings.json"
    )
    if legacy_settings.is_file():
        try:
            settings = UserSettings.model_validate_json(legacy_settings.read_text(encoding="utf-8"))
            settings = settings.model_copy(update={"version": CONFIG_VERSION})
        except (OSError, UnicodeError, ValidationError) as error:
            raise ConfigFileError(legacy_settings, str(error)) from error
    env = _read_env_file(project_root() / ".env")
    try:
        advanced = AdvancedConfig(
            llm_base_url=env.get("LLM_BASE_URL", AdvancedConfig.model_fields["llm_base_url"].default),
            llm_model=env.get("LLM_MODEL", AdvancedConfig.model_fields["llm_model"].default),
            llm_api_key=env.get("LLM_API_KEY", ""),
            confirmation_timeout=int(env.get("CONFIRMATION_TIMEOUT", "30")),
            audit_db_path=Path(env.get("AUDIT_DB_PATH", "~/.local/state/jarvis/audit.db")).expanduser(),
        )
    except (ValueError, ValidationError) as error:
        raise ConfigFileError(project_root() / ".env", str(error)) from error
    return JarvisConfig(settings=settings, advanced=advanced)
