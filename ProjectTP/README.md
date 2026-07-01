# ProjectTP — дежурства и отчёты

## Запуск целиком в Docker

В каталоге с этим файлом:

```bash
cp .env.example .env
# Заполните SESSION_SECRET и bootstrap-админа (при пустой БД)

docker compose up -d --build
```

Веб-интерфейс: `http://localhost` (или `http://localhost:<HTTP_PORT>`). Переменные окружения — в `.env.example`.

Первый администратор создаётся из переменных `BOOTSTRAP_ADMIN_*` при пустой БД. Дополнительных администраторов может назначить (и при необходимости снять права) только текущий админ: вкладка **Админ** → таблица сотрудников, колонка **Права администратора** (флажок «Админ»); операции пишутся в журнал (API `GET /api/admin/role-audit`). Нельзя оставить систему без единственного администратора; **изначального** администратора (логин из `BOOTSTRAP_ADMIN_USERNAME`) нельзя лишить прав администратора.

## Документация

- [docs/site-guide.md](docs/site-guide.md) — **инструкция по сайту** для сотрудников и администраторов (график, отчёты, ресурсы, админка).
- [../ТЗ-по-проекту.md](../ТЗ-по-проекту.md) — **техническое задание** (фактическое состояние продукта).
- [docs/roadmap.md](docs/roadmap.md) — **дорожная карта** продукта и открытые направления.
- [deployment_and_tz_request.md](deployment_and_tz_request.md) — быстрый деплой и шаблон запроса ТЗ на доработки.
- [docs/deploy-rocky-linux.md](docs/deploy-rocky-linux.md) — **целевой стек Docker**, запуск, обновление без потери БД, бэкап, перенос на другой хост, Rocky Linux, firewalld.
- [docs/notifications-inventory.md](docs/notifications-inventory.md) — **уведомления** (n8n, UI, Битрикс **№22** — выполнено).

Целевой рантайм контейнеров: **Docker Engine** + `docker compose` (см. раздел 1 в файле выше).

## CI и тесты

- В корне репозитория — `.gitlab-ci.yml`: job **`backend-pytest`** (`pytest` в `ProjectTP/backend/tests/`). Линтеры в pipeline не подключались (минимальный объём); при необходимости добавьте отдельный job.
- Локально: `cd ProjectTP/backend && pip install -r requirements.txt && pytest -q`.

## Эксплуатация API

- **Liveness:** `GET /api/health` — процесс жив (`{"ok": true, "service": "projecttp"}`).
- **Readiness (БД):** `GET /api/ready` — выполняется `SELECT 1`; при недоступности Postgres — **503**.
- **Вход:** после **12** неудачных попыток с одного IP и логина за **15 минут** — **429** (счётчик в памяти процесса; при нескольких воркерах каждый ведёт свой учёт). Успешный вход сбрасывает счётчик для этой пары.
- **Сессия:** cookie `session`, параметр **Max-Age** задаётся **`SESSION_MAX_AGE_SECONDS`** (см. `.env.example`); для HTTPS включайте `SESSION_COOKIE_HTTPS_ONLY=true`.
- **Статика:** при изменении `app.js` / `styles.css` поднимайте query-string `?v=…` в `index.html` и `login.html`, чтобы сбросить кэш у браузеров.

## Модульность фронта (задача №65)

Тексты блоков инструкции «выход сотрудника» собираются на сервере (`employee_exit_blocks.py`). Список чекбоксов в `index.html` должен соответствовать идентификаторам блоков; при добавлении блока обновляйте backend и разметку.

- `scripts/setup-docker-rocky.sh` — установка Docker CE и compose plugin на Rocky Linux 8/9.