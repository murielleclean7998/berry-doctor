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
    co2_ppm REAL,
    solution_ec REAL,
    solution_ph REAL,
    nutrient_temp REAL,
    relay_state_json TEXT
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

CREATE TABLE IF NOT EXISTS control_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    action TEXT,
    device TEXT,
    mode TEXT,
    reason TEXT,
    payload_json TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS market_price_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    item TEXT,
    price_per_kg REAL,
    change_amount REAL,
    trend INTEGER,
    forecast_price REAL,
    source TEXT
);

CREATE TABLE IF NOT EXISTS camera_capture_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    trigger_source TEXT,
    status TEXT,
    image_name TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS community_insight (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    summary TEXT,
    tags TEXT,
    source_site TEXT,
    shared BOOLEAN DEFAULT 1,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS pilot_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    site_name TEXT,
    category TEXT,
    sentiment TEXT,
    feedback TEXT,
    status TEXT,
    action_item TEXT
);

CREATE TABLE IF NOT EXISTS monthly_report_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    month_key TEXT,
    summary_json TEXT,
    sent BOOLEAN DEFAULT 0
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


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


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

    @staticmethod
    def _normalize_house_id(snapshot: dict[str, Any], house_id: int | None) -> int:
        candidate = house_id or snapshot.get("house_id") or snapshot.get("house") or 1
        return int(candidate)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        assert self.db_path is not None
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
        schema_sql = schema_path.read_text(encoding="utf-8") if schema_path.exists() else SCHEMA_SQL_FALLBACK
        with self.connect() as conn:
            conn.executescript(schema_sql)
            self._run_lightweight_migrations(conn)

    def _run_lightweight_migrations(self, conn: sqlite3.Connection) -> None:
        self._ensure_columns(
            conn,
            "sensor_log",
            {
                "solution_ec": "REAL",
                "solution_ph": "REAL",
                "nutrient_temp": "REAL",
                "relay_state_json": "TEXT",
            },
        )

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, column_type in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

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

    def recent_diary(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM farm_diary ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_sensor_snapshot(self, snapshot: dict[str, Any], house_id: int | None = None) -> int:
        normalized_house = self._normalize_house_id(snapshot, house_id)
        relay_state = snapshot.get("relay_state") or snapshot.get("relay_states")
        relay_json = self._serialize_value(relay_state) if relay_state is not None else None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sensor_log (
                    house_id, temp_indoor, temp_outdoor, humidity, soil_moisture_1, soil_moisture_2,
                    soil_temp, light_lux, leaf_wetness, water_level, co2_ppm,
                    solution_ec, solution_ph, nutrient_temp, relay_state_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_house,
                    snapshot.get("temp_indoor"),
                    snapshot.get("temp_outdoor"),
                    snapshot.get("humidity"),
                    snapshot.get("soil_moisture_1"),
                    snapshot.get("soil_moisture_2"),
                    snapshot.get("soil_temp"),
                    snapshot.get("light_lux"),
                    snapshot.get("leaf_wetness"),
                    snapshot.get("water_level"),
                    snapshot.get("co2_ppm"),
                    snapshot.get("solution_ec"),
                    snapshot.get("solution_ph"),
                    snapshot.get("nutrient_temp"),
                    relay_json,
                ),
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
        payload = _as_dict(row)
        if payload and payload.get("relay_state_json"):
            payload["relay_state"] = self._deserialize_value(payload["relay_state_json"], {})
        return payload

    def sensor_history(self, limit: int = 48, house_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sensor_log"
        params: tuple[Any, ...] = ()
        if house_id is not None:
            sql += " WHERE house_id = ?"
            params = (house_id,)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params = params + (limit,)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            if item.get("relay_state_json"):
                item["relay_state"] = self._deserialize_value(item["relay_state_json"], {})
        return payload

    def prune_old_sensor_logs(self, days: int = 90) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM sensor_log WHERE timestamp < ?", (cutoff,))
            return int(cursor.rowcount)

    def record_spray(self, pesticide_name: str, target_disease: str, dilution: int | None, phi_days: int | None, house_id: int | None = None) -> int:
        safe_harvest_date = (date.today() + timedelta(days=phi_days)).isoformat() if phi_days is not None else None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO spray_log (house_id, pesticide_name, target_disease, dilution, phi_days, safe_harvest_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (house_id, pesticide_name, target_disease, dilution, phi_days, safe_harvest_date),
            )
            return int(cursor.lastrowid)

    def recent_sprays(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM spray_log ORDER BY timestamp DESC LIMIT ?",
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

    def record_harvest(
        self,
        weight_kg: float,
        house_id: int | None = None,
        grade: str = "A",
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

    def recent_harvests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM harvest_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

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
        return float(row["total"] if row else 0.0)

    def harvest_by_house(self, days: int = 30) -> list[dict[str, Any]]:
        since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT COALESCE(house_id, 0) AS house_id,
                       COUNT(*) AS harvest_count,
                       COALESCE(SUM(weight_kg), 0) AS total_weight,
                       COALESCE(AVG(weight_kg), 0) AS avg_weight
                FROM harvest_log
                WHERE timestamp >= ?
                GROUP BY COALESCE(house_id, 0)
                ORDER BY total_weight DESC
                """,
                (since,),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def recent_diagnoses(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM diagnosis_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_control_action(
        self,
        action: str,
        device: str,
        mode: str,
        reason: str,
        payload: dict[str, Any] | None = None,
        result: str = "queued",
        house_id: int | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO control_log (house_id, action, device, mode, reason, payload_json, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (house_id, action, device, mode, reason, self._serialize_value(payload or {}), result),
            )
            return int(cursor.lastrowid)

    def recent_control_actions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM control_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            item["payload"] = self._deserialize_value(item.get("payload_json"), {})
        return payload

    def record_market_snapshot(
        self,
        item: str,
        price_per_kg: float,
        change_amount: float,
        trend: int,
        source: str,
        forecast_price: float | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO market_price_log (item, price_per_kg, change_amount, trend, forecast_price, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item, price_per_kg, change_amount, trend, forecast_price, source),
            )
            return int(cursor.lastrowid)

    def market_history(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM market_price_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_camera_capture(
        self,
        house_id: int | None,
        trigger_source: str,
        status: str,
        image_name: str | None = None,
        note: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO camera_capture_log (house_id, trigger_source, status, image_name, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (house_id, trigger_source, status, image_name, note),
            )
            return int(cursor.lastrowid)

    def recent_camera_captures(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM camera_capture_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_community_insight(
        self,
        title: str,
        summary: str,
        tags: list[str] | None = None,
        source_site: str = "berry-doctor",
        shared: bool = True,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO community_insight (title, summary, tags, source_site, shared, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, summary, self._serialize_value(tags or []), source_site, int(shared), self._serialize_value(payload or {})),
            )
            return int(cursor.lastrowid)

    def recent_community_insights(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM community_insight ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            item["tags_list"] = self._deserialize_value(item.get("tags"), [])
            item["payload"] = self._deserialize_value(item.get("payload_json"), {})
        return payload

    def record_pilot_feedback(
        self,
        site_name: str,
        category: str,
        sentiment: str,
        feedback: str,
        status: str = "open",
        action_item: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pilot_feedback (site_name, category, sentiment, feedback, status, action_item)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (site_name, category, sentiment, feedback, status, action_item),
            )
            return int(cursor.lastrowid)

    def recent_pilot_feedback(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pilot_feedback ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_monthly_report(self, month_key: str, summary: dict[str, Any], sent: bool = False) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO monthly_report_log (month_key, summary_json, sent)
                VALUES (?, ?, ?)
                """,
                (month_key, self._serialize_value(summary), int(sent)),
            )
            return int(cursor.lastrowid)

    def latest_monthly_report(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM monthly_report_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        payload = _as_dict(row)
        if payload:
            payload["summary"] = self._deserialize_value(payload.get("summary_json"), {})
        return payload

    def backup_to(self, target: Path | str) -> Path:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source:
            destination = sqlite3.connect(target_path)
            try:
                source.backup(destination)
                destination.commit()
            finally:
                destination.close()
        return target_path
