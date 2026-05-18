# Эксплуатация уведомлений о дежурствах (runbook)

Цель: воспроизводимо включить рассылку (встроенный планировщик и/или внешний cron, Битрикс, опционально n8n) без устных пояснений. Эталон времени слотов — **Europe/Moscow** (см. [duty-time-moscow.md](duty-time-moscow.md)).

## 1. Переменные окружения (backend)

Скопируйте `ProjectTP/.env.example` в `.env` и задайте как минимум секреты из общего деплоя (`SESSION_SECRET`, Postgres, bootstrap при пустой БД — см. [deploy-rocky-linux.md](deploy-rocky-linux.md)).

| Переменная | Обязательность | Назначение |
|------------|----------------|------------|
| `TZ` | **Рекомендуется явно** `Europe/Moscow` | Часовой пояс процесса для **APScheduler** (:55 и :00). В `docker-compose.yml` по умолчанию `${TZ:-Europe/Moscow}`. Расчёт слота в коде идёт по МСК независимо от браузера; **`TZ` должна совпадать с внешним cron**, если тот тоже дергает dispatch по «локальным» :55/:00. |
| `BITRIX_INCOMING_WEBHOOK_URL` | Для ЛС в Битрикс | Базовый URL входящего вебхука …`/rest/<user>/<token>/` (без имени метода в конце). |
| `BITRIX_NOTIFY_DIALOG_ID` | Для сообщения в **общий чат** при старте слота и для «график на день» | Идентификатор диалога (`chatNNN` или иной формат, принимаемый API). |
| `BITRIX_WEBHOOK_TIMEOUT_SEC` | Опционально | Таймаут HTTP к Битрикс (секунды). |
| `N8N_WEBHOOK_URL` | Опционально | URL вебхука n8n; пока пусто — события в n8n не отправляются. |
| `N8N_WEBHOOK_TIMEOUT_SEC` | Опционально | Таймаут вызова вебхука. |
| `N8N_DUTY_WEBHOOK_ENABLED` | Опционально, по умолчанию `false` | Должно быть **`true`**, иначе при непустом `N8N_WEBHOOK_URL` дубли JSON в n8n **не** выполняется (только Битрикс при настроенном вебхуке). |

Проверка после старта: `docker compose logs backend | grep -i scheduler` — ожидается строка вида «Notification scheduler started (TZ=…)». Ошибки рассылки при срабатывании планировщика — в тех же логах (`duty notify …`).

## 2. Таблица `duty_notification_settings` (PostgreSQL)

Одна строка с **`id = 1`** (singleton). Создаётся миграциями; при отсутствии часть кода создаёт строку при первом обращении.

| Колонка / группа | Смысл в эксплуатации |
|------------------|----------------------|
| **`scheduler_enabled`** | Если **`false`**, встроенный **APScheduler** не вызывает dispatch (фоновые тики `:55` / `:00` отклоняются с причиной в логах). **Внешний cron** или ручной вызов API идут с `invoked_by_scheduler=False` и **не** блокируются этим флагом. |
| **`selected_method`** | Значение `'cron'` или `'n8n'` хранится в БД и **не** участвует в текущей логике `dispatch_duty_notification` (не читается Python-кодом). Имеет смысл как задел/ручная метка для эксплуатации; выбор «кто дергает» (встроенный планировщик vs n8n vs OS cron) делается настройкой **`scheduler_enabled`** и расписанием **вне** приложения. |
| **`cron_enabled_upcoming_5m`**, **`cron_enabled_start`**, **`cron_enabled_chat_on_start`** | Флаги режимов, которые **реально читает** dispatch при отправке. |
| **`n8n_enabled_*`** | Дублируются из админского PATCH теми же значениями, что и `cron_*` (обратная совместимость схемы БД). На поведение dispatch это не влияет отдельно — достаточно смотреть на флаги, отображаемые в API как `enabled_*`. |
| **Шаблоны** (`upcoming_5m_template`, `start_personal_template`, `start_chat_template`, `test_*`) | Тексты ЛС и чата; правка через API шаблонов (вкладка админки / `PATCH …/notifications/templates`). |

Просмотр и смена флагов без SQL: API **`GET/PATCH /api/admin/notifications/settings`** (нужны права на управление уведомлениями). Поля ответа: `scheduler_enabled`, `enabled_upcoming_5m`, `enabled_start`, `enabled_chat_on_start`.

## 3. Каналы и типичные сценарии

1. **Только встроенный планировщик:** `scheduler_enabled=true`, в `.env` заданы Битрикс (и при необходимости n8n), `TZ` согласована с ожиданиями МСК. Внешний cron для тех же эндпоинтов **не** настраивать — риск дублей; см. [notifications-dedup.md](notifications-dedup.md).
2. **Только внешний cron / n8n:** выставить **`scheduler_enabled=false`**, вызывать по расписанию `POST /api/admin/notifications/duty-upcoming/5m` и `…/start` (или общий dispatch с `mode=`) с авторизацией админа/сервисной УЗ. Часовые метки в теле запроса не обязательны: слот считается по «сейчас» МСК.
3. **n8n как транспорт JSON:** включить `N8N_DUTY_WEBHOOK_ENABLED=true` и задать `N8N_WEBHOOK_URL`; Битрикс настраивается независимо (сообщения уходят в ЛС/чат по вебхуку сотрудника и `BITRIX_NOTIFY_DIALOG_ID`). Не дублировать тот же текст из n8n в Битрикс, если backend уже шлёт в Битрикс — см. [notifications-dedup.md](notifications-dedup.md).

Детали каналов и типичные ошибки Битрикс — [notifications-inventory.md](notifications-inventory.md), быстрая диагностика — [notifications-diagnostics.md](notifications-diagnostics.md). Регламент против дублей между scheduler / cron / n8n — [notifications-dedup.md](notifications-dedup.md). Приёмка на стенде — [staging-acceptance-checklist.md](staging-acceptance-checklist.md).

## 4. Минимальный чеклист перед продом

- [ ] В `.env` заданы `SESSION_SECRET`, креды БД, при необходимости bootstrap.
- [ ] `TZ=Europe/Moscow` (или согласованная зона, совпадающая с внешним cron).
- [ ] Для Битрикс: `BITRIX_INCOMING_WEBHOOK_URL`, у дежурных заполнен `bitrix_user_id`; для общего чата — `BITRIX_NOTIFY_DIALOG_ID`, участник вебхука в чате.
- [ ] В БД (или через UI) проверены `scheduler_enabled` и три флага режимов.
- [ ] Решено, кто шлёт по расписанию: только процесс backend или внешняя цепочка (без дублирования); пройден чеклист из [notifications-dedup.md](notifications-dedup.md) §6.
