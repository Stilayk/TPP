FROM python:3.12-slim

WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY entrypoint.sh ./entrypoint.sh
COPY docker_healthcheck.py ./docker_healthcheck.py
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

RUN chmod +x ./entrypoint.sh ./docker_healthcheck.py

EXPOSE 8000

CMD ["/app/backend/entrypoint.sh"]

