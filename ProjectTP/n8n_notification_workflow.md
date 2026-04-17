# P2 №6: n8n — уведомления о дежурствах (webhook)

## Backend

- Эндпоинт: `POST /api/admin/notifications/duty-upcoming/dispatch` (алиасы: `/duty-upcoming/5m`, `/duty-upcoming/start`).
- Роль: только **admin** (сессия).
- Query-параметры:
  - `at` — ISO datetime; если не задан, используется текущее время процесса для расчёта слота.
  - `mode` — `upcoming_2m` (legacy, чат в Битрикс), `upcoming_5m`, `start` (см. описание в коде и в `docs/notifications-inventory.md`).
  - `strict_timing` — по умолчанию `true`: слот считается только если после сдвига (`+5` мин для `upcoming_5m`, `+0` для `start`, `+2` для `upcoming_2m`) минуты ровно `00` (как у встроенного cron `:55` / `:00`). При `strict_timing=false` допускается снап к ближайшему целому часу в пределах **±3 минут** (дрейф внешнего cron/n8n).
- Переменные окружения:
  - `N8N_WEBHOOK_URL` — URL **Webhook** в n8n.
  - `N8N_DUTY_WEBHOOK_ENABLED` — должно быть **`true`**, иначе JSON в n8n **не отправляется** (остаётся только Битрикс при настроенном `BITRIX_INCOMING_WEBHOOK_URL`).
- Если **ни** n8n (по условиям выше), **ни** Битрикс не настроены, ответ `sent=false`, поле `reason` содержит текст вроде: `No notification channels configured (set BITRIX_INCOMING_WEBHOOK_URL and/or optional n8n)`.

## Тело webhook (JSON)

Поле `event` совпадает с `mode` API (`upcoming_2m`, `upcoming_5m`, `start`). Пример:

```json
{
  "event": "upcoming_5m",
  "date": "2026-03-31",
  "slot": 0,
  "start_time": "07:00",
  "employee": {
    "id": 1,
    "full_name": "Иванов Иван",
    "username": "ivanov",
    "bitrix_user_id": 11751
  }
}
```

## Рекомендуемый workflow в n8n

1. Узел **Webhook** (POST) — принимает JSON выше.
2. Узел **IF** — проверка `event` на нужное значение (`upcoming_5m`, `start`, …).
3. Узел уведомления на выбор команды:
   - **Telegram** / **Slack** / email;
   - или **HTTP Request** во внутренний сервис;
   - для «звука» в браузере — обычно отдельная страница/PWA или корпоративный мессенджер (чистый n8n не воспроизводит звук на ПК пользователя без клиента).

4. Текст уведомления: например «Через 5 минут дежурство: {{ $json.employee.full_name }}, слот {{ $json.start_time }}».

## Деплой

В `.env` / `docker-compose` задать `N8N_WEBHOOK_URL=https://<n8n-host>/webhook/<id>` (секрет только через env) и при необходимости `N8N_DUTY_WEBHOOK_ENABLED=true`.

## Диагностика

Краткий чеклист по TZ, Битрикс и `strict_timing`: [docs/notifications-diagnostics.md](docs/notifications-diagnostics.md).
