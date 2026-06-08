# Docker запуск CollectIT

Этот набор поднимает весь проект:

- `postgres` — PostgreSQL 16
- `redis` — Redis для Channels и Celery
- `backend` — Django ASGI через Daphne
- `celery` — worker фоновых задач
- `celery-beat` — расписание фоновых задач, включая AI-импорт новостей
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

По умолчанию `postgres`, `redis` и прямой `backend:8000` привязаны только к
`127.0.0.1`, чтобы не открыть служебные порты наружу при запуске на сервере.
Наружу должен смотреть только frontend/nginx (`FRONTEND_HOST=0.0.0.0`).

Админка через frontend/nginx:

```text
http://localhost:3000/admin/
```

## Создать администратора

В отдельном окне:

```powershell
docker compose --env-file .env.docker exec backend python manage.py createsuperuser
```

## Production на домене

Для полноценного запуска CollectIT нужен VPS/сервер с Docker daemon и Docker Compose v2. Обычный shared-хостинг REG.RU с FTP/MySQL не подходит для текущего стека: приложению нужны PostgreSQL, Redis, Daphne/WebSocket, Celery worker и Celery beat.

Минимальный запуск на VPS:

```bash
git clone <repo-url> collectit
cd collectit
cp .env.docker.example .env.docker
```

В `.env.docker` для доменов:

```env
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=collecit.ru,www.collecit.ru,collecit.online,www.collecit.online
CORS_ALLOWED_ORIGINS=https://collecit.ru,https://www.collecit.ru,https://collecit.online,https://www.collecit.online
FRONTEND_URL=https://collecit.ru
JWT_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=True
ENABLE_DEMO_DEPOSIT=False
FRONTEND_HOST=127.0.0.1
FRONTEND_PORT=3000
ACME_EMAIL=admin@collecit.ru
```

Затем:

```bash
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` поднимает Caddy на `80/443`; Caddy выпускает Let's Encrypt-сертификаты и проксирует запросы в `frontend:80`. Перед запуском DNS-записи `A` для `collecit.ru`, `www.collecit.ru`, `collecit.online`, `www.collecit.online` должны указывать на IP VPS.

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
- Для локальной регистрации удобнее `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`: ссылка подтверждения печатается в `docker compose --env-file .env.docker logs -f backend`. Для SMTP обязательно задайте `EMAIL_TIMEOUT`, чтобы регистрация не зависала до 504.
- Если Gmail SMTP на `smtp.gmail.com:587` таймаутится из Docker/WSL, используйте SSL-порт `465`: `EMAIL_PORT=465`, `EMAIL_USE_TLS=False`, `EMAIL_USE_SSL=True`.
- AI-импорт новостей с `numizmatik.ru` настраивается через `GEMINI_API_KEY`, `NEWS_IMPORT_ENABLED`, `NEWS_IMPORT_INTERVAL_MINUTES`, `NEWS_IMPORT_LIMIT`. За один запуск парсер объединяет найденные источники в одну большую AI-статью с галереей картинок. Ручная проверка парсинга без публикации:
  `docker compose --env-file .env.docker exec backend python manage.py import_numizmatik_news --limit 3 --dry-run`.
  Основная модель задаётся через `GEMINI_MODEL`, fallback при ошибке — через `GEMINI_FALLBACK_MODEL`.
- Telegram-уведомления о тикетах поддержки включаются через `TELEGRAM_BOT_TOKEN` и `TELEGRAM_ADMIN_CHAT_IDS`. Чтобы узнать chat id, отправьте боту `/start`, затем выполните:
  `docker compose --env-file .env.docker exec backend python manage.py telegram_get_updates`.
- Media-файлы должны открываться через frontend/nginx на том же origin, например `http://localhost:3000/media/...`. Nginx прокидывает backend полный `Host` с портом, чтобы DRF не строил ссылки вида `http://localhost/media/...`.
- Для production поменяйте `DJANGO_SECRET_KEY`, выключите `DJANGO_DEBUG`, настройте HTTPS, поставьте `JWT_COOKIE_SECURE=True` и включите `DJANGO_SECURE_SSL_REDIRECT=True`.
- JWT JSON endpoints, Bearer-auth и access-token в WebSocket query string выключены по умолчанию: `ENABLE_LEGACY_JWT_ENDPOINTS=False`, `ENABLE_BEARER_JWT_AUTH=False`, `ALLOW_WEBSOCKET_QUERY_TOKEN=False`.
- Refresh-токены ротируются и отзываются через SimpleJWT blacklist. После обновления backend выполните миграции: `docker compose --env-file .env.docker exec backend python manage.py migrate`.
- Для защиты загрузок оставьте лимиты `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`, `USER_IMAGE_MAX_BYTES`, `USER_IMAGE_MAX_COUNT` в разумных пределах.
- Не включайте `ENABLE_DEMO_DEPOSIT=True` на production: это тестовый endpoint ручного пополнения баланса.
