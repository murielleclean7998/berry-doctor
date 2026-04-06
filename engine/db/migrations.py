from __future__ import annotations

from engine.db.sqlite import SQLiteRepository


def run_pending_migrations(repository: SQLiteRepository) -> None:
    """Phase 0 keeps a single schema version. Hook left for future migrations."""
    repository.initialize()
