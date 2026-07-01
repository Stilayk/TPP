# Инструкция по развёртыванию и запрос ТЗ

Актуальность: **2026-07-01**. Подробный runbook для Rocky Linux — [docs/deploy-rocky-linux.md](docs/deploy-rocky-linux.md). Формальное ТЗ продукта — [../ТЗ-по-проекту.md](../ТЗ-по-проекту.md).

---

## 1. Быстрый деплой через Docker Compose

### Предусловия

- **Docker Engine** + **Compose v2** (целевой рантайм, не Podman).
- Свободный порт для веб-интерфейса (по умолчанию **80**, задаётся `HTTP_PORT`).

### Подготовка

1. Перейти в каталог `ProjectTP/`.
2. Скопировать переменные окружения:
   ```bash
   cp .env.example .env
   ```
3. Заполнить **обязательные** значения в `.env`:
   - `SESSION_SECRET` — случайная строка;
   - `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_FULLNAME` — первый admin (только при пустой БД);
   - при необходимости `POSTGRES_PASSWORD`, `COMPOSE_PROJECT_NAME`, `HTTP_PORT`.
4. Опционально: `BITRIX_INCOMING_WEBHOOK_URL`, `N8N_WEBHOOK_URL`, `TZ=Europe/Moscow`.

### Запуск

```bash
docker compose up -d --build
docker compose ps
```

Открыть: `http://localhost` или `http://localhost:<HTTP_PORT>`.

### Остановка и обновление

- Остановка **без удаления данных**: `docker compose down`
- Обновление после изменения кода: `docker compose up -d --build`
- **Не использовать** `docker compose down -v` на проде без бэкапа — удалит том PostgreSQL `pgdata`.

### Данные

- PostgreSQL — именованный том `pgdata` (см. §5.1 в [deploy-rocky-linux.md](docs/deploy-rocky-linux.md)).
- Excel-отчёты — каталог `./exports` (volume в compose).
- Миграции применяются автоматически при старте backend (`alembic upgrade head`).

---

## 2. Локальная разработка (без Docker для backend)

1. Поднять PostgreSQL (локально или `docker compose up -d db`).
2. Задать `DATABASE_URL` в `.env` (см. `.env.example`).
3. Backend:
   ```bash
   cd ProjectTP/backend
   pip install -r requirements.txt
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
4. Прокси статики и API (из каталога `ProjectTP/`):
   ```bash
   python local_dev_proxy.py
   ```
5. Открыть `http://127.0.0.1:8080`.

---

## 3. Проверки после деплоя

| Проверка | Ожидание |
|----------|----------|
| `GET /api/health` | `{"ok": true, "service": "projecttp"}` |
| `GET /api/ready` | `{"ok": true}`; при недоступной БД — **503** |
| Вход под bootstrap-admin | Главная страница, вкладка «Админ» |
| `docker compose ps` | Сервисы `db`, `backend`, `nginx` — running |

Приёмка сценариев: [docs/staging-acceptance-checklist.md](docs/staging-acceptance-checklist.md).

---

## 4. Чек-лист запроса формального ТЗ

Перед крупной новой фичей запросить у заказчика:

- Бизнес-цель и метрики успеха.
- Роли и права (кто что видит и меняет).
- Happy-path сценарий по шагам.
- Edge cases (минимум 3 критичных).
- Критерии приёмки («дано / когда / тогда»).
- Данные: что хранить, срок, кто видит.
- Интеграции (Битрикс, n8n, форматы).
- Нефункциональные требования (безопасность, SLA, аудит).
- План релиза и отката.

Текущее базовое ТЗ реализованного продукта: [../ТЗ-по-проекту.md](../ТЗ-по-проекту.md).

---

## 5. Шаблон запроса ТЗ на доработку

```text
Нужен формальный ТЗ для задачи: <название>.

1. Бизнес-цель:
2. Пользовательские роли и права:
3. Сценарий happy-path (шаги):
4. Критичные ограничения / исключения:
5. Критерии приёмки:
6. Интеграции и внешние зависимости:
7. Требования к хранению и доступу к данным:
8. Дедлайн и план внедрения:
```

После согласования — карточка в корневом `TASKS.md` и запись в `HANDOFF.md`.
