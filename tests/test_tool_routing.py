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
