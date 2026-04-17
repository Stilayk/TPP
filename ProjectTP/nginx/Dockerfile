FROM nginx:1.27-alpine

# Статика и конфиг — контекст сборки: корень `ProjectTP` (см. docker-compose).
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/ /usr/share/nginx/html/

EXPOSE 80

