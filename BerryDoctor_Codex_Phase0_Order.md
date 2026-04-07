# BerryDoctor Phase 0 MVP — Codex Development Order

## Context

You are building **BerryDoctor (딸기박사)** — a free, open-source smart strawberry farm total solution for small Korean farmers. Three reference documents are attached:

1. **BerryDoctor_Codex_Handoff_v2.0.md** — Master spec (architecture, modules, code specs, data schemas, build instructions). **This is your primary reference.**
2. **BerryDoctor_Total_Solution_Spec_v1.1.md** — Hardware schematics, circuit diagrams, GPIO pin maps, 3-country tech comparison.
3. **BerryDoctor_파일럿 농가_농장_설치가이드.md** — Pilot farm context (Seosan Buseok-myeon, Seolhyang variety, soil-based, 200pyeong × 3 houses).

## Phase 0 MVP Scope

Build a **working Windows .exe** that does the following **without any hardware sensors** (software-only mode):

### Must Have (Phase 0)

1. **KakaoTalk Bot Integration**
   - Receive messages via webhook (Flask mini-server)
   - Send alerts via KakaoTalk Channel API
   - Parse all commands defined in Section 7 of v2.0 spec
   - Respond with templated messages from `engine/ai/coach.py`

2. **AI Disease Diagnosis (Photo)**
   - Receive photo via KakaoTalk → run YOLOv8s ONNX inference
   - Pre-trained model: train on Kaggle "Strawberry Disease Detection Dataset" (2,958 images, 7 diseases + healthy)
   - Export to `models/berry-disease-v1.onnx`
   - Return: disease name (Korean), confidence %, recommended pesticide from `pesticide_db.json`, farmer tip from `farmer_tips.json`
   - If confidence < 70%: append "정확하지 않을 수 있어요. 직접 확인 부탁드려요"

3. **Weather Integration**
   - Fetch KMA (기상청) ultra-short-term forecast API every hour
   - Fetch 팜맵 agricultural weather API (data.go.kr/15058627)
   - Frost prediction: if tomorrow min temp < -5°C (Buseok-myeon coastal profile) → KakaoTalk alert
   - Heavy rain prediction: if hourly rainfall > 20mm → KakaoTalk alert with drainage check reminder
   - Disease risk calculation: temp × humidity → Botrytis probability (see `disease_risk.py` spec in v2.0 Section 4.5)

4. **Daily Report (21:00 auto-send)**
   - Weather summary (today + tomorrow forecast)
   - Growth stage reminder (from `seolhyang_calendar.json`)
   - Market price (가락시장 경락가 API)
   - Tomorrow's task recommendations (from Knowledge Graph)
   - Farmer tip of the day

5. **"Strawberry Coach" Conversation Engine**
   - When sensor data is unavailable (Phase 0), use weather API data + growth stage + Knowledge Graph
   - Answer questions like "오늘 할일", "시세", "보조금" using data files in `data/` directory
   - All responses in Korean casual-polite tone (해요체), explain WHY something is recommended

6. **SQLite Database**
   - Implement schema from v2.0 Section 10
   - Store: farm_diary (KakaoTalk text input), spray_log, harvest_log, alert_log, config
   - Auto-delete sensor_log older than 90 days (for future Phase 1)

7. **Setup Wizard (first run)**
   - Minimal tkinter window: farm location (시군구 dropdown), house count, variety, cultivation type
   - Load regional profile from `regional_profiles.json`
   - Generate config in SQLite

8. **System Tray Icon**
   - pystray: green=normal, yellow=warning, red=critical
   - Right-click menu: "대시보드 열기", "설정", "종료"
   - Runs in background, auto-start with Windows (optional)

9. **Mosquitto Embedded**
   - Bundle mosquitto.exe, auto-start on launch
   - Ready for Phase 1 ESP32 connection (no sensors in Phase 0, but broker must be running)

10. **PyInstaller Build**
    - Single `딸기박사.exe` with all models, data, mosquitto bundled
    - No Python installation required on farmer's PC
    - No signup, no login, no browser required

### Must NOT Have (Phase 0)

- ESP32 firmware (Phase 1)
- Relay control (Phase 2)
- Local LLM / RAG (Phase 3)
- Yield prediction (Phase 3+)
- Web dashboard can be minimal/placeholder

### Data Files to Create

Create all JSON files specified in `data/` directory of v2.0 spec:
- `knowledge_graph.json` — Seolhyang growth stages, environment requirements per stage
- `farmer_tips.json` — At least 20 tips (expand from the 7 examples in spec)
- `pesticide_db.json` — All registered pesticides for strawberry diseases in Korea
- `subsidy_db.json` — Major 2026 smart farm subsidy programs
- `regional_profiles.json` — At least 5 regions (서산 부석면, 논산, 담양, 진주, 밀양)
- `seolhyang_calendar.json` — Month-by-month growth stage with environment targets
- `class_labels_ko.json` — Korean disease name mapping for YOLO classes

### AI Model Training

Before building the app, train the disease detection model:

```
1. Download: Kaggle "Strawberry Disease Detection Dataset" 
2. Augment: flip, rotate, brightness, crop → ~15,000 images
3. Train: YOLOv8s, 100 epochs, imgsz=640
4. Validate: mAP50 ≥ 0.90
5. Export: ONNX format → models/berry-disease-v1.onnx
6. Test: inference < 200ms on CPU
```

### Tech Stack (strict)

- Python 3.11+
- SQLite3 (built-in, no external DB)
- paho-mqtt 2.0+
- APScheduler 3.10+
- FastAPI + Jinja2 (minimal web dashboard)
- pystray + Pillow (system tray)
- ONNX Runtime 1.17+ (YOLO inference)
- httpx (API calls)
- Flask (KakaoTalk webhook receiver)
- PyInstaller 6.0+ (build)
- Mosquitto 2.0+ (embedded binary)

### Directory Structure

Follow exactly the structure defined in v2.0 spec Section 3.

### Key Design Rules

1. **Zero signup** — No external service registration required by the farmer
2. **Korean casual-polite tone** — All messages in 해요체, explain like talking to a neighbor
3. **Every alert explains WHY** — Include sensor data, regional context, and farmer tip
4. **Graceful degradation** — If any API fails, continue with cached data + inform user
5. **i18n ready** — All user-facing strings via `i18n/ko.json`, never hardcoded
6. **Windows compatible** — Target Windows 10/11, test on both

### Deliverables

1. Complete source code in `berry-doctor/` repository structure
2. Trained YOLO model (`berry-disease-v1.onnx`)
3. All data JSON files populated
4. Working `딸기박사.exe` build
5. `README.md` with setup instructions
6. Basic test suite (`tests/`)

### Success Criteria

- [ ] `딸기박사.exe` double-click → runs without Python installed
- [ ] KakaoTalk: send strawberry disease photo → receive Korean diagnosis + pesticide recommendation
- [ ] KakaoTalk: type "상태" → receive weather-based farm status
- [ ] KakaoTalk: type "오늘 할일" → receive daily task recommendations
- [ ] KakaoTalk: type "시세" → receive 가락시장 Seolhyang price
- [ ] KakaoTalk: type "기록 농약 프로피네브" → stored in SQLite spray_log
- [ ] KakaoTalk: type "기록 수확 30kg" → stored in SQLite harvest_log
- [ ] 21:00 daily → auto-send daily report via KakaoTalk
- [ ] Frost/rain warning → auto-alert via KakaoTalk
- [ ] System tray icon visible, green status
- [ ] Mosquitto broker running on localhost:1883 (ready for Phase 1)

Start with the repository scaffold, then implement in this order:
`schema.sql → config.py → mqtt_broker.py → disease_detector.py → kakao/ → scheduler/ → coach.py → tray/ → PyInstaller build`
