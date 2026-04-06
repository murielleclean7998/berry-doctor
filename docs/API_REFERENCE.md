# API Reference

## Flask Webhook

- `GET /health`
- `POST /kakao/webhook`

예시 payload:

```json
{
  "text": "오늘 할일"
}
```

사진 진단 예시:

```json
{
  "text": "진단",
  "image_bytes": "<base64>"
}
```

## FastAPI Dashboard

- `GET /`
- `GET /history`
- `GET /settings`
- `GET /diary`
- `GET /api/status`
