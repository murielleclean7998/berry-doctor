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
