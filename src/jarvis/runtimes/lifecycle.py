"""Core-owned coordination for profile-destructive runtime participants."""

from __future__ import annotations

import asyncio

from jarvis.profiles.destructive import (
    ConfirmDestructiveOperation,
    DeleteProfileResult,
    DestructivePreview,
    ResetProfileResult,
    ResetScope,
)
from jarvis.profiles.models import ProfileId
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.runtimes.errors import RuntimePartialCleanupError
from jarvis.runtimes.manager import RuntimeManager


class ProfileRuntimeLifecycleCoordinator:
    """Quiesce the Core-owned runtime before database-owned destructive work."""

    def __init__(
        self,
        profiles: ProfileService,
        profile_configuration: ProfileConfigService,
        runtimes: RuntimeManager,
    ) -> None:
        self._profiles = profiles
        self._profile_configuration = profile_configuration
        self._runtimes = runtimes

    async def preview_reset(
        self, profile_id: ProfileId, scope: ResetScope
    ) -> tuple[DestructivePreview, bool]:
        preview = await asyncio.to_thread(
            self._profile_configuration.preview_reset, profile_id, scope
        )
        return preview, scope is ResetScope.WHOLE_PROFILE and self._runtimes.has_active(profile_id)

    async def confirm_reset(self, command: ConfirmDestructiveOperation) -> ResetProfileResult:
        was_active = command.target.scope is ResetScope.WHOLE_PROFILE and self._runtimes.has_active(
            command.profile_id
        )
        if command.target.scope is ResetScope.WHOLE_PROFILE:
            async with self._runtimes.profile_lifecycle_guard(command.profile_id):
                try:
                    return await asyncio.to_thread(
                        self._profile_configuration.confirm_reset, command
                    )
                except BaseException as error:
                    if was_active:
                        raise RuntimePartialCleanupError() from error
                    raise
        return await asyncio.to_thread(self._profile_configuration.confirm_reset, command)

    async def preview_delete(self, profile_id: ProfileId) -> tuple[DestructivePreview, bool]:
        preview = await asyncio.to_thread(self._profiles.preview_delete, profile_id)
        return preview, self._runtimes.has_active(profile_id)

    async def confirm_delete(self, command: ConfirmDestructiveOperation) -> DeleteProfileResult:
        was_active = self._runtimes.has_active(command.profile_id)
        async with self._runtimes.profile_lifecycle_guard(command.profile_id):
            try:
                return await asyncio.to_thread(self._profiles.confirm_delete, command)
            except BaseException as error:
                if was_active:
                    raise RuntimePartialCleanupError() from error
                raise
