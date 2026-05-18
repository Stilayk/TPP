# Дежурства и уведомления: эталон времени Europe/Moscow

График по слотам и триггеры уведомлений (**:55** за 5 минут до часа, **:00** на старте слота) считаются в **московском** локальном времени. Это не зависит от часового пояса браузера пользователя и от случайного TZ хоста без настройки.

## Код

| Что | Где |
|-----|-----|
| «Сейчас», «сегодня», разбор параметра `at` для dispatch | `backend/app/duty_tz.py` |
| Расчёт слота для уведомления | `backend/app/duty_notification_slot.py`, `backend/app/duty_notifications.py` |
| Cron APScheduler :55 / :00 | `backend/app/notification_scheduler.py`, переменная **`TZ`** (`Settings`, по умолчанию `Europe/Moscow`) |

## Окружение

В типичном деплое задайте **`TZ=Europe/Moscow`** для процесса backend (в `.env` для compose см. `docker-compose.yml`: `${TZ:-Europe/Moscow}`). Расхождение между **`TZ`** процесса и внешним cron приводит к сдвигу минут триггера относительно логики слотов.

## Ручной параметр `at`

- Дата-время **без указания зоны** в запросе интерпретируется как **локальное время МСК** (удобно для тестов и ручного вызова).
- Значение с **UTC** или offset переводится в **Europe/Moscow** перед выбором слота.

Эксплуатация (переменные окружения, `duty_notification_settings`): [notifications-runbook.md](notifications-runbook.md). Исключение дублей между инициаторами: [notifications-dedup.md](notifications-dedup.md).
