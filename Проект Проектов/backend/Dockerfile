FROM python:3.12-slim

WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh ./entrypoint.sh
COPY app ./app

RUN chmod +x ./entrypoint.sh

EXPOSE 8000

CMD ["/app/backend/entrypoint.sh"]

