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
CREATE INDEX IF NOT EXISTS idx_sensor_log_house_timestamp ON sensor_log (house_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS sensor_latest (
    house_id INTEGER PRIMARY KEY,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

CREATE TABLE IF NOT EXISTS sensor_minute_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER NOT NULL,
    bucket_minute DATETIME NOT NULL,
    sample_count INTEGER DEFAULT 0,
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
    relay_state_json TEXT,
    UNIQUE (house_id, bucket_minute)
);
CREATE INDEX IF NOT EXISTS idx_sensor_minute_log_house_bucket ON sensor_minute_log (house_id, bucket_minute DESC);

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
CREATE INDEX IF NOT EXISTS idx_community_insight_source_timestamp ON community_insight (source_site, timestamp DESC);

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

CREATE TABLE IF NOT EXISTS signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME,
    source TEXT,
    title TEXT,
    summary TEXT,
    url TEXT,
    language TEXT,
    relevance_score REAL,
    urgency TEXT,
    delivered BOOLEAN DEFAULT 0,
    hash TEXT UNIQUE,
    tags_json TEXT,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_signal_log_timestamp ON signal_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signal_log_urgency_timestamp ON signal_log (urgency, timestamp DESC);

CREATE TABLE IF NOT EXISTS satellite_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    capture_date DATE,
    satellite TEXT,
    cloud_pct REAL,
    ndvi_mean REAL,
    ndvi_min REAL,
    ndvi_max REAL,
    ndwi_mean REAL,
    gndvi_mean REAL,
    change_vs_prev REAL,
    change_vs_year REAL,
    change_vs_region REAL,
    raw_data_path TEXT,
    status TEXT DEFAULT 'ok',
    note TEXT,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_satellite_log_house_capture ON satellite_log (house_id, capture_date DESC);

CREATE TABLE IF NOT EXISTS fusion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    trigger_source TEXT,
    trigger_detail TEXT,
    sensor_risk REAL,
    satellite_risk REAL,
    signal_risk REAL,
    composite_risk REAL,
    agreement TEXT,
    level TEXT,
    message_sent TEXT,
    farmer_response TEXT
);
CREATE INDEX IF NOT EXISTS idx_fusion_log_trigger_timestamp ON fusion_log (trigger_source, timestamp DESC);

