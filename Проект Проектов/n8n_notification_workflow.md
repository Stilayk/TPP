# P2 №6: n8n — уведомление за 2 минуты до дежурства

## Backend

- Эндпоинт: `POST /api/admin/notifications/duty-upcoming/dispatch`
- Роль: только **admin** (сессия).
- Опциональный query: `at` — ISO datetime; иначе берётся «сейчас + 2 минуты» для вычисления целевого слота.
- Переменная окружения: `N8N_WEBHOOK_URL` — URL **Webhook** в n8n. Если пусто, ответ `sent=False`, `reason='N8N webhook is not configured'` (dry-run).

## Тело webhook (JSON)

Пример поля, отправляемого на URL:

```json
{
  "event": "duty_upcoming_2m",
  "date": "2026-03-31",
  "slot": 0,
  "start_time": "07:00",
  "employee": {
    "id": 1,
    "full_name": "Иванов Иван",
    "username": "ivanov"
  }
}
```

## Рекомендуемый workflow в n8n

1. Узел **Webhook** (POST) — принимает JSON выше.
2. Узел **IF** — проверка `event === "duty_upcoming_2m"` (опционально).
3. Узел уведомления на выбор команды:
   - **Telegram** / **Slack** / email;
   - или **HTTP Request** во внутренний сервис;
   - для «звука» в браузере — обычно отдельная страница/PWA или корпоративный мессенджер (чистый n8n не воспроизводит звук на ПК пользователя без клиента).

4. Текст уведомления: например «Через 2 минуты дежурство: {{ $json.employee.full_name }}, слот {{ $json.start_time }}».

## Деплой

В `.env` / `docker-compose` задать `N8N_WEBHOOK_URL=https://<n8n-host>/webhook/<id>` (секрет только через env).
