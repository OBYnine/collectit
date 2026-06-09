# CollectIT — платформа для коллекционеров

Веб-приложение для обмена и продажи коллекционных предметов (монеты, значки, марки, винил, фарфор и т.д.).
Эскроу-сделки через ЮKassa, доставка через СДЭК, чат с WebSocket.

---

## Возможности

- **Коллекции и предметы** — CRUD с галереей фотографий, флаг `is_public`, цены, продажа
- **Эскроу-сделки** — деньги удерживаются до подтверждения покупателем, покупательская цена включает сервисный сбор 7%
- **ЮKassa** — пополнение баланса (с webhook-защитой от двойного зачисления)
- **Вывод средств** — ручные заявки на СБП или карту с резервированием суммы на балансе
- **СДЭК** — реальный API + fallback на демо-точки
- **Игровой онбординг** — стартовый квест: телефон, ПВЗ СДЭК, первая коллекция и первый предмет
- **Юридические согласия** — обязательные чекбоксы при регистрации с просмотром текста соглашения и согласия на ПДн
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

**Сервисный сбор:** продавец указывает базовую цену предмета и получает именно ее. Покупатель видит и оплачивает цену с наценкой 7%; при возврате покупателю возвращается вся оплаченная сумма, включая сервисный сбор.

**Данные для доставки:** перед согласием продавца и оплатой покупателя у участников должны быть заполнены телефон и пункт выдачи СДЭК. Телефон перед отправкой в СДЭК нормализуется к формату `+7...`; фейковые номера для заказов не используются.

**Вывод средств:** продавец может создать ручную заявку на вывод через СБП или карту. Сумма сразу резервируется с баланса, администратор обрабатывает заявку в Django Admin: берет в обработку, отмечает выплаченной или отклоняет с возвратом средств на баланс. Карточный вывод в этом MVP предназначен для ручной обработки; для продакшена его лучше заменить токенизированными выплатами через платежного провайдера.

В Django Admin у каждой сделки есть отдельная запись `Deal` со своим UUID. В списке сделок показывается текущая сумма удержания, общий итог удержанных средств, кнопка ручного зачисления продавцу и кнопка возврата удержанных средств покупателю для спорных случаев.

---

## Игровой онбординг

После входа пользователь видит стартовый квест, пока не выполнит базовые шаги подготовки аккаунта:

- заполнить номер телефона;
- выбрать пункт выдачи СДЭК;
- создать первую коллекцию;
- добавить первый предмет.

Страница `/onboarding` показывает прогресс, XP и текущий ранг. Небольшой виджет внизу интерфейса ведет к следующей миссии. Когда шаг впервые становится выполненным, он сохраняется в профиле пользователя и больше не откатывается назад: если позже удалить телефон, ПВЗ, предмет или коллекцию, миссия останется завершенной.

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
| GET/POST | `/api/accounts/withdrawals/`            | Заявки на вывод средств через СБП/карту |
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
| WS     | `ws://host/ws/chats/{id}/`                | WebSocket чата (auth через httpOnly cookie) |
| WS     | `ws://host/ws/notifications/`             | WebSocket уведомлений (auth через httpOnly cookie) |

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

## Деплой на домены

Для `collecit.ru` и `collecit.online` текущий проект нужно разворачивать на VPS или выделенном сервере с Docker daemon и Docker Compose v2. Обычный shared-хостинг с FTP/MySQL не подходит без переработки архитектуры: CollectIT использует PostgreSQL, Redis, Django Channels/WebSocket, Celery worker и Celery beat.

В репозитории есть production-надстройка:

```bash
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Она поднимает Caddy на `80/443`, автоматически выпускает HTTPS-сертификаты и проксирует `collecit.ru`, `www.collecit.ru`, `collecit.online`, `www.collecit.online` в frontend/nginx. Перед запуском DNS `A`-записи этих доменов должны указывать на IP VPS.

Минимальные production-переменные:

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

После выкладки секреты, которые попадали в чат или скриншоты, нужно перевыпустить в панели хостинга/провайдеров.

---

## Тесты

```powershell
# Системные проверки Django
python manage.py check
python manage.py check --deploy
```

---

## Безопасность

- JWT в httpOnly cookie (защита от XSS); refresh-токены ротируются и старые refresh попадают в blacklist
- Legacy JSON JWT endpoints (`/api/auth/token/`, `/api/auth/token/refresh/`) и Bearer JWT auth выключены по умолчанию
- WebSocket-аутентификация по cookie; передача access-token через query string выключена по умолчанию
- Throttling на login (10/мин), register (5/час), payment (10/час), support (30/час), chat_message (120/мин)
- Origin-проверка для небезопасных API-запросов (`POST/PATCH/PUT/DELETE`)
- CSP и security headers в nginx (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
- Ограничения загрузок изображений: размер файла, количество изображений и разрешенные content-type
- Race condition в оплате — защита через `select_for_update + F()`
- Проверки владения коллекциями/предметами: нельзя добавить предмет в чужую коллекцию или открыть сделку по чужому `item_id`
- Идемпотентность ЮKassa-webhook (partial unique constraint в БД)
- Проверка владельца `payment_id` ЮKassa по metadata `user_id`; причины отмены `cancellation_details` возвращаются на фронт и логируются в webhook
- IP whitelist для ЮKassa-webhook (CIDR подсети) + доверенный `X-Real-IP` от nginx
- Демо-пополнение баланса отключено по умолчанию (`ENABLE_DEMO_DEPOSIT=False`)
- CORS_ALLOW_CREDENTIALS, SameSite cookie, `X-CSRFToken` на небезопасных frontend-запросах и Origin protection
- Регистрация требует принятия пользовательского соглашения и согласия на обработку персональных данных; версия, дата, IP и user-agent сохраняются в БД
- Sentry-мониторинг ошибок (опционально)
- Media-ссылки отдаются через frontend/nginx на том же origin (`/media/...`)

Для production обязательно:

```env
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.ru,www.your-domain.ru
CORS_ALLOWED_ORIGINS=https://your-domain.ru,https://www.your-domain.ru
FRONTEND_URL=https://your-domain.ru
JWT_COOKIE_SECURE=True
CSRF_COOKIE_HTTPONLY=False
ENABLE_LEGACY_JWT_ENDPOINTS=False
ENABLE_BEARER_JWT_AUTH=False
ALLOW_WEBSOCKET_QUERY_TOKEN=False
DATA_UPLOAD_MAX_MEMORY_SIZE=12582912
FILE_UPLOAD_MAX_MEMORY_SIZE=5242880
USER_IMAGE_MAX_BYTES=8388608
USER_IMAGE_MAX_COUNT=12
DJANGO_SECURE_SSL_REDIRECT=True
ENABLE_DEMO_DEPOSIT=False
EMAIL_TIMEOUT=10
EMAIL_NOTIFICATIONS_ENABLED=True
```

После включения blacklist для refresh-токенов примените миграции:

```powershell
docker compose --env-file .env.docker exec backend python manage.py migrate
```

---

## Лицензия

MIT
