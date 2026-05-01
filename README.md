# CollectIT — платформа для коллекционеров

Веб-приложение для обмена и продажи коллекционных предметов (монеты, значки, марки, винил, фарфор и т.д.).
Эскроу-сделки через ЮKassa, доставка через СДЭК, чат с WebSocket.

---

## Возможности

- **Коллекции и предметы** — CRUD с фотографиями, флаг `is_public`, цены, продажа
- **Эскроу-сделки** — деньги удерживаются до подтверждения покупателем
- **ЮKassa** — пополнение баланса (с webhook-защитой от двойного зачисления)
- **СДЭК** — реальный API + fallback на демо-точки
- **Чат** — WebSocket (Django Channels), HTTP-fallback
- **Уведомления** — внутри платформы
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
buyer ставит оценку -> seller подтверждает -> чат уходит в архив
```

**Важно:** деньги уходят продавцу **только** после явного подтверждения получения покупателем.

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
| POST   | `/api/support/tickets/`                   | Создать обращение               |
| WS     | `ws://host/ws/chats/{id}/?token=...`      | WebSocket чата                  |

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
- Race condition в оплате — защита через `select_for_update + F()`
- Идемпотентность ЮKassa-webhook (partial unique constraint в БД)
- IP whitelist для ЮKassa-webhook (CIDR подсети)
- CORS_ALLOW_CREDENTIALS, CSRF protection
- Sentry-мониторинг ошибок (опционально)

---

## Лицензия

MIT
