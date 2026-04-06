-- 센서 로그 (5초 간격, 자동 삭제: 90일)
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

-- 재배 일지 (카카오톡 입력)
CREATE TABLE IF NOT EXISTS farm_diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    entry_type TEXT,
    content TEXT,
    auto_generated BOOLEAN DEFAULT 0
);

-- 농약 살포 기록 (GAP 인증용)
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

-- 수확 기록
CREATE TABLE IF NOT EXISTS harvest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    weight_kg REAL,
    grade TEXT,
    sale_price_per_kg REAL,
    note TEXT
);

-- 알림 이력
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

-- 설정
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 생육 단계 이력
CREATE TABLE IF NOT EXISTS growth_stage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER,
    stage TEXT,
    started_at DATETIME,
    ended_at DATETIME,
    auto_detected BOOLEAN DEFAULT 1
);
