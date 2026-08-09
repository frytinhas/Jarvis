from jarvis.agent.tool_routing import route_user_request


def test_specs_require_only_real_system_information() -> None:
    route = route_user_request("quais as specs do meu pc?")

    assert route.require_tool is True
    assert route.tool_names == frozenset({"get_system_info"})
    assert route.label == "system_info"


def test_explicit_script_execution_authorizes_execute_route() -> None:
    route = route_user_request("rode /tmp/check.sh agora")

    assert route.require_tool is True
    assert route.execution_authorized is True
    assert "execute_file" in (route.tool_names or ())


def test_normal_conversation_does_not_authorize_execution() -> None:
    route = route_user_request("o que você acha desse conteúdo?")

    assert route.execution_authorized is False
    assert route.require_tool is False


def test_portuguese_xdg_directory_request_requires_a_real_tool() -> None:
    route = route_user_request("leia a minha pasta documentos e liste todos os diretorios nela")

    assert route.require_tool
    assert "list_directory" in (route.tool_names or set())


def test_contextual_read_instruction_requires_a_real_tool() -> None:
    route = route_user_request("perfeito, lista os arquivos pra mim então, para um teste")

    assert route.require_tool
    assert route.label == "filesystem_read"
    assert "list_directory" in (route.tool_names or set())


def test_educational_read_question_does_not_force_local_access() -> None:
    route = route_user_request("como listar arquivos em Python?")

    assert route.require_tool is False


def test_read_follow_up_reuses_previous_local_route() -> None:
    previous = route_user_request("procure a pasta chamada brain em Documentos")
    route = route_user_request("tudo bem, pode verificar", previous)

    assert previous.require_tool
    assert route.require_tool
    assert route.label == "filesystem_read"
