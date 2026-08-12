"""Typed profile-domain errors with safe, localization-ready projections."""

from __future__ import annotations

from jarvis.foundation.errors import JarvisError


class ProfileError(JarvisError):
    """Root error for profile identity and configuration operations."""

    default_code = "profile.operation_failed"
    default_message_key = "error.profile.operation_failed"


class ProfileNotFoundError(ProfileError):
    default_code = "profile.not_found"
    default_message_key = "error.profile.not_found"


class InvalidProfileNameError(ProfileError):
    default_code = "profile.invalid_name"
    default_message_key = "error.profile.invalid_name"


class ProfileNameConflictError(ProfileError):
    default_code = "profile.name_conflict"
    default_message_key = "error.profile.name_conflict"


class ProtectedProfileError(ProfileError):
    default_code = "profile.protected"
    default_message_key = "error.profile.protected"


class ProfileInvariantError(ProfileError):
    default_code = "profile.invariant_violation"
    default_message_key = "error.profile.invariant_violation"


class ConcurrentProfileModificationError(ProfileError):
    default_code = "profile.concurrent_modification"
    default_message_key = "error.profile.concurrent_modification"


class ProfileConfigurationError(ProfileError):
    default_code = "profile.configuration_invalid"
    default_message_key = "error.profile.configuration_invalid"


class ConfirmationRequiredError(ProfileError):
    default_code = "profile.confirmation_required"
    default_message_key = "error.profile.confirmation_required"


class ConfirmationInvalidError(ProfileError):
    default_code = "profile.confirmation_invalid"
    default_message_key = "error.profile.confirmation_invalid"


class ConfirmationExpiredError(ProfileError):
    default_code = "profile.confirmation_expired"
    default_message_key = "error.profile.confirmation_expired"


class ConfirmationStaleError(ProfileError):
    default_code = "profile.confirmation_stale"
    default_message_key = "error.profile.confirmation_stale"


class DatabaseBusyError(ProfileError):
    default_code = "database.busy"
    default_message_key = "error.database.busy"
