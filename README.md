# CollectIT — платформа для коллекционеров

Веб-приложение для обмена и продажи коллекционных предметов (монеты, значки, марки, винил, фарфор и т.д.).
Эскроу-сделки через ЮKassa, доставка через СДЭК, чат с WebSocket.

---

## Возможности

- **Коллекции и предметы** — CRUD с галереей фотографий, флаг `is_public`, цены, продажа
- **Эскроу-сделки** — деньги удерживаются до подтверждения покупателем
- **ЮKassa** — пополнение баланса (с webhook-защитой от двойного зачисления)
- **СДЭК** — реальный API + fallback на демо-точки
- **Чат** — WebSocket (Django Channels), HTTP-fallback
- **Уведомления** — внутри платформы + realtime-события для новых сообщений и счетчиков + email-дублирование
- **Рейтинги** — отзывы продавцу после сделки
- **Новости** — мульти-фото, lightbox, роль `is_news_editor`
- **Поддержка** — тикет-система с темами и ответом админа
- **Вишлист** — лайки + уведомления о смене цены

---

## Стек

| Часть | Технологии |
|-------|-----------|
| Backend | Django 5.2 + DRF + SimpleJWT (httpOnly cookie) + Channels + Celery |
| Frontend | React 18 + React Router 6 + Tailwind CSS v3 + TanStack Query |
| БД | PostgreSQL |
| Realtime | WebSocket (Daphne) + Redis (Channels layer) |
| Tasks | Celery + Redis |
| Карта | react-leaflet v4 + CartoDB Dark Matter |
| Платежи | ЮKassa (test) |
| Доставка | СДЭК API |
| Мониторинг | Sentry (бэк + фронт) |
| Шрифты | Outfit (UI), JetBrains Mono (числа) |

---

## Структура

```
collecta/
├── backend/                  # Django REST API + WebSocket
│   ├── collectit/            # settings, urls, asgi, celery
│   ├── accounts/             # User, Transaction, JWT cookie auth
│   ├── collectibles/         # Collection, Item, Wishlist
│   ├── news/                 # Article, ArticleImage
│   ├── search/               # Полнотекстовый поиск предметов
│   ├── notifications/        # Notification
│   ├── chats/                # Chat, Message, Consumer (WS), tasks (Celery)
│   ├── support/              # SupportTicket
│   ├── requirements.txt
│   └── .env.example          # Шаблон секретов (свой .env создаёте сами)
└── frontend/                 # React SPA
    └── src/
        ├── api/client.js     # Cookie-based fetch wrapper
        ├── components/       # TopNav, ErrorBoundary, Skeleton
        ├── context/          # UserContext (React Context)
        ├── hooks/            # useDebounce, useChatSocket
        ├── pages/            # Profile, News, Search, Login, Settings, ...
        ├── utils/            # config, format, queryClient, sentry
        └── styles/global.css
```

---

## Быстрый старт (dev-режим, без Redis)

### 1. PostgreSQL

```sql
CREATE DATABASE collectit_db;
CREATE USER collectit_user WITH PASSWORD 'collectit_pass';
GRANT ALL PRIVILEGES ON DATABASE collectit_db TO collectit_user;
```

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
copy .env.example .env       # Заполните DJANGO_SECRET_KEY, БД и т.д.
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Админка: http://localhost:8000/admin/

### 3. Frontend

```powershell
cd frontend
copy .env.example .env
npm install
npm start
```

Открыть: http://localhost:3000/

---

## Быстрый старт через Docker

Поднимает PostgreSQL, Redis, backend, Celery и frontend/nginx:

```powershell
copy .env.docker.example .env.docker
docker compose --env-file .env.docker up --build
```

Приложение: http://localhost:3000/

Админка: http://localhost:3000/admin/

По умолчанию наружу публикуется только frontend/nginx. PostgreSQL, Redis и прямой
backend-порт привязаны к `127.0.0.1`, чтобы не открывать служебные порты при
запуске на сервере.

Создать администратора:

```powershell
docker compose --env-file .env.docker exec backend python manage.py createsuperuser
```

Подробнее: [`DOCKER.md`](DOCKER.md)

---

## Production-режим (с Redis)

