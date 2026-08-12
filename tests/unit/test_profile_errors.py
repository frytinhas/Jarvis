from __future__ import annotations

import pytest

from jarvis.profiles.errors import (
    ConfirmationInvalidError,
    DatabaseBusyError,
    InvalidProfileNameError,
    ProfileConfigurationError,
    ProfileError,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ProfileError(), "profile.operation_failed"),
        (InvalidProfileNameError(), "profile.invalid_name"),
        (ProfileConfigurationError(), "profile.configuration_invalid"),
        (ConfirmationInvalidError(), "profile.confirmation_invalid"),
        (DatabaseBusyError(), "database.busy"),
    ],
)
def test_profile_errors_have_stable_safe_codes(error: ProfileError, code: str) -> None:
    assert error.to_safe_dict()["code"] == code


def test_profile_errors_reject_private_safe_details() -> None:
    with pytest.raises(TypeError):
        ConfirmationInvalidError(safe_details={"confirmation_token": "raw"})
