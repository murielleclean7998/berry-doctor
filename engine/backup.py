from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.paths import writable_root


@dataclass(slots=True)
class BackupService:
    repository: Any
    retention_count: int = 14
    backup_root: Path | None = None

    @property
    def backup_dir(self) -> Path:
        if self.backup_root is not None:
            path = self.backup_root
        else:
            db_path = getattr(self.repository, "db_path", None)
            base_dir = Path(db_path).parent if db_path is not None else writable_root()
            path = base_dir / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.backup_dir / f"berry-{stamp}.db"
        self.repository.backup_to(target)
        self.prune_old()
        return target

    def list_backups(self, limit: int = 20) -> list[dict[str, Any]]:
        files = sorted(self.backup_dir.glob("berry-*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        items: list[dict[str, Any]] = []
        for item in files[:limit]:
            stat = item.stat()
            items.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
        return items

    def latest_backup(self) -> Path | None:
        files = self.list_backups(limit=1)
        if not files:
            return None
        return Path(files[0]["path"])

    def prune_old(self) -> int:
        files = sorted(self.backup_dir.glob("berry-*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        removed = 0
        for item in files[self.retention_count :]:
            item.unlink(missing_ok=True)
            removed += 1
        return removed
