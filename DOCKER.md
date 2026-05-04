# Docker запуск CollectIT

Этот набор поднимает весь проект:

- `postgres` — PostgreSQL 16
- `redis` — Redis для Channels и Celery
- `backend` — Django ASGI через Daphne
- `celery` — worker фоновых задач
- `frontend` — React build через nginx, с proxy на `/api`, `/ws`, `/static`, `/media`

## Быстрый старт

```powershell
cd D:\VKR\collectit
copy .env.docker.example .env.docker
docker compose --env-file .env.docker up --build
```

Открыть приложение:

```text
http://localhost:3000
```

Backend напрямую:

```text
http://localhost:8000
```

PostgreSQL и Redis проброшены наружу на нестандартные dev-порты, чтобы не мешать локальным сервисам:

```text
PostgreSQL: localhost:5433
Redis: localhost:6380
```

Админка через frontend/nginx:

```text
http://localhost:3000/admin/
```

## Создать администратора

В отдельном окне:

```powershell
docker compose --env-file .env.docker exec backend python manage.py createsuperuser
```

## Полезные команды

```powershell
# Остановить контейнеры
docker compose --env-file .env.docker down

# Остановить и удалить данные БД/Redis/media/static volumes
docker compose --env-file .env.docker down -v

# Посмотреть логи backend
docker compose --env-file .env.docker logs -f backend

# Применить миграции вручную
docker compose --env-file .env.docker exec backend python manage.py migrate

# Django shell
docker compose --env-file .env.docker exec backend python manage.py shell
```

## Важные заметки

- Для Docker фронт собирается с `REACT_APP_API_URL=/api`, поэтому браузер ходит на тот же origin (`localhost:3000`). Это важно для httpOnly cookie и WebSocket.
- `backend` при старте ждёт Postgres, применяет миграции и собирает static files.
- `media` и `staticfiles` лежат в Docker volumes и отдаются nginx.
- Для production поменяйте `DJANGO_SECRET_KEY`, выключите `DJANGO_DEBUG`, настройте HTTPS, поставьте `JWT_COOKIE_SECURE=True` и включите `DJANGO_SECURE_SSL_REDIRECT=True`.
