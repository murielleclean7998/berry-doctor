# BerryDoctor 아키텍처 상세 문서

이 문서는 BerryDoctor의 내부 구조, 데이터 흐름, 설계 원칙을 개발자와 운영자 관점에서 설명합니다.

---

## 목차

1. [설계 원칙](#1-설계-원칙)
2. [시스템 구성도](#2-시스템-구성도)
3. [프로세스 구조](#3-프로세스-구조)
4. [데이터베이스](#4-데이터베이스)
5. [카카오톡 메시지 처리](#5-카카오톡-메시지-처리)
6. [병해 진단](#6-병해-진단)
7. [날씨와 규칙 엔진](#7-날씨와-규칙-엔진)
8. [센서와 자동 제어](#8-센서와-자동-제어)
9. [센서 데이터 저장 전략](#9-센서-데이터-저장-전략)
10. [보안](#10-보안)
11. [대시보드](#11-대시보드)
12. [스케줄러](#12-스케줄러)
13. [설정 관리](#13-설정-관리)
14. [백업](#14-백업)
15. [펌웨어](#15-펌웨어-esp32)
16. [외부 시그널 수집](#16-외부-시그널-수집)
17. [위성 모니터링](#17-위성-모니터링)
18. [3축 교차검증](#18-3축-교차검증-fusion-intelligence)
19. [야간 보안](#19-야간-보안)
20. [테스트](#20-테스트)
21. [배포](#21-배포)

---

## 1. 설계 원칙

| 원칙 | 구현 |
|------|------|
| **가입 없이 시작** | 카카오톡만 있으면 됨. 설정 마법사가 한 번만 실행 |
| **Graceful Degradation** | ONNX 없으면 휴리스틱, API 키 없으면 모의 데이터, 센서 없으면 날씨 기반 |
| **알림은 이유와 행동을 함께** | 모든 경보에 "왜 위험한지"와 "지금 뭘 해야 하는지"를 포함 |
| **앱 전체는 멈추지 않음** | 외부 API, MQTT, 날씨 모두 실패해도 캐시와 폴백으로 계속 운영 |
| **데이터는 적게, 제어는 정확하게** | 센서 수신은 전부 처리하되, 저장은 샘플링 + 집계로 DB 비대화 방지 |

---

## 2. 시스템 구성도

```
카카오톡 사용자
    │
    │ HTTPS (카카오 API)
    ▼
┌─────────────────────────────────────────────┐
│               BerryDoctor 서버               │
│                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  │
│  │ Flask    │  │ FastAPI   │  │ System   │  │
│  │ Webhook  │  │ Dashboard │  │ Tray     │  │
│  │ :5005    │  │ :8080     │  │ Icon     │  │
│  └────┬─────┘  └─────┬─────┘  └──────────┘  │
│       │              │                       │
│  ┌────▼──────────────▼──────────────────┐   │
│  │         StrawberryCoach              │   │
│  │  (대화 조립 · 진단 · 기록 · 제어)     │   │
│  └────┬──────────────┬──────────────────┘   │
│       │              │                       │
│  ┌────▼────┐   ┌─────▼──────┐               │
│  │ Rule    │   │ SQLite     │               │
│  │ Engine  │   │ Repository │               │
│  └────┬────┘   └────────────┘               │
│       │                                      │
│  ┌────▼──────────────┐                       │
│  │ GreenhouseControl │                       │
│  │ + PID Controller  │                       │
│  └────┬──────────────┘                       │
│       │ MQTT                                 │
└───────┼──────────────────────────────────────┘
        │
        ▼
   ESP32 센서/릴레이
```

---

## 3. 프로세스 구조

`main.py`에서 `BerryDoctorApplication`이 시작되면 아래 스레드가 생성됩니다:

| 스레드 | 구성 요소 | 역할 |
|--------|-----------|------|
| 메인 | `while True: sleep(1)` | Ctrl+C 대기 |
| Flask | `KakaoWebhookServer` | 카카오톡 웹훅 수신 (:5005) |
| FastAPI | `DashboardServer` (Uvicorn) | 웹 대시보드 (:8080) |
| APScheduler | `SchedulerService` | 날씨/시세/리포트/백업 등 자동 작업 |
| PyTray | `TrayController` | Windows 시스템 트레이 아이콘 |
| MQTT | `MQTTClient` (paho) | 센서 데이터 수신, 제어 명령 발행 |
| Mosquitto | `MosquittoBroker` (subprocess) | 로컬 MQTT 브로커 |

### 시작 순서

```
1. DB 초기화 (schema.sql + 마이그레이션)
2. 설정 마법사 (미설정 시)
3. 설정 로드 + 런타임 기본값 보장
4. 서비스 객체 생성
5. 초기 날씨/시세 갱신
6. Mosquitto 브로커 시작
7. MQTT 클라이언트 연결 (sensor/#, camera/# 구독)
8. Flask 웹훅 서버 시작
9. FastAPI 대시보드 시작
10. APScheduler 시작
11. 시스템 트레이 시작
```

### 종료 순서

```
1. 스케줄러 정지
2. Flask 서버 종료
3. FastAPI 서버 종료
4. 트레이 종료
5. MQTT 클라이언트 종료
6. Mosquitto 브로커 종료
```

---

## 4. 데이터베이스

SQLite 단일 파일 (`berry.db`), WAL 모드, `busy_timeout=30000`, `check_same_thread=False`.

### 테이블 목록

| 테이블 | 용도 | 보관 정책 |
|--------|------|-----------|
| `sensor_log` | 센서 원본 (샘플링) | 90일 자동 삭제 |
| `sensor_latest` | 하우스별 최신 센서값 | UPSERT (항상 1행/하우스) |
| `sensor_minute_log` | 분 단위 이동평균 집계 | 365일 자동 삭제 |
| `farm_diary` | 재배 일지 | 영구 |
| `spray_log` | 농약 살포 기록 | 영구 (GAP 인증용) |
| `harvest_log` | 수확 기록 | 영구 |
| `alert_log` | 알림 이력 | 영구 |
| `diagnosis_log` | 사진 진단 이력 | 영구 |
| `control_log` | 장비 제어 이력 | 영구 |
| `market_price_log` | 시세 이력 | 영구 |
| `camera_capture_log` | 카메라 촬영 이력 | 영구 |
| `community_insight` | 현장 인사이트 | 영구 |
| `pilot_feedback` | 시범 농가 피드백 | 영구 |
| `monthly_report_log` | 월간 리포트 | 영구 |
| `config` | 설정 KV 저장소 | 영구 |
| `growth_stage` | 생육 단계 이력 | 영구 |

### 인덱스

```sql
idx_sensor_log_house_timestamp        ON sensor_log (house_id, timestamp DESC)
idx_sensor_minute_log_house_bucket    ON sensor_minute_log (house_id, bucket_minute DESC)
idx_community_insight_source_timestamp ON community_insight (source_site, timestamp DESC)
```

### 마이그레이션

`_run_lightweight_migrations()`에서 기존 DB에 새 컬럼을 자동 추가합니다:
- `sensor_log`: `solution_ec`, `solution_ph`, `nutrient_temp`, `relay_state_json`

---

## 5. 카카오톡 메시지 처리

### 흐름

```
카카오톡 메시지
    │
    ▼
POST /kakao/webhook
    │
    ├── HMAC 서명 검증 (설정된 경우)
    │
    ├── parse_command() → CommandIntent
    │       정규식 매칭 → 의도 + 파라미터 추출
    │       매칭 실패 → "note" (일지로 저장)
    │       이미지만 → "diagnosis"
    │
    ├── handle_intent() → 응답 메시지
    │       StrawberryCoach의 해당 메서드 호출
    │
    └── JSON 응답 반환
```

### 명령어 파서 동작

`commands.py`의 `parse_command()`는 정규식 패턴을 순서대로 매칭합니다:

- `^(\d+)\s*동\s*상태$` → `house_status` (house_id 추출)
- `^기록\s*수확\s*(?:(\d+)\s*동\s*)?(\d+(?:\.\d+)?)kg$` → `record_harvest` (house_id + value 추출)
- 패턴 미매칭 + 이미지 있음 → `diagnosis`
- 패턴 미매칭 + 텍스트만 → `note` (LLM 응답 또는 일지 저장)

### 이미지 처리

3가지 방식을 지원합니다:
1. `image_bytes` (Base64 인코딩) → 디코딩
2. `image_url` → httpx로 다운로드
3. `multipart/form-data`의 `image` 파일

모든 경로에서 실패 시 사용자에게 재전송 요청 메시지를 반환합니다.

---

## 6. 병해 진단

### 3단계 폴백

```
ONNX 모델 (berry-disease-v1.onnx)
    │ 모델 파일 없음 / 추론 실패
    ▼
휴리스틱 (PIL + numpy 픽셀 분석)
    │ numpy 없음
    ▼
파일명 키워드 매핑 → 기본 "healthy"
```

### ONNX 추론

- 입력: 640x640 RGB, float32, CHW, 0~1 정규화
- 출력 파싱: 1D(분류) 또는 2D(탐지) 모두 지원
- 클래스: `data/class_labels_ko.json` (gray_mold, powdery_mildew_leaf 등)

### 휴리스틱

- 128x128 리사이즈 후 평균 밝기, Red 편향도 분석
- 밝기 < 95 → gray_mold (63%)
- Red 편향 < -8 → powdery_mildew_leaf (60%)

### 진단 결과

`DiagnosisResult`에 포함되는 정보:
- 질병명 (한글/영문 키)
- 신뢰도 (%)
- 증상 설명
- 추천 농약 + PHI(수확전사용금지기간)
- 전문가 팁
- 사용된 모델 (onnx/heuristic)
- → `diagnosis_log` 테이블에 자동 저장

---

## 7. 날씨와 규칙 엔진

### 날씨 갱신 (1시간마다)

```
OpenWeatherMap API
    │ API 키 없음 / 요청 실패
    ▼
캐시 (config.weather_cache)
    │ 캐시 없음
    ▼
모의 데이터 (지역 프로필 기반)
```

### 규칙 엔진 (`RuleEngine.evaluate_weather`)

날씨 데이터를 받으면 3가지를 평가합니다:

**1. 동해 경보**
- 조건: `내일 최저기온 < 지역 frost_warning_temp`
- 해안형은 -5도C, 내륙형은 -3도C 등 지역별 차이

**2. 호우 경보**
- 조건: `최대 시간당 강수량 >= heavy_rain_mm_per_hour` (기본 20mm/h)

**3. 질병 위험도** (가우시안 모델)

각 질병별 가중 합산:

| 질병 | 온도 비중 | 습도 비중 | 기타 |
|------|-----------|-----------|------|
| 잿빛곰팡이 | 40% (22도C) | 35% (습도 초과분) | 25% (젖은 시간) |
| 흰가루병 | 45% (20도C) | 35% (60% 최적) | 20% (건조 시간) |
| 탄저병 | 45% (28도C) | 35% (75% 초과분) | 20% (젖은 시간) |
| 시들음병 | 65% (토양 27도C) | 35% (고온 보정) | - |
| 잎마름병 | 45% (26도C) | 35% (78% 초과분) | 20% (젖은 시간) |

- 해안형 지역은 습도에 +5% 보정
- 위험도 >= 70% 이면 경보 발생

---

## 8. 센서와 자동 제어

### MQTT 메시지 수신

```
sensor/{house_id}/data  (JSON)
    │
    ▼
handle_mqtt_message()
    │
    ├── sensor_latest UPSERT (항상)
    ├── sensor_minute_log 이동평균 갱신 (항상)
    ├── sensor_log 원본 저장 (30초 간격)
    │
    └── RuleEngine.evaluate_environment()
        │
        ├── 환기 제안 (습도 >= 경고 임계값)
        ├── 강제 환기 (실내 온도 >= 28도C)
        ├── 보광 제안 (광량 부족)
        ├── 관수 펄스 (토양 수분 < 28)
        ├── 배수 펌프 (수위 >= 0.8 또는 호우)
        ├── CO2 공급 (CO2 < 450ppm)
        │
        └── PID 양액 제어
            ├── EC 오차 >= 0.12 → 농축/희석 펌프
            └── pH 오차 >= 0.25 → 산/염기 펌프
```

### 제어 명령 발행

`GreenhouseController.publish_action()`:

1. **dedupe 검사**: auto 모드에서 같은 (action, device, mode, house_id, payload)가 90초 이내에 있으면 건너뜀
2. **MQTT 발행**: `control/{house_id}/{device}` 토픽으로 JSON 전송
3. **이력 저장**: `control_log` 테이블에 기록

---

## 9. 센서 데이터 저장 전략

5초 간격 센서 데이터를 전부 저장하면 하루 17,280건, 90일이면 약 155만 행이 됩니다.
이를 방지하기 위해 3계층 구조를 사용합니다:

```
모든 MQTT 수신
    │
    ├── sensor_latest (UPSERT, 하우스당 1행)
    │   → 제어 판단과 현재 상태 표시용
    │   → 항상 최신값 유지
    │
    ├── sensor_minute_log (분 단위 이동평균)
    │   → 대시보드 그래프, 추세 분석용
    │   → 365일 보관 후 자동 삭제
    │   → UNIQUE(house_id, bucket_minute)
    │
    └── sensor_log (원본 샘플링)
        → 설정된 간격(기본 30초)마다 1건만 저장
        → 90일 보관 후 자동 삭제
        → 디버깅, 정밀 분석용
```

### 이동평균 계산

```
새 평균 = (기존 평균 * 기존 샘플 수 + 새 값) / (기존 샘플 수 + 1)
```

---

## 10. 보안

### 비밀 보호

| 항목 | 방식 |
|------|------|
| WiFi 비밀번호 | Windows DPAPI 암호화 → `dpapi:base64...` |
| API 키 | Windows DPAPI 암호화 → `dpapi:base64...` |
| 비Windows | Base64 인코딩 → `b64:base64...` (폴백) |
| 설정 화면 표시 | 마스킹 (`abc***ef`) |

### 웹훅 인증

- `webhook_signature_secret` 설정 시 HMAC-SHA256 서명 검증
- `X-Kakao-Signature`, `X-BerryDoctor-Signature`, `X-Signature-256` 헤더 지원
- 서명 비교는 `secrets.compare_digest`로 타이밍 공격 방지

### 대시보드 인증

- **토큰 기반**: 자동 생성된 `dashboard_access_token`으로 인증
- **4가지 인증 경로**:
  1. `Authorization: Bearer <token>` 헤더
  2. `berry_dashboard_token` 쿠키
  3. `X-Dashboard-Token` 헤더
  4. `?access_token=<token>` 쿼리 파라미터
- **CSRF 보호**: Double-Submit Cookie 패턴
  - 쿠키: `berry_dashboard_csrf` (httpOnly=false)
  - 폼: hidden `csrf_token` 필드
  - API: `X-CSRF-Token` 헤더
  - 모든 POST 요청에서 검증

### 중복 방지 (Dedupe)

| 대상 | 기본 윈도우 | 비교 기준 |
|------|-------------|-----------|
| 자동 제어 | 90초 | action + device + mode + house_id + payload_json |
| 알림 | 30분 | rule_id + severity + message + house_id |
| 커뮤니티 인사이트 | 30분 | title + summary + source_site + tags + payload_json |

---

## 11. 대시보드

### HTML 라우트

| 경로 | 설명 | 인증 |
|------|------|------|
| `GET /login` | 로그인 페이지 | 불필요 |
| `POST /login` | 토큰 인증 | 불필요 |
| `GET /logout` | 쿠키 삭제 후 로그인으로 | 불필요 |
| `GET /` | 메인 대시보드 | 필요 |
| `GET /history` | 기록 조회 | 필요 |
| `GET /settings` | 설정 조회/수정 | 필요 |
| `POST /settings` | 설정 저장 | 필요 + CSRF |
| `POST /settings/backup` | 백업 생성 | 필요 + CSRF |
| `GET /diary` | 재배 일지 | 필요 |
| `GET /community` | 커뮤니티 인사이트 | 필요 |
| `POST /community` | 인사이트 추가 | 필요 + CSRF |
| `GET /pilot` | 파일럿 피드백 | 필요 |
| `POST /pilot` | 피드백 추가 | 필요 + CSRF |

### JSON API

| 경로 | 설명 |
|------|------|
| `GET /api/status` | 종합 현황 (날씨, 시세, 알림, 센서, 제어, 수확예측, 백업) |
| `GET /api/sensors/history` | 센서 이력 (분 단위 집계) |
| `GET /api/records/spray` | 농약 기록 |
| `GET /api/records/harvest` | 수확 기록 |
| `GET /api/records/diagnosis` | 진단 기록 |
| `GET /api/control/actions` | 제어 이력 |
| `GET /api/community` | 커뮤니티 인사이트 |
| `POST /api/community` | 인사이트 추가 (CSRF 필요) |
| `GET /api/pilot` | 파일럿 피드백 |
| `POST /api/pilot` | 피드백 추가 (CSRF 필요) |
| `GET /api/settings` | 설정 조회 (비밀 마스킹) |
| `GET /api/backups` | 백업 목록 |
| `POST /api/backups/create` | 백업 생성 (CSRF 필요) |
| `GET /api/backups/latest` | 최신 백업 다운로드 |

---

## 12. 스케줄러

APScheduler (BackgroundScheduler, Asia/Seoul 타임존)로 관리됩니다:

| 작업 | 주기 | 시간 |
|------|------|------|
| 날씨 갱신 + 규칙 평가 | 1시간 | 매시 |
| 시세 갱신 | 1일 | 06:00 |
| 일일 리포트 | 1일 | 21:00 |
| 센서 로그 정리 | 1일 | 03:15 |
| DB 백업 | 1일 | 03:40 |
| 카메라 순회 촬영 | 1일 | 10:00 |
| 월간 리포트 | 1월 | 매월 1일 07:00 |

---

## 13. 설정 관리

### 설정 흐름

```
초기 설정 마법사 (Tkinter)
    │
    └── ConfigManager.save_setup()
        ├── WiFi 비밀번호 DPAPI 암호화
        ├── config 테이블에 저장
        └── firmware/wifi.generated.json 생성

런타임 기본값 보장
    │
    └── ConfigManager.ensure_runtime_defaults()
        ├── dashboard_access_token 자동 생성
        ├── webhook_signature_secret 자동 생성
        └── 각 설정 항목 기본값 확인

대시보드 설정 변경
    │
    └── ConfigManager.update_settings()
        ├── 비밀 키 → DPAPI 암호화 후 저장
        ├── 정수 키 → int 변환
        ├── 불린 키 → bool 변환
        └── reload_runtime_config() → 모든 서비스에 즉시 반영
```

### 런타임 설정 동기화

설정이 변경되면 `reload_runtime_config()`가 호출됩니다:

- 모든 서비스의 `config` 객체를 새 값으로 갱신
- `RuleEngine`의 지역 프로필 갱신
- `DiseasePredictor` 재생성
- 카메라 하우스 수, 백업 보관 개수, dedupe 윈도우 등 즉시 반영

---

## 14. 백업

### 자동 백업

- 매일 03:40에 `BackupService.create_backup()` 실행
- SQLite `backup()` API 사용 (WAL 모드에서 안전)
- `{db_path}/../backups/berry-{YYYYMMDD-HHMMSS}.db` 형태로 저장
- `backup_retention_count` (기본 14) 초과 시 오래된 파일 자동 삭제

### 수동 백업

- 대시보드 설정 화면에서 "백업 생성" 버튼
- API: `POST /api/backups/create`
- 최신 백업 다운로드: `GET /api/backups/latest`

---

## 15. 펌웨어 (ESP32)

`firmware/` 디렉토리에 PlatformIO 기반 ESP32 펌웨어 스캐폴드가 포함되어 있습니다:

| 파일 | 역할 |
|------|------|
| `sensors.cpp/h` | 온습도, 토양, 광량, 수위 센서 읽기 |
| `relays.cpp/h` | 릴레이 6채널 (환풍기, 커튼, 보광, 관수, 배수, CO2) |
| `mqtt.cpp/h` | WiFi 연결 + MQTT 발행/구독 |
| `local_rules.cpp/h` | 오프라인 안전 규칙 (긴급 환기 등) |
| `watchdog.cpp/h` | 하드웨어 워치독 타이머 |
| `security.cpp/h` | 야간 PIR 감지 → IR LED → MQTT 보안 이벤트 |
| `config.h` | 핀 번호, WiFi, MQTT 브로커 주소 |

센서 데이터는 `sensor/{house_id}/data` 토픽으로 JSON 발행되며,
제어 명령은 `control/{house_id}/{device}` 토픽으로 수신합니다.
야간 보안 이벤트는 `security/{house_id}/motion` 토픽으로 발행됩니다.

---

## 16. 외부 시그널 수집

### 소스 4종

| 소스 | 클래스 | 수집 주기 | 설명 |
|------|--------|-----------|------|
| 기상청 특보 | `KMASpecialSource` | 6시간 | 호우/저온 특보를 weather_cache에서 추출 |
| 병해충 예보 | `RDAPestSource` | 6시간 | 농진청 병해충 발생 정보 |
| 시세 급변 | `MarketAlertSource` | 6시간 | 딸기 시세 급등/급락 감지 |
| 커뮤니티 | `CommunitySource` | 실시간 | 다른 농가의 병해 진단 공유 (opt-in) |

### 관련성 분석 (SignalAnalyzer)

수집된 시그널을 우리 농장과의 관련성으로 점수화합니다:

| 기준 | 가산점 | 설명 |
|------|--------|------|
| 딸기 관련 태그 | +0.3 | "딸기", "strawberry" 태그 포함 |
| 같은 시/도 | +0.3 | farm_location과 지역 일치 |
| 환경 조건 유사 | +0.2 | 현재 센서값이 시그널 조건과 유사 |
| 생육 단계 일치 | +0.1 | 현재 생육 단계와 맞음 |

- 관련성 0.3 이하: 무시
- 긴급(critical) + 관련성 0.55 이상: 즉시 카카오톡 발송 (일 2건 제한)
- 나머지: 일일 리포트에 포함

---

## 17. 위성 모니터링

### 데이터 흐름

```
Copernicus Sentinel-2 (매일 06:30 확인)
    │
    ├── 구름량 > 40% → "구름 차단" 메시지
    │
    └── 밴드 다운로드 (B04, B08, B03, B11, SCL)
        │
        ├── NDVI = (NIR - Red) / (NIR + Red)    → 식생 활력
        ├── NDWI = (NIR - SWIR) / (NIR + SWIR)  → 수분 상태
        └── GNDVI = (NIR - Green) / (NIR + Green) → 엽록소
            │
            ├── 이전 촬영 대비 변화량
            ├── 작년 같은 시기 대비 변화량
            ├── 지역 평균 대비 변화량
            │
            └── SatelliteInterpreter → 사람 말로 번역
```

### NDVI 등급

| NDVI | 등급 | 조치 |
|------|------|------|
| >= 0.7 | 좋음 | 없음 |
| >= 0.5 | 보통 | 없음 |
| >= 0.3 | 주의 | 확인 필요 |
| < 0.3 | 위험 | 즉시 점검 |

### 타임라인

`기록` 명령으로 월별 NDVI 추이와 가장 좋았던 시기를 확인할 수 있습니다.
`작년 비교` 명령으로 작년 같은 시기와의 차이를 볼 수 있습니다.

---

## 18. 3축 교차검증 (Fusion Intelligence)

센서, 위성, 외부 시그널이 각각 말하는 것을 모아서 통합 판단합니다.

### 트리거

| 트리거 | 시점 | 동작 |
|--------|------|------|
| `sensor` | 센서 이상 감지 시 | 위성+시그널 데이터를 함께 조회하여 교차검증 |
| `satellite` | 새 위성 촬영 도착 시 | 센서+시그널 데이터를 함께 조회하여 교차검증 |
| `signal` | critical/warning 시그널 수신 시 | 센서+위성 데이터를 함께 조회하여 교차검증 |
| `daily` | 매일 21:00 | 세 축 모두 종합하여 하루 리포트 생성 |

### 합의 판단

```
3축 위험도 각각 60 이상?
    │
    ├── 모두 Yes → "all_agree" (합성 위험도 × 1.3)
    ├── 2개 Yes  → "two_agree" (합성 위험도 × 1.1)
    └── 1개만    → "one_only"  (합성 위험도 × 0.8)
```

### 위험 등급

| 합성 위험도 | 등급 | 동작 |
|-------------|------|------|
| >= 80 | critical | 즉시 카카오톡 경보 |
| >= 60 | warning | 카카오톡 주의 알림 |
| >= 40 | caution | 일일 리포트에 포함 |
| < 40 | info | 기록만 |

### 병합 윈도우

같은 트리거 소스에서 같은 level의 이벤트가 `signal_merge_window_seconds`(기본 3600초) 이내에 반복되면, 새 메시지를 보내지 않고 "비슷한 흐름이 이어지고 있어요"로 병합합니다.

---

## 19. 야간 보안

### ESP32 흐름

```
광량 < 50 lux → NIGHT_MODE 진입
    │
    PIR 센서 HIGH 감지
    │
    ├── IR LED ON (200ms)
    ├── MQTT 발행: security/{house_id}/motion
    ├── 버저 1초 (설정 시)
    └── 쿨다운 30초
```

### 서버 흐름

```
MQTT 수신: security/{house_id}/motion
    │
    ├── SecurityMonitor.on_motion_detected()
    │   ├── security_log 테이블에 저장
    │   └── 카카오톡 경보 발송 (사진 수 포함)
    │
    └── "보안 기록" 명령으로 최근 7일 이벤트 조회
```

---

## 20. 테스트

```bash
python -m unittest discover -s tests -v
```

| 테스트 파일 | 검증 대상 |
|------------|-----------|
| `test_kakao_commands.py` | 명령어 파서 (상태, 수확, 농약, 하우스, 기록/비교/보안) |
| `test_disease_detector.py` | 휴리스틱 폴백 진단 |
| `test_rules.py` | 질병 위험도 계산 |
| `test_repository.py` | DB CRUD, N+1 해소, 진단/농약 이력 |
| `test_phase_features.py` | 시세 예측, 규칙 엔진 제어 제안, 프로필 갱신 |
| `test_security_features.py` | WiFi 암호화/복호화, 웹훅 HMAC, 백업 |
| `test_runtime_hardening.py` | 센서 3계층, 제어 dedupe, CSRF |
| `test_sensor_health.py` | 센서 로그 정리 |
| `test_signal.py` | 시그널 수집, 관련성 분석, 즉시 발송 제한 |
| `test_satellite.py` | NDVI 등급, 위성 관측 저장, 타임라인 요약 |
| `test_fusion.py` | 3축 위험도, 합의 판단, 일일 리포트 |
| `test_security.py` | 야간 보안 이벤트 저장/전달 |

---

## 21. 배포

### PyInstaller 빌드

```bash
python setup.py
```

`dist/딸기박사.exe` 단일 파일이 생성됩니다.

번들에 포함되는 리소스:
- `models/` (ONNX 모델)
- `data/` (시드 데이터)
- `i18n/` (번역 파일)
- `bin/mosquitto/mosquitto.exe` (MQTT 브로커)
- `assets/berry-doctor.ico` (아이콘)

### 실행 환경 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| OS | Windows 10 | Windows 11 |
| Python | 3.11 | 3.12 |
| RAM | 512MB | 2GB |
| 디스크 | 200MB | 1GB (로그 포함) |
| 네트워크 | 카카오톡 API용 | + OpenWeatherMap API |
| 하드웨어 | 없음 (모의 모드) | ESP32 센서 모듈 |
