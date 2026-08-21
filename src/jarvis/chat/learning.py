"""Minimum M006A learning-state service."""

from __future__ import annotations

from jarvis.chat.models import LearningSnapshot, LearningStatus
from jarvis.chat.repository import ConversationRepository
from jarvis.foundation.clock import Clock
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId


class LearningService:
    def __init__(self, repository: ConversationRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def status(self, profile_id: ProfileId, model_id: ModelId) -> LearningSnapshot:
        return self._repository.learning(profile_id, model_id)

    def start(self, profile_id: ProfileId, model_id: ModelId) -> LearningSnapshot:
        return self._repository.set_learning(
            profile_id, model_id, LearningStatus.ACTIVE, self._clock.now()
        )

    def finish(self, profile_id: ProfileId, model_id: ModelId) -> LearningSnapshot:
        return self._repository.set_learning(
            profile_id, model_id, LearningStatus.FINISHED, self._clock.now()
        )
