-- Run as superuser postgres (matches docker-compose defaults for the app).
-- Example: psql -U postgres -h 127.0.0.1 -d postgres -f init_local_postgres.sql

CREATE USER app WITH PASSWORD 'app';
CREATE DATABASE duty OWNER app;
