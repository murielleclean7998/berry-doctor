# BerryDoctor (딸기박사)

> 카카오톡으로 딸기 농장을 관리하는 무료 스마트팜 도우미

작은 딸기 농가는 인력이 부족하고, 기존 스마트팜은 비용이 높아 시작하기 어렵습니다.
**딸기박사**는 농부가 이미 쓰고 있는 카카오톡으로 사진을 보내고 명령을 입력하면, 병해 진단부터 출하 판단까지 바로 답하는 도구입니다.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **병해 진단** | 딸기 사진을 카카오톡으로 보내면 ONNX 모델 또는 휴리스틱으로 진단 결과를 돌려줍니다 |
| **날씨 경보** | 동해, 호우, 질병 위험을 자동 감지하고 카카오톡으로 알려줍니다 |
| **오늘 할일** | 생육 단계와 날씨를 보고 오늘 해야 할 작업 3가지를 추천합니다 |
| **수확/농약 기록** | `기록 수확 30kg`, `기록 농약 프로피네브` 같은 명령으로 이력을 관리합니다 |
| **안전출하일 확인** | 출하 명령 시 최근 농약 살포의 안전출하일을 자동으로 확인합니다 |
| **시세/보조금** | 딸기 시세 동향과 정부 보조금 정보를 조회합니다 |
| **센서 연동** | MQTT로 하우스별 온습도, 토양, 양액 데이터를 수집하고 자동 제어를 제안합니다 |
| **대시보드** | 웹 대시보드에서 전체 현황, 기록, 설정을 한눈에 볼 수 있습니다 |
| **일일/월간 리포트** | 매일 21시 요약 리포트, 매월 1일 월간 리포트를 자동 발송합니다 |
| **외부 시그널** | 기상특보, 병해충예보, 시세급변 등 외부 정보를 수집하고 우리 농장과의 관련성을 분석합니다 |
| **위성 모니터링** | Sentinel-2 위성으로 하우스 주변 NDVI를 추적하고, 작년 대비 변화를 알려줍니다 |
| **3축 교차검증** | 센서 + 위성 + 외부 시그널이 같은 방향을 가리킬 때 더 강하게 경보합니다 |
| **야간 보안** | PIR 센서로 야간 움직임을 감지하면 사진 촬영 후 카카오톡으로 알립니다 |

---

## 빠른 시작

### 필요한 것

- **Python 3.11 이상**
- **Windows 10/11** (DPAPI 암호화, 시스템 트레이 사용)
- 카카오톡 채널 (선택 — 없으면 모의 모드로 동작)

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/Berry-doctor.git
cd Berry-doctor

# 2. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 실행
python main.py
```

첫 실행 시 **설정 마법사**가 열립니다:
1. 농장 위치를 선택합니다 (지역별 기상 임계값 자동 적용)
2. 하우스 수, 품종, 재배 방식을 입력합니다
3. WiFi 정보를 입력합니다 (센서 펌웨어용, 선택)

> API 키가 없으면 **모의 데이터 모드**로 자동 전환됩니다.
> 모든 기능을 체험할 수 있고, 나중에 대시보드 설정에서 실제 키를 넣으면 됩니다.

### Windows 실행 파일

```bash
python setup.py
```

`dist/딸기박사.exe` 하나로 설치 없이 실행할 수 있습니다.

---

## 카카오톡 명령어

카카오톡에서 아래 명령어를 보내면 됩니다:

| 명령어 | 동작 |
|--------|------|
| `상태` | 전체 농장 상태 요약 |
| `1동 상태` | 1동 하우스 상태 |
| `오늘 할일` | 오늘 추천 작업 3가지 |
| `시세` | 딸기 시세와 출하 시점 예측 |
| `출하` | 안전출하일 확인 후 출하 판단 |
| `보조금` | 이용 가능한 정부 보조금 |
| `기록 수확 30kg` | 수확 30kg 기록 |
| `기록 수확 2동 30kg` | 2동 수확 30kg 기록 |
| `기록 농약 프로피네브` | 농약 살포 기록 |
| `진단` + 사진 | 병해 사진 진단 |
| `리포트` | 오늘의 일일 리포트 |
| `환풍기 켜`, `커튼 닫아`, `보광 켜`, `물 줘` | 장비 제어 (센서 연동 시) |
| `1동 환풍기 켜` | 특정 동 장비 제어 |
| `목표온도 18` | 목표 온도 설정 |
| `기록` | 위성 기반 시즌 타임라인 |
| `작년 비교` | 작년 같은 시기와 NDVI 비교 |
| `보안 기록` | 최근 7일 야간 보안 이벤트 |
| `도움말` | 명령어 목록 |
| (그 외 텍스트) | LLM 응답 또는 재배 일지로 자동 저장 |

---

## 대시보드

실행 후 브라우저에서 `http://127.0.0.1:8080`으로 접속합니다.

