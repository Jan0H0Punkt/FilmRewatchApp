"""Business-logic layer for the stats module (DESIGN §5.1) — the seam the router depends on."""

from datetime import date

from app.stats.algorithm import Stats, compute
from app.stats.repository import StatsRepository


class StatsService:
    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    def stats(self, today: date) -> Stats:
        return compute(self._repository.watches(), today)
