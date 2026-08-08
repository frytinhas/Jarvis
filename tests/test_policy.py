from jarvis.security.policy import Decision, PolicyEngine, Risk


def test_default_policy() -> None:
    policy = PolicyEngine()
    assert policy.decide(Risk.READ) is Decision.ALLOW
    assert policy.decide(Risk.CREATE) is Decision.CONFIRM
    assert policy.decide(Risk.MODIFY) is Decision.CONFIRM
    assert policy.decide(Risk.DELETE) is Decision.CONFIRM
    assert policy.decide(Risk.EXECUTE) is Decision.CONFIRM
    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY

