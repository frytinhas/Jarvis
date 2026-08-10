from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


READ_TOOLS = frozenset({"read_file", "file_info", "list_directory", "search_files"})
WRITE_TOOLS = frozenset({
    "create_file", "create_directory", "write_file", "append_file", "move_file",
    "rename_file", "delete_file", "delete_directory", *READ_TOOLS,
})
EXECUTE_TOOLS = frozenset({"execute_file", *READ_TOOLS})
APPLICATION_TOOLS = frozenset({"launch_application"})


@dataclass(frozen=True)
class ToolRoute:
    tool_names: frozenset[str] | None = None
    require_tool: bool = False
    execution_authorized: bool = False
    label: str = ""


def route_user_request(text: str, previous: ToolRoute | None = None) -> ToolRoute:
    normalized = _normalize(text)
    if _requests_broad_root_search(normalized):
        return ToolRoute(frozenset(), True, label="broad_filesystem_search")
    if _matches_system_info(normalized):
        return ToolRoute(frozenset({"get_system_info"}), True, label="system_info")
    if re.search(r"\b(processos?|processes|process list)\b", normalized):
        return ToolRoute(frozenset({"get_processes"}), True, label="processes")
    if re.search(r"\b(onde estou|diretorio atual|pasta atual|current directory|current folder)\b", normalized):
        return ToolRoute(frozenset({"get_current_directory"}), True, label="current_directory")

    application_action = bool(re.search(
        r"\b(abre|abra|abrir|open|va no|inicie|iniciar|launch|start|toca|toque)\b",
        normalized,
    ))
    if application_action and not _has_concrete_target(normalized):
        return ToolRoute(APPLICATION_TOOLS, require_tool=True, execution_authorized=True, label="application")

    execute = bool(re.search(
        r"\b(executa|execute|executar|rode|roda|rodar|run|abre|abra|abrir|open|inicie|iniciar|launch|start)\b",
        normalized,
    ))
    if execute:
        return ToolRoute(
            EXECUTE_TOOLS,
            require_tool=_has_concrete_target(normalized),
            execution_authorized=True,
            label="execute",
        )

    mutable = bool(re.search(
        r"\b(crie|criar|escreva|escrever|altere|alterar|modifique|mova|mover|renomeie|"
        r"renomear|apague|apagar|delete|create|write|modify|move|rename)\b",
        normalized,
    ))
    if mutable:
        return ToolRoute(WRITE_TOOLS, _has_concrete_target(normalized), label="filesystem_change")

    read = bool(re.search(
        r"\b(leia|le|ler|lista|liste|listar|procura|procure|procurar|busca|busque|buscar|"
        r"encontra|encontre|encontrar|inspeciona|inspecione|inspecionar|verifica|verifique|"
        r"verificar|analisa|analise|analisar|resume|resuma|resumir|examina|examine|examinar|"
        r"read|list|search|find|inspect|analyze|summarize|examine)\b",
        normalized,
    ))
    if read:
        contextual_follow_up = (
            previous is not None
            and previous.label == "filesystem_read"
            and not _is_educational_read(normalized)
        )
        require_tool = (
            _has_concrete_target(normalized)
            or _requests_local_read_action(normalized)
            or contextual_follow_up
        )
        return ToolRoute(READ_TOOLS, require_tool, label="filesystem_read")
    return ToolRoute()


def _matches_system_info(text: str) -> bool:
    subject = bool(re.search(
        r"\b(meu|minha|meus|minhas|deste|desse|este|essa|local|pc|computador|maquina|sistema)\b",
        text,
    ))
    detail = bool(re.search(
        r"\b(specs?|especificacoes?|hardware|cpu|processador|ram|memoria|gpu|"
        r"placa de video|kernel|sistema operacional|operating system)\b",
        text,
    ))
    return subject and detail


def _has_concrete_target(text: str) -> bool:
    if re.search(r"(?:^|\s)(?:~|/|\./|\.\./)[^\s]*", text):
        return True
    if re.search(r"\b[\w.-]+\.(?:sh|appimage|bin|run|py|txt|md|json|xml|log|conf|cfg)\b", text):
        return True
    if re.search(r"[\"'][^\"']{2,}[\"']", text):
        return True
    if re.search(
        r"\b(?:minha|meu|suas?|seus?|the)\s+(?:pasta|diretorio|folder|directory)\s+"
        r"(?:documentos|documents|downloads|imagens|pictures|musica|music|videos?|desktop|area de trabalho)\b",
        text,
    ):
        return True
    if re.search(
        r"\b(?:documentos|documents|downloads|imagens|pictures|musica|music|videos?|desktop)\b",
        text,
    ):
        return True
    return bool(re.search(
        r"\b(?:arquivo|script|binario|executavel|file|folder|directory)\s+"
        r"(?:chamado|chamada|named)\s+[\w.-]+",
        text,
    ))


def _requests_broad_root_search(text: str) -> bool:
    searching = bool(re.search(r"\b(liste|listar|procure|procurar|busque|buscar|encontre|find|search|list)\b", text))
    broad_path = bool(re.search(r"(?:^|\s)(?:/|/home)(?:\s|$)", text))
    return searching and broad_path


def _requests_local_read_action(text: str) -> bool:
    if _is_educational_read(text):
        return False
    action = bool(re.search(
        r"(?:^|[.!?,;:]\s*|\b(?:pode|por favor|favor|quero|preciso|please|can you)\s+)"
        r"(?:leia|le|lista|liste|procura|procure|busca|busque|encontra|encontre|"
        r"inspeciona|inspecione|verifica|verifique|analisa|analise|resume|resuma|examina|examine|"
        r"read|list|search|find|inspect|analyze|summarize|examine)\b",
        text,
    ))
    local_subject = bool(re.search(
        r"\b(arquivos?|files?|pastas?|folders?|diretorios?|directories|documentos|documents|"
        r"downloads|projetos?|projects?|scripts?|logs?|conteudo da pasta|folder contents)\b",
        text,
    ))
    return action and local_subject


def _is_educational_read(text: str) -> bool:
    return bool(re.search(
        r"\b(como|how to|qual comando|what command|exemplo|example)\b",
        text,
    ))


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
