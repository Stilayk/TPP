# Развёртывание на Rocky Linux (Docker Compose)

**Целевой рантайм:** **Docker Engine** и плагин **Compose v2** (`docker compose`). Тот же `docker-compose.yml` часто поднимается и через `podman compose`, но для продакшена и документации за базу берётся **Docker**; при расхождениях ориентируйтесь на Docker CE, как в `scripts/setup-docker-rocky.sh`.

Продакшен-режим: на сервере нужны только **Docker** и **Git** (или архив с кодом). Python, Node и отдельный Postgres на хосте не требуются: поднимаются контейнеры **PostgreSQL**, **backend (FastAPI)** и **nginx** со статическим фронтендом из `frontend/`.

## 1. Что переносится

| Компонент | Где хранится |
|-----------|----------------|
| Код | каталог с `docker-compose.yml` (репозиторий или архив) |
| Секреты и порты | файл `.env` рядом с `docker-compose.yml` (см. `.env.example`) |
| Данные БД | Docker volume `pgdata` |
| Excel-экспорты | каталог `./exports` на хосте (монтируется в backend) |

## 2. Установка Docker на Rocky Linux 8/9

От root или через sudo:

```bash
chmod +x scripts/setup-docker-rocky.sh
sudo ./scripts/setup-docker-rocky.sh
```

После скрипта пользователь, под которым вы работаете, должен быть в группе `docker`; при необходимости выйдите из сессии и войдите снова, затем:

```bash
docker compose version
```

Альтернатива: пакет `docker` из репозиториев Rocky без Docker CE — возможен, но ниже предполагается **Docker CE** и плагин **compose v2**, как в скрипте.

## 3. Перенос проекта на сервер

**Вариант A — Git**

```bash
sudo dnf -y install git
cd /opt   # или домашний каталог
sudo git clone <URL-репозитория> duty-stack
sudo chown -R "$USER:$USER" duty-stack
cd duty-stack/Проект\ Проектов   # если в монорепо путь такой; иначе — корень с compose
```

**Вариант B — архив**

На машине с кодом упакуйте каталог, где лежат `docker-compose.yml`, `backend/`, `frontend/`, `nginx/`, скопируйте на Rocky (`scp`, `rsync`) и распакуйте.

## 4. Конфигурация `.env`

```bash
cp .env.example .env
nano .env   # или vi
```

Обязательно задайте:

- `SESSION_SECRET` — длинная случайная строка.
- При **пустой** базе: `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_FULLNAME`.

Рекомендуется сменить `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` под продакшен; они должны совпадать с тем, что подставится в `DATABASE_URL` внутри compose (compose собирает URL из этих переменных).

Опционально:

- `HTTP_PORT` — если порт `80` занят (например `8080`; тогда URL будет `http://<хост>:8080`).
- `POSTGRES_PORT` — если на хосте занят `5432` (для доступа к БД с хоста; контейнеры ходят на сервис `db:5432` без изменений).

## 5. Запуск и обновление

Из каталога с `docker-compose.yml`:

```bash
docker compose up -d --build
docker compose ps
```

Проверка: откройте в браузере `http://<IP-сервера>` (или `http://<IP>:<HTTP_PORT>`).

Остановка:

```bash
docker compose down
```

Остановка **с удалением данных БД** (осторожно):

```bash
docker compose down -v
```

### 5.1. Данные БД при падении контейнера и пересборке

- Данные PostgreSQL лежат в **именованном томе** `pgdata` (см. `docker-compose.yml`). **Падение** контейнера `db` или `docker compose up -d --build` **не удаляют** этот том сами по себе.
- Безопасное обновление кода: **`docker compose up -d --build`** из **одного и того же** каталога с compose и стабильным **`COMPOSE_PROJECT_NAME`** в `.env` (иначе Compose создаст **новый** том, и база покажется «пустой»).
- Данные **теряются**, если вызывать **`docker compose down -v`**, вручную удалять volume или менять имя проекта/путь так, что подключается другой том.
- Диагностика «куда делась БД»: `docker volume ls` (или `podman volume ls`), сопоставить имя тома с префиксом проекта; логи: `docker compose logs db`.

Обновление версии кода:

```bash
git pull   # если из git
docker compose up -d --build
```

## 6. Файрвол (firewalld)

Если включён firewalld и нужен доступ с других машин:

```bash
sudo firewall-cmd --permanent --add-service=http
# или нестандартный порт, например 8080:
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

Порт PostgreSQL (`POSTGRES_PORT`, по умолчанию 5432) в продакшене обычно **не** открывают наружу; администрирование — по SSH или только с localhost.

## 7. Резервное копирование и миграция на другой хост

Перед **`docker compose down -v`**, экспериментами с томами или миграцией ОС сделайте **дамп БД**.

**База**

```bash
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-app}" "${POSTGRES_DB:-duty}" > backup.sql
```

Восстановление на новом сервере (после `docker compose up -d db` и готовности БД):

```bash
docker compose exec -T db psql -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-duty}" < backup.sql
```

(Убедитесь, что пользователь/БД совпадают с `.env`.)

Для крупных баз удобнее custom-формат: `pg_dump -Fc` и `pg_restore` (см. документацию PostgreSQL).

**Экспорты**

Скопируйте каталог `exports/` с старого сервера в тот же путь рядом с `docker-compose.yml`.

**Том `pgdata`**

Допустим перенос volume: остановить стек, скопировать данные Docker (`/var/lib/docker/volumes/...`) — способ зависит от установки; проще и надёжнее **pg_dump/pg_restore**.

## 8. Диагностика

```bash
docker compose logs -f backend
docker compose logs -f db
```

Частые причины `unhealthy` у backend: пустой `SESSION_SECRET`, не задан bootstrap при пустой БД, неверные креды Postgres. Текст ошибки будет в логах.

## 9. Локальная разработка без полного стека в Docker

1. В каталоге с `docker-compose.yml`: `docker compose up -d db` (Postgres на `localhost:5432`, см. `POSTGRES_PORT` в `.env`).
2. В `.env` задать `DATABASE_URL=postgresql+psycopg://…@127.0.0.1:5432/…` в соответствии с `POSTGRES_*`.
3. В каталоге `backend/` запустить uvicorn с переменными из `.env` (в т.ч. `SESSION_SECRET`).
4. При необходимости — `python local_dev_proxy.py` из каталога проекта и открыть URL прокси (см. комментарии в `local_dev_proxy.py`).
