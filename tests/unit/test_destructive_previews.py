from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from jarvis.profiles.destructive import (
    ConfirmDestructiveOperation,
    DeletionScope,
    DestructiveOperationKind,
    DestructivePreview,
    DestructivePreviewItem,
    DestructiveTarget,
    OperationId,
    ResetScope,
)
from jarvis.profiles.errors import ConfirmationInvalidError
from jarvis.profiles.models import ProfileId

pytestmark = pytest.mark.unit


def test_closed_operation_scope_matrix_rejects_mismatches() -> None:
    assert DestructiveTarget(DestructiveOperationKind.DELETE_PROFILE, DeletionScope.WHOLE_PROFILE)
    assert DestructiveTarget(DestructiveOperationKind.RESET_CONFIGURATION, ResetScope.PERSONA)
    with pytest.raises(ConfirmationInvalidError):
        DestructiveTarget(DestructiveOperationKind.DELETE_PROFILE, ResetScope.PERSONA)
    with pytest.raises(ConfirmationInvalidError):
        DestructiveTarget(DestructiveOperationKind.RESET_CONFIGURATION, DeletionScope.WHOLE_PROFILE)


@pytest.mark.parametrize(
    "parse",
    [
        lambda: DestructiveOperationKind.parse("arbitrary"),
        lambda: ResetScope.parse("arbitrary"),
        lambda: DeletionScope.parse("arbitrary"),
    ],
)
def test_unknown_persisted_values_fail_through_typed_parsers(
    parse: Callable[[], object],
) -> None:
    with pytest.raises(ConfirmationInvalidError):
        parse()


def test_raw_confirmation_tokens_are_excluded_from_representations() -> None:
    operation_id = OperationId(UUID("20000000-0000-4000-8000-000000000001"))
    profile_id = ProfileId(UUID("10000000-0000-4000-8000-000000000001"))
    target = DestructiveTarget(DestructiveOperationKind.RESET_CONFIGURATION, ResetScope.PERSONA)
    now = datetime(2026, 8, 11, 12, tzinfo=UTC)
    raw = "synthetic-raw-confirmation-token"
    preview = DestructivePreview(
        operation_id,
        target,
        profile_id,
        1,
        1,
        now,
        now + timedelta(minutes=5),
        2,
        (DestructivePreviewItem("persona", "restore-default", 1, 1, True),),
        True,
        raw,
    )
    confirmation = ConfirmDestructiveOperation(operation_id, target, profile_id, raw)
    assert raw not in repr(preview)
    assert raw not in repr(confirmation)
    assert preview.confirmation_token == raw
