"""The settings service's orchestration (DESIGN §5.1), against a fake repository (§9)."""

from datetime import UTC, datetime

from app.settings.models import Settings
from app.settings.service import SettingsService

STAMP = datetime(2026, 1, 1, tzinfo=UTC)


class FakeRepository:
    """In-memory ``SettingsRepositoryProtocol`` implementation."""

    def __init__(self, rewatch_share: int | None = None) -> None:
        self.row = Settings(id=1, rewatch_share=rewatch_share, updated_at=STAMP)
        self.commits = 0

    def get(self) -> Settings:
        return self.row

    def update(self, rewatch_share: int | None) -> Settings:
        self.row.rewatch_share = rewatch_share
        return self.row

    def commit(self) -> None:
        self.commits += 1


def test_get_returns_the_stored_row() -> None:
    repository = FakeRepository(rewatch_share=30)

    assert SettingsService(repository).get().rewatch_share == 30


def test_update_replaces_the_stored_value() -> None:
    repository = FakeRepository(rewatch_share=30)

    result = SettingsService(repository).update(50)

    assert result.rewatch_share == 50
    assert repository.row.rewatch_share == 50


def test_update_turns_the_share_off() -> None:
    repository = FakeRepository(rewatch_share=30)

    assert SettingsService(repository).update(None).rewatch_share is None


def test_update_commits_exactly_once() -> None:
    repository = FakeRepository()

    SettingsService(repository).update(20)

    assert repository.commits == 1
