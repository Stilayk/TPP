# Duty Web App (техподдержка)

Веб‑приложение для:
1) графика дежурств по 1 часу в рабочее время **09:00–18:00** (слоты `09-10 ... 17-18`),
2) ежедневного отчета: **минуты + описание** и выгрузка **Excel (.xlsx)**, сохраняемая на сервере.

Проект деплоится на **Rocky Linux** через **Docker Compose** (БД SQLite + Excel в volumes).

## Стек

- Backend: **FastAPI + SQLAlchemy + SQLite**
- Excel: **openpyxl**
- Frontend: статик **HTML/JS без сборки**
- Proxy/статика: **Nginx**

## Что хранится и не теряется

- `data/` — файл SQLite (`/data/app.sqlite`) в контейнере
- `exports/` — выгруженные `.xlsx` (`/exports` в контейнере)

## Подготовка на Rocky Linux

1. Установите Docker Engine и Docker Compose plugin (примерные команды зависят от версии Rocky; важно наличие `docker compose`).
2. Перейдите в папку проекта на сервере: `duty_app/`.
3. Создайте файл `.env` на основе `.env.example` и задайте значения:
   - `SESSION_SECRET` (обязательно)
   - `BOOTSTRAP_ADMIN_USERNAME/PASSWORD/FULLNAME` (если вы первый раз запускаете и БД пустая)

4. Поднимите сервисы:
   - `docker compose up -d --build`

5. Откройте в браузере:
   - `http://<host>/`
   - если сессии нет, фронт автоматически редиректит на `http://<host>/login.html`

## Bootstrap первого админа

Если в SQLite ещё нет пользователей, backend создаст администратора из переменных:
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_FULLNAME`

Дальше админ добавляет сотрудников `support`, и они смогут заполнять отчеты.