- **메인**: 농장 현황, 센서 그래프, 최근 알림, 제어 이력
- **기록**: 알림/농약/수확/진단/제어/카메라 전체 이력
- **일지**: 카카오톡으로 남긴 메모와 자동 기록
- **설정**: API 키, 임계값, dedupe 설정, 백업 관리
- **커뮤니티**: 현장 인사이트 공유
- **파일럿**: 시범 농가 피드백 관리

> 대시보드는 토큰 인증으로 보호됩니다.
> 첫 실행 시 자동 생성된 토큰은 설정 화면에서 확인할 수 있습니다.

---

## 프로젝트 구조

```
Berry-doctor/
├── main.py                    # 앱 진입점
├── setup.py                   # PyInstaller 빌드
├── requirements.txt           # Python 의존성
│
├── engine/                    # 핵심 엔진
│   ├── ai/                    # AI 모듈
│   │   ├── coach.py           # 대화/응답 조립
│   │   ├── disease_detector.py # ONNX 병해 진단
│   │   ├── llm.py             # 로컬 LLM 어시스턴트 (선택)
│   │   ├── yield_estimator.py # 수확량 예측
│   │   └── price_forecast.py  # 시세 예측
│   ├── db/                    # 데이터베이스
│   │   ├── schema.sql         # SQLite 스키마
│   │   └── sqlite.py          # Repository 클래스
│   ├── kakao/                 # 카카오톡 연동
│   │   ├── webhook.py         # 웹훅 서버 (Flask)
│   │   ├── commands.py        # 명령어 파서
│   │   └── sender.py          # 메시지 전송
│   ├── rules/                 # 규칙 엔진
│   │   ├── engine.py          # 날씨/센서 → 이벤트/제어 제안
│   │   └── disease_risk.py    # 질병 위험도 계산
│   ├── control/               # 온실 제어
│   │   ├── greenhouse.py      # MQTT 제어 명령 발행
│   │   └── pid.py             # 양액 EC/pH P제어
│   ├── signal/                # 외부 시그널 수집
│   │   ├── collector.py       # 수집기 (4개 소스 통합)
│   │   ├── analyzer.py        # 관련성 분석 (지역, 환경, 생육단계)
│   │   └── sources/           # 기상특보, 병해충예보, 시세급변, 커뮤니티
│   ├── satellite/             # 위성 모니터링
│   │   ├── copernicus.py      # Sentinel-2 클라이언트
│   │   ├── indices.py         # NDVI/NDWI/GNDVI 계산
│   │   ├── timeline.py        # 시즌 타임라인 생성
│   │   └── interpreter.py     # 위성 데이터 → 사람 말 번역
│   ├── fusion/                # 3축 교차검증
│   │   ├── intelligence.py    # 센서+위성+시그널 통합 판단
│   │   ├── risk_scorer.py     # 합의 기반 위험도 계산
│   │   ├── context_builder.py # 맥락 조립
│   │   └── message_composer.py # 메시지 작성
│   ├── scheduler/             # 자동 작업
│   │   ├── jobs.py            # 스케줄러 등록
│   │   ├── weather.py         # 날씨 갱신 (1시간)
│   │   ├── market.py          # 시세 갱신 (매일 06:00)
│   │   ├── daily_report.py    # 일일 리포트 (21:00)
│   │   ├── monthly_report.py  # 월간 리포트 (매월 1일)
│   │   ├── camera.py          # 카메라 촬영 (10:00)
│   │   ├── signal_job.py      # 시그널 수집 (6시간)
│   │   ├── satellite_job.py   # 위성 확인 (매일 06:30)
│   │   └── sensor_health.py   # 로그 정리 (03:15)
│   ├── security/              # 보안
│   │   ├── __init__.py        # DPAPI 암호화, HMAC 서명
│   │   └── monitor.py         # 야간 보안 모니터
│   ├── web/                   # 대시보드
│   │   ├── app.py             # FastAPI 앱
│   │   ├── routes.py          # REST 라우트
│   │   └── templates/         # HTML 템플릿
│   ├── backup.py              # DB 백업 서비스
│   ├── config.py              # 설정 관리
│   └── tray/icon.py           # 시스템 트레이
│
├── data/                      # 시드 데이터
│   ├── regional_profiles.json # 지역별 기상 프로필
│   ├── pesticide_db.json      # 농약-질병 매핑
│   ├── seolhyang_calendar.json # 설향 생육 캘린더
│   ├── knowledge_graph.json   # 품종별 재배 지식
│   ├── farmer_tips.json       # 전문가 팁
│   ├── subsidy_db.json        # 정부 보조금 정보
│   ├── signal_sources.json    # 시그널 소스 설정
│   └── satellite_config.json  # 위성 모니터링 설정
│
├── firmware/                  # ESP32 센서 펌웨어
│   └── src/                   # 센서, 릴레이, MQTT, 워치독, 야간보안
│
├── models/                    # ONNX 모델 (별도 배치)
├── i18n/                      # 다국어 (ko, en, ja)
├── tests/                     # 단위 테스트 (29개)
└── docs/                      # 상세 문서
    └── ARCHITECTURE.md        # 아키텍처 상세 설명
```

