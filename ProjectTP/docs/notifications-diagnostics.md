# Диагностика уведомлений о дежурствах (чеклист)

Используйте вместе с [notifications-inventory.md](notifications-inventory.md) и [n8n_notification_workflow.md](../n8n_notification_workflow.md).

## 1. Часовой пояс

- В **Docker** для сервиса `backend` задайте `TZ` (в `docker-compose.yml` уже есть `TZ: "${TZ:-UTC}"`).
- В `.env` рекомендуется `TZ=Europe/Moscow` (или зона заказчика), чтобы встроенный планировщик и внешний cron совпадали с локальными `:55` / `:00`.

## 2. Строгое время триггера

- По умолчанию (`strict_timing=true`) слот определяется только если после сдвига минуты ровно **00** (см. инвентаризацию).
- Если внешний вызов приходит с опозданием на 1–2 минуты, используйте **`strict_timing=false`** на эндпоинте dispatch (тот же путь, что и раньше; регистрируется отдельным модулем роутера до общего `duties`).
- Допуск снапшота к часу: **±3 минуты** к ближайшему `:00` (константа `RELAXED_SLOT_TOLERANCE` в `app/duty_notification_slot.py`).

## 3. Каналы

- **Битрикс ЛС** за 5 минут / в старт: нужны `BITRIX_INCOMING_WEBHOOK_URL` и у сотрудника заполненный `bitrix_user_id`.
- **Общий чат**: пара URL + `BITRIX_NOTIFY_DIALOG_ID`, пользователь вебхука — участник чата; см. инвентаризацию про `chatNNN`.
- **n8n**: `N8N_WEBHOOK_URL` и **`N8N_DUTY_WEBHOOK_ENABLED=true`**, иначе webhook не вызывается.

## 4. Быстрые проверки

- Ручной вызов с явным временем: `POST .../duty-upcoming/5m?at=2026-04-15T09:55:00` (ISO) при `strict_timing=true`.
- Тест ЛС: `POST /api/admin/notifications/duty-test?user_id=...` (админ).
- Скрипт чата: `python check_bitrix_message.py` из каталога `ProjectTP/` при заданных `BITRIX_*` в окружении.

## 5. Встроенный планировщик

- Флаги в админке (`scheduler_enabled`, включение 5m/start) хранятся в `duty_notification_settings`; при отключённом планировщике фоновые вызовы не отправляют уведомления.
