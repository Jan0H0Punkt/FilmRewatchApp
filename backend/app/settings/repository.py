"""Data-access layer for the settings module (DESIGN §5.1).

One row, one read, one write — no business rules, no HTTP. The row is seeded
by migration ``0009_settings``, so :meth:`get` never actually meets a missing
row; ``get_one`` makes that assumption explicit instead of handing the
service an ``Optional`` it would have to narrow.
"""

from sqlalchemy.orm import Session

from app.core.db import utc_now
from app.settings.models import Settings


class SettingsRepository:
    """SQLAlchemy-backed settings data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> Settings:
        """The single settings row, seeded by the migration."""
        return self._session.get_one(Settings, 1)

    def update(self, rewatch_share: int | None) -> Settings:
        """Overwrite the row's value and stamp it (FR-RW-08)."""
        row = self.get()
        row.rewatch_share = rewatch_share
        row.updated_at = utc_now()
        return row

    def commit(self) -> None:
        """Seal the unit of work (the service's call, mirroring the other modules)."""
        self._session.commit()
