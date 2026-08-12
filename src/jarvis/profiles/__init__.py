"""Profile identity and configuration domain."""

from jarvis.profiles.configuration import (
    AppearanceConfiguration,
    ProfileAggregate,
    ProfileConfiguration,
    ProfileConfigurationSectionSnapshot,
    ProfileConfigurationValues,
    SectionRevision,
    UpdateProfileConfiguration,
)
from jarvis.profiles.models import (
    Capability,
    ConfigurationSection,
    CreateProfile,
    PermissionDecision,
    Profile,
    ProfileId,
    ProfileKind,
    RenameProfile,
    VisibleLoggingMode,
)
from jarvis.profiles.names import NormalizedProfileName, normalize_profile_name

__all__ = [
    "AppearanceConfiguration",
    "Capability",
    "ConfigurationSection",
    "CreateProfile",
    "NormalizedProfileName",
    "PermissionDecision",
    "Profile",
    "ProfileConfiguration",
    "ProfileAggregate",
    "ProfileConfigurationValues",
    "ProfileConfigurationSectionSnapshot",
    "ProfileId",
    "ProfileKind",
    "RenameProfile",
    "SectionRevision",
    "UpdateProfileConfiguration",
    "VisibleLoggingMode",
    "normalize_profile_name",
]
