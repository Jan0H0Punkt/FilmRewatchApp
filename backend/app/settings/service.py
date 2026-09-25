"""Business-logic layer for the settings module (DESIGN §5.1, FR-RW-08).

Thin on purpose: the range/step rule is already enforced by the Pydantic
schema at the API boundary (§5.3), so nothing repeats it here. This layer
exists for the repository seam (:class:`SettingsRepositoryProtocol`), which
makes it unit-testable against a fake (§9).
"""

from typing import Protocol

from app.settings.models import Settings


class SettingsRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1)."""

    def get(self) -> Settings: ...

    def update(self, rewatch_share: int | None) -> Settings: ...

    def commit(self) -> None: ...


class SettingsService:
    """Reads and replaces the single settings row (FR-RW-08)."""

    def __init__(self, repository: SettingsRepositoryProtocol) -> None:
        self._repository = repository

    def get(self) -> Settings:
        """The stored settings row."""
        return self._repository.get()

    def update(self, rewatch_share: int | None) -> Settings:
        """Replace ``rewatch_share`` and return the stored state (FR-RW-08)."""
        row = self._repository.update(rewatch_share)
        self._repository.commit()
        return row
