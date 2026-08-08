from jarvis.security.policy import Decision, PolicyEngine, Risk


def test_default_policy() -> None:
    policy = PolicyEngine()
    assert policy.decide(Risk.READ) is Decision.ALLOW
    assert policy.decide(Risk.CREATE) is Decision.ALLOW
    assert policy.decide(Risk.MODIFY) is Decision.CONFIRM
    assert policy.decide(Risk.DELETE) is Decision.CONFIRM
    assert policy.decide(Risk.EXECUTE) is Decision.CONFIRM
    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY


def test_configured_policy_can_disable_or_auto_allow_categories() -> None:
    policy = PolicyEngine({Risk.READ: Decision.DENY, Risk.DELETE: Decision.ALLOW})
    assert policy.decide(Risk.READ) is Decision.DENY
    assert policy.decide(Risk.DELETE) is Decision.ALLOW
    assert policy.decide(Risk.PRIVILEGED) is Decision.DENY
