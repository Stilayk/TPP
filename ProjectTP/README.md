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

- [docs/deploy-rocky-linux.md](docs/deploy-rocky-linux.md) — **целевой стек Docker**, запуск, обновление без потери БД, бэкап, перенос на другой хост, Rocky Linux, firewalld.
- [docs/notifications-inventory.md](docs/notifications-inventory.md) — **уведомления** (n8n, UI, план Битрикс №22).

Целевой рантайм контейнеров: **Docker Engine** + `docker compose` (см. раздел 1 в файле выше).

## Скрипты

- `scripts/setup-docker-rocky.sh` — установка Docker CE и compose plugin на Rocky Linux 8/9.