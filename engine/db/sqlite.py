from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from engine.paths import app_root, writable_root

logger = logging.getLogger(__name__)


SCHEMA_SQL_FALLBACK = """
CREATE TABLE IF NOT EXISTS sensor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    temp_indoor REAL,
    temp_outdoor REAL,
    humidity REAL,
    soil_moisture_1 REAL,
    soil_moisture_2 REAL,
    soil_temp REAL,
    light_lux REAL,
    leaf_wetness REAL,
    water_level REAL,
    co2_ppm REAL
);

CREATE TABLE IF NOT EXISTS farm_diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    entry_type TEXT,
    content TEXT,
    auto_generated BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spray_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    pesticide_name TEXT,
    target_disease TEXT,
    dilution INTEGER,
    phi_days INTEGER,
    safe_harvest_date DATE
);

CREATE TABLE IF NOT EXISTS harvest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    weight_kg REAL,
    grade TEXT,
    sale_price_per_kg REAL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    rule_id TEXT,
    severity TEXT,
    message TEXT,
    action_taken TEXT,
    acknowledged BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS diagnosis_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    disease_key TEXT,
    disease_name TEXT,
    confidence REAL,
    symptoms TEXT,
    pesticide_name TEXT,
    phi_days INTEGER,
    model_used TEXT,
    image_name TEXT
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS growth_stage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER,
    stage TEXT,
    started_at DATETIME,
    ended_at DATETIME,
    auto_detected BOOLEAN DEFAULT 1
);
"""


@dataclass(slots=True)
class SQLiteRepository:
    db_path: Path | None = None

    def __post_init__(self) -> None:
        if self.db_path is None:
            self.db_path = writable_root() / "berry.db"

    @staticmethod
    def _deserialize_value(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    @staticmethod
    def _serialize_value(value: Any) -> str:
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        schema_path = app_root() / "engine" / "db" / "schema.sql"
        if schema_path.exists():
            schema_sql = schema_path.read_text(encoding="utf-8")
        else:
            schema_sql = SCHEMA_SQL_FALLBACK
        with self.connect() as conn:
            conn.executescript(schema_sql)

    def get_config(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return self._deserialize_value(row["value"], default)

    def set_config(self, key: str, value: Any) -> None:
        stored = self._serialize_value(value)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, stored),
            )

    def set_many_config(self, entries: dict[str, Any]) -> None:
        rows = [(key, self._serialize_value(value)) for key, value in entries.items()]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def all_config(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {row["key"]: self._deserialize_value(row["value"]) for row in rows}

    def record_diary(self, content: str, house_id: int | None = None, entry_type: str = "note", auto_generated: bool = False) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO farm_diary (house_id, entry_type, content, auto_generated) VALUES (?, ?, ?, ?)",
                (house_id, entry_type, content, int(auto_generated)),
            )
            return int(cursor.lastrowid)

    def record_spray(self, pesticide_name: str, target_disease: str, dilution: int | None, phi_days: int | None, house_id: int | None = None) -> int:
        safe_harvest_date = None
        if phi_days is not None:
            safe_harvest_date = (date.today() + timedelta(days=phi_days)).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO spray_log (house_id, pesticide_name, target_disease, dilution, phi_days, safe_harvest_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (house_id, pesticide_name, target_disease, dilution, phi_days, safe_harvest_date),
            )
            return int(cursor.lastrowid)

    def record_harvest(
        self,
        weight_kg: float,
        house_id: int | None = None,
        grade: str = "특",
        sale_price_per_kg: float | None = None,
        note: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO harvest_log (house_id, weight_kg, grade, sale_price_per_kg, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (house_id, weight_kg, grade, sale_price_per_kg, note),
            )
            return int(cursor.lastrowid)

    def monthly_harvest_total(self, year: int | None = None, month: int | None = None) -> float:
        today = date.today()
        year = year or today.year
        month = month or today.month
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(weight_kg), 0) AS total
                FROM harvest_log
                WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?
                """,
                (f"{year:04d}", f"{month:02d}"),
            ).fetchone()
        return float(row["total"] if row else 0)

    def record_alert(
        self,
        rule_id: str,
        severity: str,
        message: str,
        house_id: int | None = None,
        action_taken: str | None = None,
        acknowledged: bool = False,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alert_log (house_id, rule_id, severity, message, action_taken, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (house_id, rule_id, severity, message, action_taken, int(acknowledged)),
            )
            return int(cursor.lastrowid)

    def record_diagnosis(
        self,
        disease_key: str,
        disease_name: str,
        confidence: float,
        symptoms: str,
        model_used: str,
        pesticide_name: str | None = None,
        phi_days: int | None = None,
        image_name: str | None = None,
        house_id: int | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO diagnosis_log (
                    house_id, disease_key, disease_name, confidence, symptoms,
                    pesticide_name, phi_days, model_used, image_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (house_id, disease_key, disease_name, confidence, symptoms, pesticide_name, phi_days, model_used, image_name),
            )
            return int(cursor.lastrowid)

    def latest_sensor_snapshot(self, house_id: int | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM sensor_log"
        params: tuple[Any, ...] = ()
        if house_id is not None:
            sql += " WHERE house_id = ?"
            params = (house_id,)
        sql += " ORDER BY timestamp DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def prune_old_sensor_logs(self, days: int = 90) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM sensor_log WHERE timestamp < ?", (cutoff,))
            return int(cursor.rowcount)

    def recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_sprays(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM spray_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_harvests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM harvest_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_diagnoses(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM diagnosis_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def active_spray_restrictions(self, reference_date: date | None = None, house_id: int | None = None) -> list[dict[str, Any]]:
        reference_date = reference_date or date.today()
        query = """
            SELECT *
            FROM spray_log
            WHERE safe_harvest_date IS NOT NULL
              AND safe_harvest_date >= ?
        """
        params: list[Any] = [reference_date.isoformat()]
        if house_id is not None:
            query += " AND (house_id = ? OR house_id IS NULL)"
            params.append(house_id)
        query += " ORDER BY safe_harvest_date ASC, timestamp DESC"
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]
