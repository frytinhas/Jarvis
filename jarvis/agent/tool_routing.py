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


@dataclass(frozen=True)
class ToolRoute:
    tool_names: frozenset[str] | None = None
    require_tool: bool = False
    execution_authorized: bool = False
    label: str = ""


def route_user_request(text: str) -> ToolRoute:
    normalized = _normalize(text)
    if _requests_broad_root_search(normalized):
        return ToolRoute(frozenset(), True, label="broad_filesystem_search")
    if _matches_system_info(normalized):
        return ToolRoute(frozenset({"get_system_info"}), True, label="system_info")
    if re.search(r"\b(processos?|processes|process list)\b", normalized):
        return ToolRoute(frozenset({"get_processes"}), True, label="processes")
    if re.search(r"\b(onde estou|diretorio atual|pasta atual|current directory|current folder)\b", normalized):
        return ToolRoute(frozenset({"get_current_directory"}), True, label="current_directory")

    execute = bool(re.search(
        r"\b(executa|execute|executar|rode|roda|rodar|inicie|iniciar|run|launch|start)\b",
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
        r"\b(leia|ler|liste|listar|procure|procurar|busque|buscar|encontre|encontrar|"
        r"inspecione|verifique|read|list|search|find|inspect)\b",
        normalized,
    ))
    if read:
        return ToolRoute(READ_TOOLS, _has_concrete_target(normalized), label="filesystem_read")
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
    return bool(re.search(
        r"\b(?:arquivo|script|binario|executavel|file|folder|directory)\s+"
        r"(?:chamado|chamada|named)\s+[\w.-]+",
        text,
    ))


def _requests_broad_root_search(text: str) -> bool:
    searching = bool(re.search(r"\b(liste|listar|procure|procurar|busque|buscar|encontre|find|search|list)\b", text))
    broad_path = bool(re.search(r"(?:^|\s)(?:/|/home)(?:\s|$)", text))
    return searching and broad_path


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))
