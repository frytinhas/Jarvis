from jarvis.security.policy import Decision, PolicyEngine, Risk


def test_default_policy() -> None:
    policy = PolicyEngine()
    assert policy.decide(Risk.READ) is Decision.ALLOW
    assert policy.decide(Risk.CREATE) is Decision.ALLOW
    assert policy.decide(Risk.MODIFY) is Decision.CONFIRM
    assert policy.decide(Risk.DELETE) is Decision.CONFIRM
    assert policy.decide(Risk.EXECUTE) is Decision.ALLOW
    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY


def test_configured_policy_can_disable_or_auto_allow_categories() -> None:
    policy = PolicyEngine({Risk.READ: Decision.DENY, Risk.DELETE: Decision.ALLOW})
    assert policy.decide(Risk.READ) is Decision.DENY
    assert policy.decide(Risk.DELETE) is Decision.ALLOW
    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY


def test_policy_can_update_non_privileged_decision() -> None:
    policy = PolicyEngine()

    policy.set_decision(Risk.EXECUTE, Decision.CONFIRM)

    assert policy.decide(Risk.EXECUTE) is Decision.CONFIRM


def test_policy_rejects_privileged_update() -> None:
    policy = PolicyEngine()

    try:
        policy.set_decision(Risk.PRIVILEGED, Decision.ALLOW)
    except ValueError:
        pass
    else:
        raise AssertionError("PRIVILEGED não pode ser alterado")

    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY
