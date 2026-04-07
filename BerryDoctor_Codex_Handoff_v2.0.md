# BerryDoctor (딸기박사) — Codex Handoff Spec v2.0

> **BerryDoctor Project | MIT License | The 4th Path: ⟨H⊕A⟩ ↦ Ω**
> Target: OpenClaw (GPT-5.4 Codex) Implementation
> Date: 2026-04-06
> Pilot Farm: 충남 서산시 부석면 / 설향 / 토경 / 200평×3동

---

## 0. 프로젝트 개요

BerryDoctor는 영세 딸기 농가를 위한 **무료 오픈소스 토털 스마트팜 솔루션**이다.
일본(소농 표준 패키지), 중국(AI 196% 증산), 한국(ICT 인프라) 3국의 검증된 기술을 통합하여,
**하드웨어 20~30만원 + 소프트웨어 0원**으로 프리바(Priva)급 환경제어를 실현한다.

### 0.1 설계 원칙

1. **가입 제로(Zero Signup)**: 어떤 외부 서비스 가입도 필요 없음
2. **더블클릭 설치**: `딸기박사.exe` 실행이 전부
3. **카카오톡이 UI**: 농부는 카톡 외에 아무것도 안 봄
4. **사전학습 완료 배포**: AI 모델은 .onnx로 내장, 농부가 학습시키는 것 없음
5. **PC 꺼져도 동작**: ESP32 펌웨어에 핵심 룰 5개 내장
6. **친절한 설명**: 모든 알림에 "왜 이 알림이 왔는지 + 어떻게 하면 되는지" 포함
7. **지역 맞춤**: 초기 설정에서 농장 위치 선택 → 지역별 기본값 자동 적용

### 0.2 수치 목표

| 지표 | 전통 농가 | BerryDoctor 적용 후 |
|------|-----------|-------------------|
| 병충해 손실 | 15~20% | **5% 이하** |
| 하우스 방문/일 | 3~5회 | **0~1회** |
| 난방비 | 기준 100% | **80~85%** (15~20% 절감) |
| 비료비 | 기준 100% | **70~80%** (20~30% 절감) |
| 소프트웨어 비용 | 연 100~300만원 | **0원** |
| 하드웨어 비용 | 1,500~3,000만원/동 | **7~10만원/동** |

---

## 1. 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│                   농부 인터페이스                    │
│  ┌──────────┐  ┌──────────────────────────────┐ │
│  │ 카카오톡  │  │ 웹 대시보드 (선택, 브라우저)   │ │
│  │  챗봇    │  │ localhost:8080               │ │
│  └────┬─────┘  └──────────┬───────────────────┘ │
└───────┼───────────────────┼─────────────────────┘
        │                   │
┌───────▼───────────────────▼─────────────────────┐
│           딸기박사.exe (단일 Python 프로세스)        │
│                                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │  berry-engine (메인 데몬)                     │ │
│  │  ├─ mqtt_client: 센서 데이터 수신             │ │
│  │  ├─ rule_engine: 환경제어 판단               │ │
│  │  ├─ pid_controller: 관비 EC 제어             │ │
│  │  ├─ disease_predictor: 온도×습도→발생확률     │ │
│  │  ├─ scheduler (APScheduler): 정기 작업       │ │
│  │  ├─ kakao_bot: 알림+명령 인터페이스           │ │
│  │  ├─ sensor_health: 센서 자기진단              │ │
│  │  └─ api_client: 기상청/도매시장/팜맵          │ │
│  └─────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │ SQLite        │  │ AI 모듈 (사전학습 완료)  │   │
│  │ berry.db      │  │ ├─ YOLO 병해진단 .onnx  │   │
│  │ ├ sensor_log  │  │ ├─ disease_prob 모델    │   │
│  │ ├ farm_diary  │  │ ├─ knowledge_graph.json │   │
│  │ ├ harvest_log │  │ ├─ farmer_tips.json     │   │
│  │ ├ spray_log   │  │ ├─ pesticide_db.json    │   │
│  │ ├ config      │  │ └─ price_forecast 모델   │   │
│  │ └ alerts      │  │                         │   │
│  └──────────────┘  └────────────────────────┘   │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │ Mosquitto     │  │ FastAPI 웹서버          │   │
│  │ (내장 MQTT)   │  │ localhost:8080         │   │
│  └──────────────┘  └────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐ │
│  │ 시스템 트레이 아이콘 (pystray)                 │ │
│  │ 🟢 정상 / 🟡 주의 / 🔴 긴급                   │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────┘
                       │ MQTT localhost:1883
┌──────────────────────▼──────────────────────────┐
│          온실 현장 (하우스 1~3동)                    │
│  ┌────────────────────────────────────────┐      │
│  │  ESP32-WROOM-32D (동별 1개)             │      │
│  │  ├─ 센서 입력 (온습도/토양/조도)         │      │
│  │  ├─ 릴레이 출력 (환풍/커튼/관수/보광)    │      │
│  │  ├─ 로컬 룰 5개 (PC 없이도 동작)        │      │
│  │  ├─ WiFi 끊김 시 SPIFFS 버퍼           │      │
│  │  └─ ESP32-CAM (병해 촬영)              │      │
│  └────────────────────────────────────────┘      │
└─────────────────────────────────────────────────┘
```

---

## 2. 기술 스택 (의존성 전체)

| 계층 | 기술 | 버전 | 역할 |
|------|------|------|------|
| 언어 | Python | 3.11+ | 전체 백엔드 |
| DB | SQLite3 | 내장 | 센서로그, 설정, 일지 |
| MQTT | Mosquitto | 2.0+ | ESP32↔PC 통신 |
| MQTT 클라이언트 | paho-mqtt | 2.0+ | Python MQTT |
| 스케줄러 | APScheduler | 3.10+ | 정기 작업 |
| 웹 | FastAPI + Jinja2 | 0.110+ | 대시보드 (선택) |
| 차트 | Chart.js | CDN | 웹 대시보드 차트 |
| 트레이 | pystray + Pillow | latest | 시스템 트레이 아이콘 |
| AI 병해 | ONNX Runtime | 1.17+ | YOLOv8s 추론 |
| AI 시세 | Prophet + LightGBM | latest | 경락가 예측 |
| AI LLM | llama-cpp-python | latest | 로컬 LLM (선택, GPU) |
| 벡터DB | ChromaDB | latest | RAG 농업지식 (선택) |
| HTTP | httpx | latest | 기상청/도매시장 API |
| 카카오톡 | 카카오 채널 API | v2 | 알림톡 + 웹훅 수신 |
| 배포 | PyInstaller | 6.0+ | 단일 .exe 빌드 |
| MCU | Arduino (PlatformIO) | ESP-IDF 5.x | ESP32 펌웨어 |
| MCU 통신 | PubSubClient | 2.8+ | ESP32 MQTT |

> **외부 서비스 가입 필요: 0개**
> 카카오톡 채널은 BerryDoctor Project가 운영하며, 농부는 "친구 추가"만 함

---

## 3. 디렉토리 구조

```
berry-doctor/
├── README.md
├── LICENSE                          # MIT
├── requirements.txt
├── setup.py                         # PyInstaller 빌드 설정
├── main.py                          # 진입점
│
├── engine/
│   ├── __init__.py
│   ├── config.py                    # 설정 관리 (SQLite config 테이블)
│   ├── mqtt_broker.py               # Mosquitto 프로세스 관리
│   ├── mqtt_client.py               # paho-mqtt 구독/발행
│   │
│   ├── rules/
│   │   ├── engine.py                # 룰 엔진 코어
│   │   ├── climate.py               # 온습도 제어 규칙
│   │   ├── nutrient.py              # 관비 EC 기반 제어 (PID)
│   │   ├── frost.py                 # 동해 예측 + 선제 보온
│   │   ├── light.py                 # 광량 보상 보광 제어
│   │   ├── flood.py                 # 침수 3단계 방어
│   │   └── disease_risk.py          # 온도×습도×잎젖음→발생확률
│   │
│   ├── scheduler/
│   │   ├── jobs.py                  # APScheduler 작업 등록
│   │   ├── weather.py               # 기상청 API (매 시간)
│   │   ├── farmmap.py               # 팜맵 농업기상 API
│   │   ├── market.py                # 도매시장 경락가 (매일 06:00)
│   │   ├── camera.py                # ESP32-CAM 촬영 (매일 10:00)
│   │   ├── daily_report.py          # 일일 리포트 (매일 21:00)
│   │   └── sensor_health.py         # 센서 헬스체크 (매 5분)
│   │
│   ├── ai/
│   │   ├── disease_detector.py      # YOLOv8s ONNX 추론
│   │   ├── disease_predictor.py     # 환경 기반 발생 확률 모델
│   │   ├── knowledge_graph.py       # 품종·생육단계 Knowledge Graph
│   │   ├── price_forecast.py        # 경락가 예측
│   │   ├── yield_estimator.py       # 수확량 예측 (Phase 3+)
│   │   └── coach.py                 # "딸기 코치" 대화 엔진
│   │
│   ├── kakao/
│   │   ├── webhook.py               # 카카오톡 수신 (Flask 미니서버)
│   │   ├── sender.py                # 알림톡 발송
│   │   ├── commands.py              # 명령어 파싱
│   │   └── templates.py             # 메시지 템플릿
│   │
│   ├── db/
│   │   ├── sqlite.py                # SQLite CRUD
│   │   ├── schema.sql               # 테이블 정의
│   │   └── migrations.py            # 버전 업 시 스키마 변경
│   │
│   ├── web/
│   │   ├── app.py                   # FastAPI 앱
│   │   ├── routes.py                # API 라우트
│   │   └── templates/               # Jinja2 HTML
│   │       ├── dashboard.html
│   │       ├── history.html
│   │       ├── settings.html
│   │       └── diary.html
│   │
│   └── tray/
│       ├── icon.py                  # pystray 시스템 트레이
│       └── assets/                  # 아이콘 파일 (green/yellow/red)
│
├── models/                          # 사전학습 AI 모델 (배포 포함)
│   ├── berry-disease-v1.onnx        # YOLOv8s 딸기 병해 7종+정상
│   ├── berry-disease-v1.yaml        # 클래스 정의
│   ├── class_labels_ko.json         # 한국어 병명 매핑
│   └── price_model.pkl              # 경락가 예측 모델
│
├── data/                            # 내장 데이터 (배포 포함)
│   ├── knowledge_graph.json         # 품종·생육단계·환경 요구 매핑
│   ├── farmer_tips.json             # 고수 농부 노하우 DB
│   ├── pesticide_db.json            # 한국 등록 농약 DB (딸기)
│   ├── subsidy_db.json              # 보조금·지원사업 DB
│   ├── regional_profiles.json       # 지역별 기본값 프리셋
│   └── seolhyang_calendar.json      # 설향 생육 캘린더
│
├── firmware/                        # ESP32 PlatformIO 프로젝트
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp                 # 메인 루프
│       ├── sensors.h/.cpp           # 센서 읽기
│       ├── mqtt.h/.cpp              # MQTT 발행/구독
│       ├── relays.h/.cpp            # 릴레이 제어
│       ├── local_rules.h/.cpp       # PC 없이 독립 동작 룰 5개
│       ├── data_buffer.h/.cpp       # WiFi 끊김 시 SPIFFS 버퍼
│       ├── calibration.h/.cpp       # 센서 자동 보정
│       ├── watchdog.h/.cpp          # 릴레이 안전 타임아웃
│       └── config.h                 # GPIO 핀맵, WiFi 설정
│
├── i18n/                            # 다국어 (초기 한국어만)
│   ├── ko.json
│   ├── ja.json                      # (예정)
│   └── en.json                      # (예정)
│
├── tests/
│   ├── test_rules.py
│   ├── test_disease_detector.py
│   ├── test_kakao_commands.py
│   └── test_sensor_health.py
│
└── docs/
    ├── INSTALL_FARMER.md            # 농부용 설치 가이드 (한국어)
    ├── INSTALL_DEV.md               # 개발자용 설치 가이드
    ├── HARDWARE_BOM.md              # 부품 목록 + 구매처
    ├── WIRING_GUIDE.md              # 배선도 + 사진
    └── API_REFERENCE.md             # 내부 API 문서
```

---

## 4. 모듈별 상세 명세

### 4.1 main.py — 진입점

```python
"""
딸기박사 메인 진입점
더블클릭 실행 → 전체 서비스 자동 시작
"""

# 실행 순서:
# 1. SQLite DB 초기화 (berry.db 없으면 schema.sql로 생성)
# 2. config 로드 (첫 실행 시 setup_wizard 실행)
# 3. Mosquitto 프로세스 시작 (localhost:1883)
# 4. MQTT 클라이언트 연결 + 구독 (sensor/#, command/#)
# 5. 룰 엔진 초기화 (regional_profile 로드)
# 6. AI 모델 로드 (ONNX, Knowledge Graph)
# 7. APScheduler 시작 (정기 작업 등록)
# 8. 카카오톡 웹훅 리스너 시작
# 9. FastAPI 웹서버 시작 (localhost:8080)
# 10. 시스템 트레이 아이콘 표시
# 11. Windows 절전 방지 설정 (SetThreadExecutionState)
```

### 4.2 setup_wizard — 최초 실행 마법사

```
첫 실행 시 GUI 창 (tkinter 최소):
┌────────────────────────────────┐
│    🍓 딸기박사 초기 설정         │
│                                │
│  농장 위치: [서산시 부석면 ▼]    │  ← 시군구 선택
│  하우스 수: [3] 동              │
│  품종: [설향 ▼]                 │  ← 설향/금실/매향/기타
│  재배 방식: [토경 ▼]            │  ← 토경/수경
│  WiFi SSID: [____________]     │
│  WiFi 비밀번호: [____________]  │
│                                │
│       [설정 완료]               │
└────────────────────────────────┘

→ regional_profiles.json에서 "서산시 부석면" 프리셋 로드
→ 설향 생육 캘린더 활성화
→ ESP32 펌웨어용 WiFi 설정 파일 생성
```

### 4.3 regional_profiles.json — 지역 프로필

```json
{
  "서산시_부석면": {
    "type": "coastal",
    "description": "천수만 반도형, 해양성 기후, 해풍 유입",
    "weather_station": "서산(129)",
    "farmmap_grid": "3614025",
    "thresholds": {
      "humidity_warning": 80,
      "humidity_critical": 88,
      "frost_warning_temp": -5,
      "soil_ec_max": 0.7,
      "flood_sensor_warn_cm": 5,
      "flood_sensor_critical_cm": 10,
      "light_target_umol": 150
    },
    "notes": [
      "해풍으로 인해 내륙 대비 습도가 5~10% 높음",
      "겨울철 염분 유입 주의 — 토양 EC 0.7 이상 시 관수로 세척",
      "천수만 인접 → 호우 시 배수 불량 가능성 높음",
      "겨울 일조량이 내륙(논산 등) 대비 부족할 수 있음"
    ]
  },
  "논산시": {
    "type": "inland",
    "thresholds": {
      "humidity_warning": 85,
      "frost_warning_temp": -3,
      "soil_ec_max": 1.0,
      "flood_sensor_warn_cm": 8,
      "light_target_umol": 150
    }
  }
}
```

### 4.4 rules/engine.py — 룰 엔진

```python
"""
룰 엔진 코어
센서 데이터 수신 → 조건 평가 → 액션 실행 → 알림 발송

모든 룰은 다음 구조:
{
  "id": "RULE_HIGH_HUMIDITY",
  "condition": "humidity > threshold.humidity_warning",
  "action": "relay/vent/on",
  "duration_min": 30,
  "alert": True,
  "alert_template": "humidity_warning",
  "cooldown_min": 15,
  "explain": "부석면은 해풍으로 습도가 높아 {threshold}% 넘으면 잿빛곰팡이 위험이 올라가요."
}
"""

# 기본 룰 목록 (우선순위 순):
# 1. FROST_EMERGENCY: 외기온 < frost_warning_temp → 보온커튼 닫기
# 2. HIGH_TEMP_EMERGENCY: 실내온 > 30°C → 환풍기 ON + 측창 개방
# 3. FLOOD_EMERGENCY: 수위 > critical_cm → 배수펌프 ON + 긴급 알림
# 4. HIGH_HUMIDITY: 습도 > warning → 환풍기 ON (30분)
# 5. DISEASE_RISK: disease_predictor > 70% → 환기 강화 + 알림
# 6. LOW_LIGHT: 조도 < target × 0.5 → 보광등 ON (자연광 복구 시 OFF)
# 7. LOW_SOIL_MOISTURE: 토양수분 < 40% → 관수 추천 알림
# 8. HIGH_SOIL_EC: 토양 EC > max → 세척관수 추천 알림
# 9. NIGHT_TEMP: 야간 + 실내온 > 15°C → 환기 권장 (도장 방지)
# 10. DAILY_SCHEDULE: 생육 캘린더 기반 일일 작업 알림
```

### 4.5 rules/disease_risk.py — 병해 발생 확률 모델

```python
"""
환경 기반 병해 발생 확률 예측
Kim et al. (2018) General Infection Model 기반

입력: 온도, 습도, 잎 젖음 시간(추정), 연속 고습 시간
출력: 질병별 발생 확률 (0~100%)

설향 주요 병해 5종:
1. 잿빛곰팡이 (Botrytis cinerea)
   - 최적: 20~25°C + 습도 >90% + 잎젖음 >6h
   - 위험 시작: 습도 >80% (부석면 해양성 보정)
   
2. 흰가루병 (Powdery mildew)
   - 최적: 15~25°C + 습도 40~70% + 건조/습윤 반복
   - 특이: 너무 습하면 오히려 감소
   
3. 탄저병 (Anthracnose)
   - 최적: 25~30°C + 고습 + 비 맞은 후
   - 주 발생기: 육묘기(여름)
   
4. 시들음병 (Fusarium wilt)
   - 토양 전염 → 토양온도 25~30°C에서 활성화
   - 연작 시 급증
   
5. 잎마름병 (Leaf blight)
   - 고온다습 조건 + 과밀 식재
"""

def calculate_disease_risk(temp, humidity, wet_hours, soil_temp, profile):
    """
    Returns: {
        "botrytis": {"risk": 72, "level": "high", "action": "환기 필요"},
        "powdery_mildew": {"risk": 15, "level": "low", "action": "현재 안전"},
        ...
    }
    """
    # 부석면 보정: humidity_offset = +5 (해풍 습도 보정)
    pass
```

### 4.6 ai/coach.py — 딸기 코치 대화 엔진

```python
"""
"딸기 코치" — 센서 데이터 + AI 진단 + 고수 노하우를 조합하여
농부에게 친절하게 설명하는 대화 엔진

동작 모드:
1. 자동 알림: 룰 엔진 트리거 시 → 원인 + 대처 + 고수 팁 포함
2. 질문 응답: 농부가 카톡으로 질문 → Knowledge Graph + 노하우 DB 검색
3. 사진 진단: 이미지 수신 → YOLO 추론 → 병명 + 약제 + 주의사항

응답 원칙:
- 전문 용어 최소화, 농부 눈높이 평어체
- 센서 수치를 "22°C" 대신 "지금 하우스 안이 22도예요" 식으로
- 모든 알림에 "왜?" + "어떻게?" + "고수는?"
- 확신도 70% 미만이면 "정확하지 않을 수 있어요. 직접 확인 부탁드려요" 추가
"""

# 메시지 템플릿 예시:
TEMPLATES = {
    "humidity_warning": {
        "title": "⚠️ {house_name} 습도 주의",
        "body": (
            "지금 습도가 {humidity}%예요.\n"
            "{region_note}\n\n"
            "💡 고수 팁: \"{farmer_tip}\"\n\n"
            "→ 환풍기를 {duration}분 돌리는 게 좋겠어요.\n"
            "자동으로 켤까요? '환풍기 켜'라고 답해주세요."
        )
    },
    "disease_photo_result": {
        "title": "📸 병해 진단 결과",
        "body": (
            "분석 결과: **{disease_name}** (확신도 {confidence}%)\n\n"
            "🔍 증상: {symptoms}\n"
            "💊 추천 약제: {pesticide_name} ({dilution}배 희석)\n"
            "⚠️ 안전사용기준: 수확 {phi_days}일 전까지만 사용\n\n"
            "💡 고수 팁: \"{farmer_tip}\"\n\n"
            "{low_confidence_note}"
        )
    },
    "daily_report": {
        "title": "📋 {date} 일일 리포트",
        "body": (
            "오늘의 하우스 상태:\n"
            "{house_summary}\n\n"
            "📅 생육 단계: {growth_stage} ({days_since_plant}일째)\n"
            "🌡 오늘 평균: {avg_temp}°C / 습도 {avg_humidity}%\n"
            "💰 설향 시세: {price}원/kg ({price_change})\n\n"
            "📝 내일 할 일:\n{tomorrow_tasks}"
        )
    }
}
```

### 4.7 data/farmer_tips.json — 고수 노하우 DB

```json
{
  "tips": [
    {
      "id": "TIP_001",
      "category": "disease",
      "disease": "botrytis",
      "trigger": "humidity > 80",
      "tip": "잿빛곰팡이는 꽃에서 먼저 와요. 시든 꽃잎을 매일 제거하면 전염을 크게 줄일 수 있어요.",
      "source": "논산 15년차 농부 경험",
      "growth_stages": ["flowering", "fruiting"]
    },
    {
      "id": "TIP_002",
      "category": "temperature",
      "trigger": "night_temp > 13",
      "tip": "설향은 야간 온도가 13도 넘으면 줄기만 웃자라요. 8~10도가 딱 좋아요. 차라리 좀 춥게 두세요.",
      "source": "상주 12년차 농부 경험",
      "growth_stages": ["vegetative", "flower_bud"]
    },
    {
      "id": "TIP_003",
      "category": "watering",
      "trigger": "soil_moisture < 50",
      "tip": "토경 설향은 아침 일찍 관수하고 낮에 말리는 게 좋아요. 저녁 관수하면 밤새 과습되면서 곰팡이 올 수 있어요.",
      "source": "밀양 10년차 농부 경험",
      "growth_stages": ["all"]
    },
    {
      "id": "TIP_004",
      "category": "light",
      "trigger": "low_light_consecutive_days > 3",
      "tip": "흐린 날 3일 넘으면 꽃눈 형성이 늦어져요. 보광등 없으면 최소한 비닐 청소라도 해서 광투과율을 올려보세요.",
      "source": "농진청 딸기 재배 매뉴얼",
      "growth_stages": ["flower_bud", "flowering"]
    },
    {
      "id": "TIP_005",
      "category": "salt",
      "trigger": "soil_ec > 0.7",
      "tip": "해안가 하우스는 겨울 해풍에 염분이 쌓여요. 맑은 날 관수량을 20% 늘려서 염류를 씻어내 주세요.",
      "source": "서산 해안가 농가 경험",
      "growth_stages": ["all"],
      "regions": ["coastal"]
    },
    {
      "id": "TIP_006",
      "category": "harvest",
      "trigger": "harvest_season",
      "tip": "설향은 80% 착색됐을 때 따는 게 상품성이 최고예요. 100% 빨갛게 되면 유통 중에 물러져요.",
      "source": "진천 수출농가 경험",
      "growth_stages": ["harvest"]
    },
    {
      "id": "TIP_007",
      "category": "flood",
      "trigger": "heavy_rain_forecast",
      "tip": "비 오기 전에 배수로를 한 번 쓸어주세요. 낙엽이나 흙이 막혀 있으면 물이 안 빠져요. 5분이면 돼요.",
      "source": "서산 부석면 농가 경험",
      "growth_stages": ["all"],
      "regions": ["coastal", "lowland"]
    }
  ]
}
```

### 4.8 data/pesticide_db.json — 등록 농약 DB (딸기)

```json
{
  "source": "농약안전정보시스템 psis.rda.go.kr",
  "last_updated": "2026-03",
  "crop": "딸기",
  "entries": [
    {
      "disease": "botrytis",
      "disease_ko": "잿빛곰팡이병",
      "pesticides": [
        {
          "name": "프로피네브 수화제",
          "dilution": 500,
          "phi_days": 3,
          "max_applications": 3,
          "note": "수확 3일 전까지 사용 가능"
        },
        {
          "name": "이프로디온 수화제",
          "dilution": 1000,
          "phi_days": 7,
          "max_applications": 3,
          "note": "내성 발현 주의 — 교호 살포 권장"
        }
      ]
    },
    {
      "disease": "powdery_mildew",
      "disease_ko": "흰가루병",
      "pesticides": [
        {
          "name": "트리플루미졸 수화제",
          "dilution": 3000,
          "phi_days": 1,
          "max_applications": 4,
          "note": "초기 발생 시 효과적"
        }
      ]
    }
  ]
}
```

---

## 5. 하드웨어 BOM (서산 부석면 3동 기준)

### 5.1 Phase 1: 모니터링 (1동당)

| # | 부품 | 모델/파트넘버 | 수량 | 단가 | 비고 |
|---|------|-------------|------|------|------|
| 1 | 메인 MCU | ESP32-WROOM-32D DevKitC V4 | 1 | 8,000 | |
| 2 | 실내 온습도 | DHT22 (AM2302) | 1 | 4,500 | |
| 3 | 실외 온습도 | DHT22 (AM2302) | 1 | 4,500 | |
| 4 | 토양수분 | Capacitive Soil Moisture v2.0 (HW-390, TLC555I 칩) | 2 | 3,000 | IP65 방수형 권장 |
| 5 | 토양온도 | DS18B20 방수프로브 | 1 | 3,000 | |
| 6 | 조도 | BH1750FVI (GY-302) | 1 | 2,500 | |
| 7 | 엽면습도 (선택) | 저항식 엽면센서 | 1 | 3,000 | 병해 예측 정확도↑ |
| 8 | 방수케이스 | IP65 ABS 158×90×60mm | 1 | 6,000 | |
| 9 | 전원 | USB-C 5V 2A 어댑터 | 1 | 5,000 | |
| 10 | 케이블+저항 | 실리콘 3심 5m ×2 + 4.7kΩ ×5 | 1 | 5,000 | |
| | | | | **1동 소계** | **47,500** |

### 5.2 Phase 2: 제어 추가 (1동당)

| # | 부품 | 모델 | 수량 | 단가 | 비고 |
|---|------|------|------|------|------|
| 11 | 릴레이 | 4CH 5V 옵토 HW-316 | 1 | 4,500 | 수동 오버라이드 스위치 필수 |
| 12 | 수위센서 | XKC-Y25-T12V 비접촉 | 1 | 5,000 | 배수구 |
| 13 | MOSFET | IRF520N 모듈 | 1 | 2,000 | 12V 장비용 |
| 14 | 다이오드 | 1N4007 ×4 | 1 | 800 | 역기전력 보호 |
| 15 | 터미널+퓨즈 | 스크류터미널 + 인라인퓨즈 3A | 1 | 3,500 | |
| | | | | **1동 추가** | **15,800** |

### 5.3 Phase 3: AI 카메라 (3동 공용 1대)

| # | 부품 | 모델 | 수량 | 단가 | 비고 |
|---|------|------|------|------|------|
| 16 | AI 카메라 | ESP32-CAM (OV2640) | 1 | 9,000 | 이동식, 동별 순회 가능 |
| 17 | microSD | 32GB Class 10 | 1 | 8,000 | |
| 18 | 마운트 | L브라켓 + 클램프 | 1 | 3,000 | |
| | | | | **소계** | **20,000** |

### 5.4 전체 비용 요약

| 구성 | 3동 합계 | 비고 |
|------|---------|------|
| Phase 1 (모니터링) | **142,500원** | 3동 × 47,500 |
| Phase 2 (제어) | **47,400원** | 3동 × 15,800 |
| Phase 3 (AI 카메라) | **20,000원** | 공용 1대 |
| 12V SMPS (공용) | **12,000원** | |
| WiFi 중계기 (필요 시) | **10,000원** | |
| **전체 합계** | **약 232,000원** | |

---

## 6. ESP32 펌웨어 명세

### 6.1 GPIO 핀맵 (config.h)

```cpp
// === 센서 입력 ===
#define PIN_DHT22_INDOOR    4     // 실내 온습도
#define PIN_DHT22_OUTDOOR   5     // 실외 온습도
#define PIN_DS18B20_BUS     15    // 1-Wire 버스 (토양온도)
#define PIN_I2C_SDA         21    // BH1750 SDA
#define PIN_I2C_SCL         22    // BH1750 SCL
#define PIN_SOIL_MOISTURE_1 34    // 토양수분 #1 (ADC1)
#define PIN_SOIL_MOISTURE_2 35    // 토양수분 #2 (ADC1)
#define PIN_LEAF_WETNESS    36    // 엽면습도 (ADC1, 선택)
#define PIN_WATER_LEVEL     39    // 수위센서 (ADC1)

// === 릴레이 출력 ===
#define PIN_RELAY_VENT      12    // 환풍기
#define PIN_RELAY_CURTAIN   13    // 보온커튼
#define PIN_RELAY_LIGHT     14    // LED 보광등
#define PIN_RELAY_SPARE     27    // 예비 (CO2 또는 배수펌프)

// === MOSFET 출력 ===
#define PIN_MOSFET_PUMP     25    // 관수펌프/솔레노이드
#define PIN_MOSFET_DRAIN    26    // 배수펌프 (침수 시)

// === 설정 ===
#define SENSOR_READ_INTERVAL_MS  5000   // 5초
#define MQTT_PUBLISH_INTERVAL_MS 10000  // 10초
#define WATCHDOG_TIMEOUT_MS      1800000 // 30분
#define DATA_BUFFER_MAX_ENTRIES  1000    // WiFi 끊김 시 저장
```

### 6.2 로컬 룰 5개 (PC 없이 독립 동작)

```cpp
// local_rules.cpp
// PC(berry-engine) 연결 끊김 시 ESP32가 독립 실행하는 안전 룰

void checkLocalRules(SensorData &data, Config &cfg) {
    
    // RULE 1: 동해 방지 (최우선)
    if (data.outdoor_temp < cfg.frost_warning_temp) {
        activateRelay(PIN_RELAY_CURTAIN, ON);
        sendMQTTAlert("FROST_LOCAL", data.outdoor_temp);
    }
    
    // RULE 2: 고온 환기
    if (data.indoor_temp > 30.0) {
        activateRelay(PIN_RELAY_VENT, ON, 30 * 60); // 30분
    }
    
    // RULE 3: 고습 환기 (부석면 해양성 보정: 80%)
    if (data.humidity > cfg.humidity_warning) {
        activateRelay(PIN_RELAY_VENT, ON, 30 * 60);
    }
    
    // RULE 4: 침수 긴급 배수
    if (data.water_level > cfg.flood_critical_cm) {
        activateRelay(PIN_MOSFET_DRAIN, ON);
        sendMQTTAlert("FLOOD_LOCAL", data.water_level);
    }
    
    // RULE 5: 릴레이 안전 타임아웃 (워치독)
    checkWatchdogTimeouts(); // 30분 초과 ON 상태 → 강제 OFF
}
```

### 6.3 WiFi 끊김 시 데이터 버퍼

```cpp
// data_buffer.cpp
// WiFi/MQTT 연결 끊김 시 SPIFFS에 센서 데이터 저장
// 복구 시 일괄 전송

void bufferSensorData(SensorData &data) {
    if (!mqttConnected()) {
        // SPIFFS에 JSON 라인 추가
        File f = SPIFFS.open("/buffer.jsonl", FILE_APPEND);
        f.println(data.toJSON());
        f.close();
        buffered_count++;
    }
}

void flushBuffer() {
    if (mqttConnected() && buffered_count > 0) {
        File f = SPIFFS.open("/buffer.jsonl", FILE_READ);
        while (f.available()) {
            String line = f.readStringUntil('\n');
            mqtt.publish("sensor/buffered", line.c_str());
            delay(50); // 과부하 방지
        }
        f.close();
        SPIFFS.remove("/buffer.jsonl");
        buffered_count = 0;
    }
}
```

### 6.4 센서 자동 보정 (calibration.cpp)

```cpp
// 초기 설정 시 카카오톡으로 가이드:
// "센서를 마른 흙에 꽂아주세요" → 3초 대기 → dry_value 저장
// "센서를 젖은 흙에 꽂아주세요" → 3초 대기 → wet_value 저장
// → 자동으로 0~100% 매핑 완료

struct CalibrationData {
    int dry_value;    // ADC 건조 상태
    int wet_value;    // ADC 습윤 상태
    bool calibrated;
};

int readMoisturePercent(int raw, CalibrationData &cal) {
    if (!cal.calibrated) return -1; // 미보정
    int percent = map(raw, cal.dry_value, cal.wet_value, 0, 100);
    return constrain(percent, 0, 100);
}
```

---

## 7. 카카오톡 봇 전체 명령어

| 명령 | 동작 | 응답 예시 |
|------|------|----------|
| `상태` | 전동 최신 센서값 | "1동 22°C/65% ✅ / 2동 24°C/82% ⚠️ / 3동 21°C/60% ✅" |
| `1동 상태` | 특정 동 상세 | 온도/습도/토양수분/조도/병해위험도 전체 |
| `환풍기 켜` | 전동 환풍기 ON | "✅ 전체 환풍기 ON (30분 후 자동 OFF)" |
| `2동 환풍기 켜` | 특정 동 | "✅ 2동 환풍기 ON" |
| `커튼 닫아` | 보온커튼 | "✅ 전체 보온커튼 닫기" |
| `보광 켜` | LED 보광등 | "✅ 보광등 ON (자연광 복구 시 자동 OFF)" |
| `물 줘` | 관수 펌프 | "✅ 관수 시작 (설정량 완료 후 자동 정지)" |
| `사진` | ESP32-CAM 촬영 | [최근 촬영 이미지 전송] |
| `진단` + 사진 | YOLO 분석 | 병명 + 약제 + 고수팁 |
| `오늘 할일` | 일일 작업 추천 | 생육단계+기상+센서 기반 |
| `시세` | 경락가 조회 | "설향 특품 8,200원/kg (+300원)" |
| `출하` | 출하 추천 | "이번 주 목요일 추천 (가격 상승 예상)" |
| `보조금` | 지원사업 매칭 | "신청 가능: ICT융복합 (마감 4/30)" |
| `기록 농약 프로피네브` | 살포 기록 | "✅ 프로피네브 살포 기록 완료 (잔류기간 3일)" |
| `기록 수확 30kg` | 수확 기록 | "✅ 30kg 기록 (이번 달 누적 180kg)" |
| `리포트` | 월간 리포트 | 수확량/매출/비용/병해 발생 이력 요약 |
| `목표온도 22` | 설정 변경 | "✅ 주간 목표온도 22°C로 변경" |
| `도움말` | 전체 명령어 | 명령어 목록 카드형 전송 |

---

## 8. AI 모델 학습 파이프라인 (사전 빌드)

### 8.1 병해 진단 모델

```bash
# 1. 데이터 준비
# Kaggle: "Strawberry Disease Detection Dataset" (2,958장, 7클래스+정상)
# Roboflow: 추가 4,918장
# 증강: flip/rotate/brightness → 총 ~15,000장

# 2. 학습
yolo detect train \
  model=yolov8s.pt \
  data=strawberry_disease.yaml \
  epochs=100 \
  imgsz=640 \
  batch=16 \
  device=0

# 3. ONNX 변환
yolo export model=best.pt format=onnx opset=17 simplify=True

# 4. 검증
# 목표: mAP50 ≥ 0.90, 추론시간 < 200ms (CPU)

# 5. 배포: models/berry-disease-v1.onnx → 딸기박사.exe에 포함
```

### 8.2 클래스 정의 (berry-disease-v1.yaml)

```yaml
names:
  0: angular_leaf_spot    # 세균모무늬병
  1: anthracnose          # 탄저병
  2: blossom_blight       # 꽃마름병
  3: gray_mold            # 잿빛곰팡이병
  4: leaf_spot            # 점무늬병
  5: powdery_mildew_fruit # 흰가루병(과실)
  6: powdery_mildew_leaf  # 흰가루병(잎)
  7: healthy              # 정상
```

---

## 9. 외부 API 연동

| API | 엔드포인트 | 주기 | 용도 |
|-----|----------|------|------|
| 기상청 초단기예보 | api.openweathermap.org 또는 data.kma.go.kr | 매 시간 | 동해/고온/호우 예측 |
| 팜맵 농업기상 | data.go.kr/15058627 | 매 시간 | 농경지 기반 정밀 기상 |
| 가락시장 경락가 | data.go.kr (공영도매시장) | 매일 06:00 | 설향 시세 + 예측 |
| 농약안전정보 | psis.rda.go.kr | 월 1회 갱신 | 등록 농약 DB 업데이트 |

> 모든 API는 공공데이터포털 무료 API키 사용 (BerryDoctor Project가 발급, 농부 발급 불필요)

---

## 10. SQLite 스키마 (schema.sql)

```sql
-- 센서 로그 (5초 간격, 자동 삭제: 90일)
CREATE TABLE sensor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER NOT NULL,          -- 1, 2, 3
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
CREATE TABLE farm_diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    entry_type TEXT,   -- 'note', 'spray', 'harvest', 'fertilize', 'plant', 'other'
    content TEXT,
    auto_generated BOOLEAN DEFAULT 0
);

-- 농약 살포 기록 (GAP 인증용)
CREATE TABLE spray_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    pesticide_name TEXT,
    target_disease TEXT,
    dilution INTEGER,
    phi_days INTEGER,        -- 수확전 사용일수
    safe_harvest_date DATE   -- 자동 계산
);

-- 수확 기록
CREATE TABLE harvest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    weight_kg REAL,
    grade TEXT,              -- '특', '상', '보통'
    sale_price_per_kg REAL,
    note TEXT
);

-- 알림 이력
CREATE TABLE alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    house_id INTEGER,
    rule_id TEXT,
    severity TEXT,            -- 'info', 'warning', 'critical'
    message TEXT,
    action_taken TEXT,
    acknowledged BOOLEAN DEFAULT 0
);

-- 설정
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 생육 단계 이력
CREATE TABLE growth_stage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id INTEGER,
    stage TEXT,               -- 'planting', 'vegetative', 'flower_bud', ...
    started_at DATETIME,
    ended_at DATETIME,
    auto_detected BOOLEAN DEFAULT 1
);
```

---

## 11. 빌드 및 배포

### 11.1 개발 환경

```bash
# 1. 레포 클론
git clone https://github.com/sinmb79/berry-doctor.git
cd berry-doctor

# 2. 가상환경
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성
pip install -r requirements.txt

# 4. 개발 실행
python main.py
```

### 11.2 PyInstaller 빌드 (.exe)

```bash
pyinstaller --onefile --windowed \
  --add-data "models;models" \
  --add-data "data;data" \
  --add-data "i18n;i18n" \
  --add-binary "mosquitto.exe;." \
  --icon "assets/berry-doctor.ico" \
  --name "딸기박사" \
  main.py
```

### 11.3 ESP32 펌웨어 빌드

```bash
cd firmware
pio run --target upload --upload-port COM3
```

---

## 12. Phase 로드맵

| Phase | 기간 | 범위 | 산출물 |
|-------|------|------|--------|
| **0** | 4주 | 카카오톡 봇 + YOLO 병해진단 + 기상 알림 (센서 없이) | berry-engine MVP + .exe |
| **1** | +4주 | ESP32 센서 연동 + 실시간 모니터링 + 룰 엔진 | 펌웨어 v1 + 3동 설치 |
| **2** | +4주 | 릴레이 제어 + 침수방어 + 보광 자동화 | Phase 2 하드웨어 설치 |
| **3** | +4주 | 병해 예측 모델 + 시세 예측 + 딸기 코치 | AI 고도화 |
| **4** | +4주 | GAP 기록 + 수확량 추적 + 월간 리포트 | 경영 관리 기능 |
| **5** | +4주 | 파일럿 농가 농장 1시즌 실증 + 피드백 반영 | v1.0 공개 릴리즈 |

### Phase 0 MVP Codex 지시 (최우선)

```
구현 순서:
1. main.py + setup_wizard (tkinter)
2. db/sqlite.py + schema.sql
3. mqtt_broker.py (Mosquitto 자동 실행)
4. ai/disease_detector.py (ONNX 추론)
5. kakao/webhook.py + sender.py + commands.py
6. scheduler/weather.py (기상청 API)
7. scheduler/daily_report.py
8. tray/icon.py
9. PyInstaller 빌드 → 딸기박사.exe

테스트:
- 카카오톡으로 딸기 사진 보내기 → 병해 진단 응답
- "상태" 입력 → 기상 데이터 응답
- "오늘 할일" → 작업 추천 응답
- 매일 21시 → 일일 리포트 자동 발송
```

---

## 13. 안전 및 주의사항

1. AC 220V 릴레이 배선은 **전기공사기사 자격자**가 시공
2. 모든 릴레이에 **하드웨어 워치독** (30분 타임아웃)
3. 릴레이 박스에 **수동/자동 전환 물리 스위치** 필수
4. 12V DC 라인에 **인라인 퓨즈 3A** 삽입
5. 센서 케이블은 전원선과 **10cm 이상 이격**
6. 방수 케이스 **IP65 이상** + 실리콘 실링
7. ESP32 **OTA 업데이트** 활성화
8. 센서 **6개월마다 재보정** 알림 (카카오톡)
9. YOLO 진단 **확신도 70% 미만** 시 "전문가 확인 권장" 문구 필수
10. 농약 추천 시 반드시 **한국 등록 농약만** 표시 + 안전사용기준 명시

---

## 14. 라이선스

- **소프트웨어**: MIT License
- **하드웨어 설계**: CERN-OHL-P-2.0
- **데이터/문서**: CC BY 4.0
- **AI 모델**: Apache 2.0 (Ultralytics YOLOv8 기반)
- **브랜드**: BerryDoctor Project / The 4th Path

> "기술은 사람을 착취하는 것이 아니라 사람을 섬기는 것이어야 한다."
> P4 := ⟨H⊕A⟩ ↦ Ω

---

*Repository: github.com/sinmb79/berry-doctor*
*Generated by Claude for BerryDoctor Project Codex Handoff*