В этом режиме работают:
- WebSocket с межпроцессной синхронизацией (несколько worker'ов)
- Точный 60-секундный таймер прибытия посылки (вне HTTP)
- Retry создания заказа СДЭК

```powershell
# 1. Поднять Redis (Memurai на Windows / Docker / sudo apt install redis)
docker run -d -p 6379:6379 --name redis redis:7

# 2. В backend/.env прописать:
#    REDIS_URL=redis://127.0.0.1:6379/0

# 3. Запуск ASGI-сервера (вместо runserver)
.\venv\Scripts\daphne -b 0.0.0.0 -p 8000 collectit.asgi:application

# 4. В отдельном окне — Celery worker
.\venv\Scripts\celery -A collectit worker -l info --pool=solo
```

---

## Эскроу-сделка — флоу

```
purchase -> seller "Согласен" -> buyer "Оплатить X RUB" -> деньги в эскроу
                |
seller "Сдал в СДЭК" -> СДЭК-заказ создан -> +60с (Celery) ->
                |
статус arrived (деньги ВСЁ ЕЩЁ в эскроу) ->
                |
buyer "Я получил товар" -> деньги переводятся продавцу -> completed
                |
completed-сделка остается в архиве у покупателя и продавца; каждый может удалить архивный чат только у себя
```

**Важно:** деньги уходят продавцу **только** после явного подтверждения получения покупателем.

В Django Admin у каждой сделки есть отдельная запись `Deal` со своим UUID. В списке сделок показывается текущая сумма удержания, общий итог удержанных средств, кнопка ручного зачисления продавцу и кнопка возврата удержанных средств покупателю для спорных случаев.

---

## API

| Метод  | URL                                       | Описание                        |
|--------|-------------------------------------------|---------------------------------|
| POST   | `/api/accounts/register/`                 | Регистрация                     |
| POST   | `/api/accounts/cookie-login/`             | Логин (httpOnly cookie)         |
| POST   | `/api/accounts/cookie-refresh/`           | Refresh токен                   |
| POST   | `/api/accounts/cookie-logout/`            | Выход                           |
| GET    | `/api/accounts/me/`                       | Текущий профиль                 |
| GET    | `/api/accounts/users/{username}/`         | Публичный профиль               |
| POST   | `/api/accounts/create-payment/`           | Создать платёж ЮKassa           |
| POST   | `/api/accounts/verify-payment/`           | Проверить платёж ЮKassa и причину отмены |
| POST   | `/api/accounts/yookassa-webhook/`         | Webhook от ЮKassa (IP-проверка) |
| GET/POST | `/api/collections/collections/`         | CRUD коллекций                  |
| GET/POST | `/api/collections/items/`               | CRUD предметов                  |
| POST   | `/api/collections/wishlist/{itemId}/`     | Toggle вишлист                  |
| GET    | `/api/search/?q=...`                      | Поиск                           |
| GET/POST | `/api/news/articles/`                   | Новости (POST — для редакторов) |
| GET    | `/api/notifications/`                     | Уведомления                     |
| GET/POST | `/api/chats/`                           | Чаты                            |
| POST   | `/api/chats/{id}/agree/`                  | Продавец согласен               |
| POST   | `/api/chats/{id}/pay/`                    | Покупатель оплачивает           |
| POST   | `/api/chats/{id}/ship/`                   | Продавец отправил               |
| POST   | `/api/chats/{id}/confirm-receipt/`        | Покупатель получил, деньги продавцу |
| POST   | `/api/chats/{id}/rate/`                   | Оценка                          |
| DELETE | `/api/chats/{id}/hide/`                   | Локально удалить чат у текущего пользователя |
| POST   | `/api/support/tickets/`                   | Создать обращение               |
| WS     | `ws://host/ws/chats/{id}/?token=...`      | WebSocket чата                  |

В ответах Chat API есть поле `support_code` вида `CHAT-123`. Пользователь видит его в окне переписки и может отправить администратору; в Django Admin этот код ищется в `Chats` и `Deals`.

`/api/search/` поддерживает фильтры `q`, `min_price`, `max_price`, `has_photo=1` и сортировку `ordering=-created_at|created_at|price|-price`.
В ответах предметов есть `image` для совместимости и массив `images[]` для галереи; фронт показывает листание фотографий в модалках предметов.

---

## AI-импорт новостей

CollectIT может автоматически брать свежие новости с `https://www.numizmatik.ru/news`, отправлять пачку найденных публикаций в Google Gemini и публиковать на `/news` одну большую обзорную статью. Текст генерируется своими словами, а исходные изображения скачиваются в `media/news/images/` и прикрепляются к этой статье галереей.
В тексте новостей поддерживается безопасное выделение жирным через `**важный фрагмент**`; HTML из текста не исполняется.

Настройки:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODEL=gemini-2.5-flash
NEWS_IMPORT_SOURCE_URL=https://www.numizmatik.ru/news
NEWS_IMPORT_ENABLED=False
NEWS_IMPORT_INTERVAL_MINUTES=360
NEWS_IMPORT_LIMIT=5        # сколько исходных новостей объединить в один обзор
NEWS_IMPORT_MAX_IMAGES=5
NEWS_IMPORT_REQUEST_TIMEOUT=60
```

Ручной запуск:

```powershell
docker compose --env-file .env.docker exec backend python manage.py import_numizmatik_news --limit 5
```

Проверка парсинга без Gemini и без публикации:

```powershell
docker compose --env-file .env.docker exec backend python manage.py import_numizmatik_news --limit 3 --dry-run
```

Для автоматического запуска включите `NEWS_IMPORT_ENABLED=True` и поднимите `celery`, `celery-beat`.

Повторный запуск с тем же набором источников не создаёт дубль. Чтобы перегенерировать уже созданный обзор, используйте `--update-existing`.
Если основная модель Gemini вернёт ошибку, импорт автоматически повторит запрос через `GEMINI_FALLBACK_MODEL`.

---

## Telegram-уведомления поддержки

Backend может отправлять администратору Telegram-сообщение при создании нового тикета и при новом сообщении пользователя в тикете.

```env
TELEGRAM_NOTIFICATIONS_ENABLED=True
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_IDS=
TELEGRAM_REQUEST_TIMEOUT=10
```

Чтобы получить `TELEGRAM_ADMIN_CHAT_IDS`, напишите боту `/start` из админского Telegram-аккаунта и выполните:

```powershell
docker compose --env-file .env.docker exec backend python manage.py telegram_get_updates
```

Скопируйте найденный `chat_id` в `.env.docker` и перезапустите backend.

---

## Тесты

```powershell
# Системные проверки Django
python manage.py check
python manage.py check --deploy
```

---

## Безопасность

- JWT в httpOnly cookie (защита от XSS)
- Throttling на login (10/мин), register (5/час), payment (10/час)
- Origin-проверка для небезопасных API-запросов (`POST/PATCH/PUT/DELETE`)
- CSP и security headers в nginx (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
- Race condition в оплате — защита через `select_for_update + F()`
- Проверки владения коллекциями/предметами: нельзя добавить предмет в чужую коллекцию или открыть сделку по чужому `item_id`
- Идемпотентность ЮKassa-webhook (partial unique constraint в БД)
- Проверка владельца `payment_id` ЮKassa по metadata `user_id`; причины отмены `cancellation_details` возвращаются на фронт и логируются в webhook
- IP whitelist для ЮKassa-webhook (CIDR подсети) + доверенный `X-Real-IP` от nginx
- Демо-пополнение баланса отключено по умолчанию (`ENABLE_DEMO_DEPOSIT=False`)
- CORS_ALLOW_CREDENTIALS, SameSite cookie и CSRF/Origin protection
- Sentry-мониторинг ошибок (опционально)
- Media-ссылки отдаются через frontend/nginx на том же origin (`/media/...`)

Для production обязательно:

```env
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.ru,www.your-domain.ru
CORS_ALLOWED_ORIGINS=https://your-domain.ru,https://www.your-domain.ru
FRONTEND_URL=https://your-domain.ru
JWT_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=True
ENABLE_DEMO_DEPOSIT=False
EMAIL_TIMEOUT=10
EMAIL_NOTIFICATIONS_ENABLED=True
```

---

## Лицензия

MIT