---

## 테스트

```bash
python -m unittest discover -s tests -v
```

29개 테스트가 파서, 규칙 엔진, DB, 보안, 센서 집계, CSRF, dedupe, 시그널, 위성, 퓨전, 야간 보안을 검증합니다.

---

## 설정 항목

대시보드 설정 화면 또는 SQLite `config` 테이블에서 조정할 수 있습니다:

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `sensor_log_interval_seconds` | 30 | 센서 원본 로그 저장 간격 (초) |
| `control_dedupe_window_seconds` | 90 | 같은 자동 제어 중복 방지 시간 (초) |
| `alert_dedupe_window_seconds` | 1800 | 같은 알림 중복 방지 시간 (초) |
| `community_insight_dedupe_window_seconds` | 1800 | 인사이트 중복 방지 시간 (초) |
| `raw_sensor_retention_days` | 90 | 센서 원본 로그 보관일 |
| `aggregate_sensor_retention_days` | 365 | 분 단위 집계 보관일 |
| `backup_retention_count` | 14 | 자동 백업 보관 개수 |

---

## 선택 의존성

기본 `requirements.txt`에 포함되지 않은 선택 패키지:

| 패키지 | 용도 | 설치 |
|--------|------|------|
| `llama-cpp-python` | 로컬 LLM 농업 어시스턴트 | `pip install llama-cpp-python` |
| `sentinelsat`, `rasterio`, `shapely`, `pyproj` | 실제 Copernicus 위성 API 연동 | `pip install -r requirements-satellite.txt` |

- LLM: 대시보드 설정에서 `local_llm_model_path`에 GGUF 모델 경로를 지정하면 활성화됩니다.
- 위성: 모의 모드에서는 설치 불필요. 실제 API 연동 시에만 필요합니다 (rasterio는 GDAL 필요).

---

## 하드웨어 (센서 연동)

센서 없이도 날씨 기반으로 모든 기능을 사용할 수 있습니다.
센서를 연결하면 실시간 환경 모니터링과 자동 제어가 가능해집니다.

| 문서 | 내용 |
|------|------|
| [부품 목록 (HARDWARE_BOM.md)](docs/HARDWARE_BOM.md) | 센서/보드/릴레이 제품명, 가격, 구매처 |
| [배선 가이드 (WIRING_GUIDE.md)](docs/WIRING_GUIDE.md) | 핀 연결 방법, 설치 위치, 문제 해결 |

**최소 15,000원**(ESP32 + 온습도 센서)으로 시작할 수 있고,
**기본 구성 50,000원**이면 온습도/토양/광량/수위까지 모니터링합니다.

---

## 주의사항

- **ONNX 모델**: 이 저장소에 학습된 실제 모델 가중치는 포함되어 있지 않습니다. 모델 없이도 휴리스틱 폴백으로 동작합니다.
- **농약/보조금 데이터**: MVP 시드 데이터입니다. 실제 배포 전 최신 공고와 안전사용기준을 반드시 재확인하세요.
- **Mosquitto**: `bin/mosquitto/`에 Windows 바이너리가 포함되어 있습니다. 센서 연동 없이도 앱은 정상 동작합니다.

---

## 라이선스

이 프로젝트의 라이선스 정보는 저장소 루트의 LICENSE 파일을 확인하세요.

---

> 도구는 화려함보다 신뢰를 남겨야 하고, 신뢰는 결국 사람과 AI가 서로 이해하려는 태도에서 시작됩니다.
