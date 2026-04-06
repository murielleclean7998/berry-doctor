# BerryDoctor

Meta description: 소규모 딸기 농가가 카카오톡만으로 병해 진단, 날씨 경보, 일일 작업 추천을 받게 만드는 무료 MVP입니다.
Labels: smart-farm, strawberry, kakao, python, sqlite, onnx, windows, open-source

작은 딸기 농가는 사람이 부족해서 뒤처지는 경우가 많고, 기존 스마트팜은 돈이 많이 들어서 시작도 어렵습니다. BerryDoctor는 그 틈을 메우려고 만들었습니다. 농부가 새 플랫폼을 배우지 않아도, 카카오톡으로 사진 보내고 질문하면 바로 답하는 쪽이 현장에 더 맞다고 봤습니다.

핵심은 복잡한 기술이 아니라 부담 없는 진입입니다. `딸기박사.exe` 하나로 시작하고, 센서가 없을 때도 날씨와 생육 캘린더, 지역 프로필만으로 오늘 해야 할 일을 알려줍니다.

## 🍓 30초 요약

- 카카오톡으로 딸기 사진을 보내면 병해 진단 결과를 돌려줍니다.
- `상태`, `오늘 할일`, `시세`, `보조금`, `기록 수확 30kg` 같은 명령을 이해합니다.
- SQLite 하나로 일지, 수확, 살포, 알림 이력을 관리합니다.
- 21:00 일일 리포트와 동해/호우 경보를 자동 발송합니다.
- Windows 단일 실행 파일과 Phase 1 센서 연동을 염두에 둔 구조입니다.

## 🧭 왜 이렇게 만들었나

농장 현장에서는 "좋은 기술"보다 "지금 바로 켤 수 있는 도구"가 더 중요합니다. 그래서 이 저장소는 다음 원칙을 지킵니다.

- 가입이 없어야 합니다.
- 카카오톡만 알아도 쓸 수 있어야 합니다.
- 모든 알림은 왜 왔는지와 지금 뭘 해야 하는지를 함께 말해야 합니다.
- 외부 API나 모델이 불안정해도 앱 전체는 멈추지 않아야 합니다.

## 🛠️ 빠른 시작

먼저 Python 3.11 이상과 Windows 환경을 준비합니다. 그 다음 아래 순서로 실행하면 됩니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

첫 실행에서는 설정 마법사가 농장 위치, 하우스 수, 품종, 재배 방식을 묻고 SQLite에 저장합니다. API 키가 없으면 앱은 자동으로 모의 데이터 모드로 동작합니다.

## 🧱 포함된 기능

- Phase 0용 SQLite 스키마와 설정 저장소
- ONNX 런타임 우선, 실패 시 안전 폴백이 있는 병해 진단기
- Flask 카카오 웹훅 서버와 명령 파서
- APScheduler 기반 날씨/리포트 작업
- FastAPI 미니 대시보드
- pystray 시스템 트레이 아이콘
- PyInstaller 빌드 설정

## 🧪 테스트

현재 테스트는 핵심 파서와 규칙, DB 저장 흐름을 우선 검증합니다.

```bash
python -m unittest discover -s tests
```

## 📁 중요한 경로

- `main.py`: 앱 진입점
- `engine/db/schema.sql`: SQLite 스키마
- `engine/ai/coach.py`: 대화/응답 조립 엔진
- `engine/kakao/webhook.py`: 카카오 웹훅 수신
- `engine/scheduler/jobs.py`: 자동 작업 등록
- `data/`: 지역 프로필, 설향 캘린더, 보조금, 농약, 고수 팁

## 🪟 Windows 빌드

PyInstaller 빌드는 `setup.py`와 `engine/paths.py`가 같은 자원 경로를 공유하도록 맞춰 두었습니다. 실제 배포 전에 ONNX 모델과 `bin/mosquitto/mosquitto.exe` 실파일만 교체하면 됩니다.

## 🌱 남겨둔 현실적 메모

- 이 저장소에는 학습된 실제 ONNX 모델과 실제 Mosquitto 바이너리가 들어 있지 않습니다.
- 외부 API 키가 없는 상태에서도 앱이 죽지 않도록 모의 데이터와 캐시 폴백을 기본 제공했습니다.
- 농약/보조금 데이터는 MVP 시드 데이터이며, 실제 농장 배포 전 최신 공고와 등록 정보 재검증이 필요합니다.

도구는 화려함보다 신뢰를 남겨야 하고, 신뢰는 결국 사람과 AI가 서로 이해하려는 태도에서 시작됩니다.