CREATE TABLE IF NOT EXISTS security_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    photo_paths TEXT,
    acknowledged BOOLEAN DEFAULT 0,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_security_log_house_timestamp ON security_log (house_id, timestamp DESC);
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

    @staticmethod
    def _sensor_field_names() -> tuple[str, ...]:
        return (
            "temp_indoor",
            "temp_outdoor",
            "humidity",
            "soil_moisture_1",
            "soil_moisture_2",
            "soil_temp",
            "light_lux",
            "leaf_wetness",
            "water_level",
            "co2_ppm",
            "solution_ec",
            "solution_ph",
            "nutrient_temp",
        )

    @classmethod
    def _sensor_row_payload(cls, snapshot: dict[str, Any], house_id: int | None = None) -> tuple[int, dict[str, Any]]:
        normalized_house = cls._normalize_house_id(snapshot, house_id)
        relay_state = snapshot.get("relay_state") or snapshot.get("relay_states")
        payload = {field: snapshot.get(field) for field in cls._sensor_field_names()}
        payload["relay_state_json"] = cls._serialize_value(relay_state) if relay_state is not None else None
        return normalized_house, payload

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sensor_log_house_timestamp ON sensor_log (house_id, timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sensor_minute_log_house_bucket ON sensor_minute_log (house_id, bucket_minute DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_community_insight_source_timestamp ON community_insight (source_site, timestamp DESC)")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS signal_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                published_at DATETIME,
                source TEXT,
                title TEXT,
                summary TEXT,
                url TEXT,
                language TEXT,
                relevance_score REAL,
                urgency TEXT,
                delivered BOOLEAN DEFAULT 0,
                hash TEXT UNIQUE,
                tags_json TEXT,
                payload_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_signal_log_timestamp ON signal_log (timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_signal_log_urgency_timestamp ON signal_log (urgency, timestamp DESC);
            CREATE TABLE IF NOT EXISTS satellite_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                house_id INTEGER,
                capture_date DATE,
                satellite TEXT,
                cloud_pct REAL,
                ndvi_mean REAL,
                ndvi_min REAL,
                ndvi_max REAL,
                ndwi_mean REAL,
                gndvi_mean REAL,
                change_vs_prev REAL,
                change_vs_year REAL,
                change_vs_region REAL,
                raw_data_path TEXT,
                status TEXT DEFAULT 'ok',
                note TEXT,
                payload_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_satellite_log_house_capture ON satellite_log (house_id, capture_date DESC);
            CREATE TABLE IF NOT EXISTS fusion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                trigger_source TEXT,
                trigger_detail TEXT,
                sensor_risk REAL,
                satellite_risk REAL,
                signal_risk REAL,
                composite_risk REAL,
                agreement TEXT,
                level TEXT,
                message_sent TEXT,
                farmer_response TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_fusion_log_trigger_timestamp ON fusion_log (trigger_source, timestamp DESC);
            CREATE TABLE IF NOT EXISTS security_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                house_id INTEGER,
                photo_paths TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                note TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_security_log_house_timestamp ON security_log (house_id, timestamp DESC);
            """
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
        normalized_house, payload = self._sensor_row_payload(snapshot, house_id)
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
                    payload.get("temp_indoor"),
                    payload.get("temp_outdoor"),
                    payload.get("humidity"),
                    payload.get("soil_moisture_1"),
                    payload.get("soil_moisture_2"),
                    payload.get("soil_temp"),
                    payload.get("light_lux"),
                    payload.get("leaf_wetness"),
                    payload.get("water_level"),
                    payload.get("co2_ppm"),
                    payload.get("solution_ec"),
                    payload.get("solution_ph"),
                    payload.get("nutrient_temp"),
                    payload.get("relay_state_json"),
                ),
            )
            return int(cursor.lastrowid)

    def upsert_latest_sensor_snapshot(self, snapshot: dict[str, Any], house_id: int | None = None) -> int:
        normalized_house, payload = self._sensor_row_payload(snapshot, house_id)
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sensor_latest (
                    house_id, updated_at, temp_indoor, temp_outdoor, humidity, soil_moisture_1, soil_moisture_2,
                    soil_temp, light_lux, leaf_wetness, water_level, co2_ppm,
                    solution_ec, solution_ph, nutrient_temp, relay_state_json
                )
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(house_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP,
                    temp_indoor = excluded.temp_indoor,
                    temp_outdoor = excluded.temp_outdoor,
                    humidity = excluded.humidity,
                    soil_moisture_1 = excluded.soil_moisture_1,
                    soil_moisture_2 = excluded.soil_moisture_2,
                    soil_temp = excluded.soil_temp,
                    light_lux = excluded.light_lux,
                    leaf_wetness = excluded.leaf_wetness,
                    water_level = excluded.water_level,
                    co2_ppm = excluded.co2_ppm,
                    solution_ec = excluded.solution_ec,
                    solution_ph = excluded.solution_ph,
                    nutrient_temp = excluded.nutrient_temp,
                    relay_state_json = excluded.relay_state_json
                """,
                (
                    normalized_house,
                    payload.get("temp_indoor"),
                    payload.get("temp_outdoor"),
                    payload.get("humidity"),
                    payload.get("soil_moisture_1"),
                    payload.get("soil_moisture_2"),
                    payload.get("soil_temp"),
                    payload.get("light_lux"),
                    payload.get("leaf_wetness"),
                    payload.get("water_level"),
                    payload.get("co2_ppm"),
                    payload.get("solution_ec"),
                    payload.get("solution_ph"),
                    payload.get("nutrient_temp"),
                    payload.get("relay_state_json"),
                ),
            )
            return int(cursor.lastrowid or normalized_house)

    def record_sensor_minute_aggregate(
        self,
        snapshot: dict[str, Any],
        house_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        normalized_house, payload = self._sensor_row_payload(snapshot, house_id)
        bucket = (timestamp or datetime.now(UTC)).replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        fields = self._sensor_field_names()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT * FROM sensor_minute_log WHERE house_id = ? AND bucket_minute = ?",
                (normalized_house, bucket),
            ).fetchone()
            if existing is None:
                cursor = conn.execute(
                    """
                    INSERT INTO sensor_minute_log (
                        house_id, bucket_minute, sample_count, temp_indoor, temp_outdoor, humidity,
                        soil_moisture_1, soil_moisture_2, soil_temp, light_lux, leaf_wetness, water_level,
                        co2_ppm, solution_ec, solution_ph, nutrient_temp, relay_state_json
                    )
                    VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_house,
                        bucket,
                        payload.get("temp_indoor"),
                        payload.get("temp_outdoor"),
                        payload.get("humidity"),
                        payload.get("soil_moisture_1"),
                        payload.get("soil_moisture_2"),
                        payload.get("soil_temp"),
                        payload.get("light_lux"),
                        payload.get("leaf_wetness"),
                        payload.get("water_level"),
                        payload.get("co2_ppm"),
                        payload.get("solution_ec"),
                        payload.get("solution_ph"),
                        payload.get("nutrient_temp"),
                        payload.get("relay_state_json"),
                    ),
                )
                return int(cursor.lastrowid)

            sample_count = int(existing["sample_count"] or 0)
            updated_fields: dict[str, Any] = {}
            for field in fields:
                new_value = payload.get(field)
                old_value = existing[field]
                if new_value is None:
                    updated_fields[field] = old_value
                elif old_value is None or sample_count <= 0:
                    updated_fields[field] = float(new_value)
                else:
                    updated_fields[field] = ((float(old_value) * sample_count) + float(new_value)) / (sample_count + 1)
            relay_state_json = payload.get("relay_state_json") or existing["relay_state_json"]
            conn.execute(
                """
                UPDATE sensor_minute_log
                SET sample_count = ?,
                    temp_indoor = ?,
                    temp_outdoor = ?,
                    humidity = ?,
                    soil_moisture_1 = ?,
                    soil_moisture_2 = ?,
                    soil_temp = ?,
                    light_lux = ?,
                    leaf_wetness = ?,
                    water_level = ?,
                    co2_ppm = ?,
                    solution_ec = ?,
                    solution_ph = ?,
                    nutrient_temp = ?,
                    relay_state_json = ?
                WHERE id = ?
                """,
                (
                    sample_count + 1,
                    updated_fields["temp_indoor"],
                    updated_fields["temp_outdoor"],
                    updated_fields["humidity"],
                    updated_fields["soil_moisture_1"],
                    updated_fields["soil_moisture_2"],
                    updated_fields["soil_temp"],
                    updated_fields["light_lux"],
                    updated_fields["leaf_wetness"],
                    updated_fields["water_level"],
                    updated_fields["co2_ppm"],
                    updated_fields["solution_ec"],
                    updated_fields["solution_ph"],
                    updated_fields["nutrient_temp"],
                    relay_state_json,
                    existing["id"],
                ),
            )
            return int(existing["id"])

    def latest_sensor_snapshot(self, house_id: int | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM sensor_latest"
        params: tuple[Any, ...] = ()
        if house_id is not None:
            sql += " WHERE house_id = ?"
            params = (house_id,)
        sql += " ORDER BY updated_at DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            if row is None:
                fallback_sql = "SELECT * FROM sensor_log"
                fallback_params: tuple[Any, ...] = ()
                if house_id is not None:
                    fallback_sql += " WHERE house_id = ?"
                    fallback_params = (house_id,)
                fallback_sql += " ORDER BY timestamp DESC LIMIT 1"
                row = conn.execute(fallback_sql, fallback_params).fetchone()
        payload = _as_dict(row)
        if payload and payload.get("relay_state_json"):
            payload["relay_state"] = self._deserialize_value(payload["relay_state_json"], {})
        if payload and payload.get("updated_at") and "timestamp" not in payload:
            payload["timestamp"] = payload["updated_at"]
        return payload

    def latest_sensor_snapshots(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM sensor_latest ORDER BY house_id ASC").fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            if item.get("relay_state_json"):
                item["relay_state"] = self._deserialize_value(item["relay_state_json"], {})
            if item.get("updated_at") and "timestamp" not in item:
                item["timestamp"] = item["updated_at"]
        return payload

    def sensor_history(self, limit: int = 48, house_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sensor_minute_log"
        params: tuple[Any, ...] = ()
        if house_id is not None:
            sql += " WHERE house_id = ?"
            params = (house_id,)
        sql += " ORDER BY bucket_minute DESC LIMIT ?"
        params = params + (limit,)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                fallback_sql = "SELECT * FROM sensor_log"
                fallback_params: tuple[Any, ...] = ()
                if house_id is not None:
                    fallback_sql += " WHERE house_id = ?"
                    fallback_params = (house_id,)
                fallback_sql += " ORDER BY timestamp DESC LIMIT ?"
                rows = conn.execute(fallback_sql, fallback_params + (limit,)).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            if item.get("relay_state_json"):
                item["relay_state"] = self._deserialize_value(item["relay_state_json"], {})
            if item.get("bucket_minute") and "timestamp" not in item:
                item["timestamp"] = item["bucket_minute"]
        return payload

    def prune_old_sensor_logs(self, days: int = 90, aggregate_days: int = 365) -> dict[str, int]:
        raw_cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        aggregate_cutoff = (datetime.now(UTC) - timedelta(days=aggregate_days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            raw_cursor = conn.execute("DELETE FROM sensor_log WHERE timestamp < ?", (raw_cutoff,))
            aggregate_cursor = conn.execute("DELETE FROM sensor_minute_log WHERE bucket_minute < ?", (aggregate_cutoff,))
            return {
                "raw_pruned_rows": int(raw_cursor.rowcount),
                "aggregate_pruned_rows": int(aggregate_cursor.rowcount),
            }

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
        dedupe_window_seconds: int | None = None,
    ) -> int:
        if dedupe_window_seconds:
            duplicate = self.find_recent_alert(
                rule_id=rule_id,
                severity=severity,
                message=message,
                house_id=house_id,
                within_seconds=dedupe_window_seconds,
            )
            if duplicate is not None:
                return int(duplicate["id"])
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

    def find_recent_alert(
        self,
        rule_id: str,
        severity: str,
        message: str,
        house_id: int | None,
        within_seconds: int,
    ) -> dict[str, Any] | None:
        cutoff = (datetime.now(UTC) - timedelta(seconds=within_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM alert_log
                WHERE timestamp >= ?
                  AND rule_id = ?
                  AND severity = ?
                  AND message = ?
                  AND ((house_id IS NULL AND ? IS NULL) OR house_id = ?)
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (cutoff, rule_id, severity, message, house_id, house_id),
            ).fetchone()
        return _as_dict(row)

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
        dedupe_window_seconds: int | None = None,
    ) -> int:
        payload_json = self._serialize_value(payload or {})
        if dedupe_window_seconds:
            duplicate = self.find_recent_control_action(
                action=action,
                device=device,
                mode=mode,
                house_id=house_id,
                payload_json=payload_json,
                within_seconds=dedupe_window_seconds,
            )
            if duplicate is not None:
                return int(duplicate["id"])
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO control_log (house_id, action, device, mode, reason, payload_json, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (house_id, action, device, mode, reason, payload_json, result),
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

    def find_recent_control_action(
        self,
        action: str,
        device: str,
        mode: str,
        house_id: int | None,
        payload_json: str,
        within_seconds: int,
    ) -> dict[str, Any] | None:
        cutoff = (datetime.now(UTC) - timedelta(seconds=within_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM control_log
                WHERE timestamp >= ?
                  AND action = ?
                  AND device = ?
                  AND mode = ?
                  AND payload_json = ?
                  AND ((house_id IS NULL AND ? IS NULL) OR house_id = ?)
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (cutoff, action, device, mode, payload_json, house_id, house_id),
            ).fetchone()
        payload = _as_dict(row)
        if payload and payload.get("payload_json"):
            payload["payload"] = self._deserialize_value(payload["payload_json"], {})
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
        dedupe_window_seconds: int | None = None,
    ) -> int:
        payload_json = self._serialize_value(payload or {})
        tags_json = self._serialize_value(tags or [])
        if dedupe_window_seconds:
            duplicate = self.find_recent_community_insight(
                title=title,
                summary=summary,
                source_site=source_site,
                tags_json=tags_json,
                payload_json=payload_json,
                within_seconds=dedupe_window_seconds,
            )
            if duplicate is not None:
                return int(duplicate["id"])
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO community_insight (title, summary, tags, source_site, shared, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, summary, tags_json, source_site, int(shared), payload_json),
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

    def find_recent_community_insight(
        self,
        title: str,
        summary: str,
        source_site: str,
        tags_json: str,
        payload_json: str,
        within_seconds: int,
    ) -> dict[str, Any] | None:
        cutoff = (datetime.now(UTC) - timedelta(seconds=within_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM community_insight
                WHERE timestamp >= ?
                  AND title = ?
                  AND summary = ?
                  AND source_site = ?
                  AND tags = ?
                  AND payload_json = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (cutoff, title, summary, source_site, tags_json, payload_json),
            ).fetchone()
        payload = _as_dict(row)
        if payload:
            payload["tags_list"] = self._deserialize_value(payload.get("tags"), [])
            payload["payload"] = self._deserialize_value(payload.get("payload_json"), {})
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

    def record_signal(
        self,
        source: str,
        title: str,
        summary: str,
        url: str,
        language: str,
        relevance_score: float,
        urgency: str,
        signal_hash: str,
        tags: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        published_at: datetime | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO signal_log (
                    published_at, source, title, summary, url, language,
                    relevance_score, urgency, hash, tags_json, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hash) DO NOTHING
                """,
                (
                    published_at.isoformat() if published_at else None,
                    source,
                    title,
                    summary,
                    url,
                    language,
                    relevance_score,
                    urgency,
                    signal_hash,
                    self._serialize_value(tags or []),
                    self._serialize_value(payload or {}),
                ),
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)
        existing = self.find_signal_by_hash(signal_hash)
        return int(existing["id"]) if existing is not None else 0

    def find_signal_by_hash(self, signal_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM signal_log WHERE hash = ? LIMIT 1", (signal_hash,)).fetchone()
        payload = _as_dict(row)
        if payload:
            payload["tags"] = self._deserialize_value(payload.get("tags_json"), [])
            payload["payload"] = self._deserialize_value(payload.get("payload_json"), {})
        return payload

    def recent_signals(self, hours: int = 48, limit: int = 20, delivered: bool | None = None) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        query = "SELECT * FROM signal_log WHERE timestamp >= ?"
        params: list[Any] = [cutoff]
        if delivered is not None:
            query += " AND delivered = ?"
            params.append(int(delivered))
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            item["tags"] = self._deserialize_value(item.get("tags_json"), [])
            item["payload"] = self._deserialize_value(item.get("payload_json"), {})
        return payload

    def count_signal_deliveries_today(self, on_day: date | None = None) -> int:
        on_day = on_day or datetime.now(UTC).date()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM signal_log
                WHERE delivered = 1
                  AND date(timestamp) = ?
                """,
                (on_day.isoformat(),),
            ).fetchone()
        return int(row["total"] if row else 0)

    def mark_signal_delivered(self, signal_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE signal_log SET delivered = 1 WHERE id = ?", (signal_id,))

    def record_satellite_log(
        self,
        house_id: int,
        capture_date: date,
        satellite: str,
        cloud_pct: float,
        ndvi_mean: float,
        ndvi_min: float,
        ndvi_max: float,
        ndwi_mean: float,
        gndvi_mean: float,
        change_vs_prev: float,
        change_vs_year: float,
        change_vs_region: float,
        raw_data_path: str | None = None,
        status: str = "ok",
        note: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO satellite_log (
                    house_id, capture_date, satellite, cloud_pct, ndvi_mean, ndvi_min, ndvi_max,
                    ndwi_mean, gndvi_mean, change_vs_prev, change_vs_year, change_vs_region,
                    raw_data_path, status, note, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    house_id,
                    capture_date.isoformat(),
                    satellite,
                    cloud_pct,
                    ndvi_mean,
                    ndvi_min,
                    ndvi_max,
                    ndwi_mean,
                    gndvi_mean,
                    change_vs_prev,
                    change_vs_year,
                    change_vs_region,
                    raw_data_path,
                    status,
                    note,
                    self._serialize_value(payload or {}),
                ),
            )
            return int(cursor.lastrowid)

    def recent_satellite_logs(self, limit: int = 20, house_id: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM satellite_log"
        params: list[Any] = []
        if house_id is not None:
            query += " WHERE house_id = ?"
            params.append(house_id)
        query += " ORDER BY capture_date DESC, timestamp DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            item["payload"] = self._deserialize_value(item.get("payload_json"), {})
        return payload

    def latest_satellite_log(self, house_id: int | None = None, days_ago: int | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM satellite_log"
        params: list[Any] = []
        clauses: list[str] = []
        if house_id is not None:
            clauses.append("house_id = ?")
            params.append(house_id)
        if days_ago is not None:
            target = (date.today() - timedelta(days=days_ago)).isoformat()
            clauses.append("capture_date <= ?")
            params.append(target)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY capture_date DESC, timestamp DESC LIMIT 1"
        with self.connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        payload = _as_dict(row)
        if payload:
            payload["payload"] = self._deserialize_value(payload.get("payload_json"), {})
        return payload

    def record_fusion_log(
        self,
        trigger_source: str,
        trigger_detail: str,
        sensor_risk: float,
        satellite_risk: float,
        signal_risk: float,
        composite_risk: float,
        agreement: str,
        level: str,
        message_sent: str,
        farmer_response: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO fusion_log (
                    trigger_source, trigger_detail, sensor_risk, satellite_risk, signal_risk,
                    composite_risk, agreement, level, message_sent, farmer_response
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trigger_source,
                    trigger_detail,
                    sensor_risk,
                    satellite_risk,
                    signal_risk,
                    composite_risk,
                    agreement,
                    level,
                    message_sent,
                    farmer_response,
                ),
            )
            return int(cursor.lastrowid)

    def find_recent_fusion_event(self, trigger_source: str, within_seconds: int) -> dict[str, Any] | None:
        cutoff = (datetime.now(UTC) - timedelta(seconds=within_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM fusion_log
                WHERE timestamp >= ?
                  AND trigger_source = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (cutoff, trigger_source),
            ).fetchone()
        return _as_dict(row)

    def recent_fusion_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM fusion_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def record_security_event(
        self,
        house_id: int,
        photo_paths: list[str],
        timestamp: str | None = None,
        acknowledged: bool = False,
        note: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO security_log (timestamp, house_id, photo_paths, acknowledged, note)
                VALUES (COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?)
                """,
                (timestamp, house_id, self._serialize_value(photo_paths), int(acknowledged), note),
            )
            return int(cursor.lastrowid)

    def recent_security_events(self, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM security_log
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
        payload = [dict(row) for row in rows]
        for item in payload:
            item["photo_paths_list"] = self._deserialize_value(item.get("photo_paths"), [])
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
