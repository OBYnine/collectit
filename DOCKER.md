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
- Не включайте `ENABLE_DEMO_DEPOSIT=True` на production: это тестовый endpoint ручного пополнения баланса.
