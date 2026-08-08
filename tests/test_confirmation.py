from datetime import datetime, timedelta, timezone

import pytest

from jarvis.security.confirmation import ConfirmationError, ConfirmationManager


def test_confirmation_is_bound_to_exact_action() -> None:
    manager = ConfirmationManager()
    action_a = manager.create("write_file", {"path": "/tmp/a", "content": "a"})
    action_b = manager.create("write_file", {"path": "/tmp/b", "content": "b"})

    confirmed = manager.consume(
        action_a.id, expected_tool="write_file", expected_arguments={"path": "/tmp/a", "content": "a"}
    )
    assert confirmed.id == action_a.id
    assert manager.consume(action_b.id).id == action_b.id


def test_changed_arguments_invalidate_confirmation() -> None:
    manager = ConfirmationManager()
    action = manager.create("delete_file", {"path": "/tmp/a"})
    with pytest.raises(ConfirmationError, match="alterados"):
        manager.consume(action.id, expected_arguments={"path": "/tmp/b"})
    with pytest.raises(ConfirmationError, match="inexistente"):
        manager.consume(action.id)


def test_expired_confirmation_fails() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock_value = [now]
    manager = ConfirmationManager(timeout_seconds=10, clock=lambda: clock_value[0])
    action = manager.create("delete_file", {"path": "/tmp/a"})
    clock_value[0] = now + timedelta(seconds=10)
    with pytest.raises(ConfirmationError, match="expirada"):
        manager.consume(action.id)

