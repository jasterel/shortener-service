# 🔗 URL Shortener Service

Production-ready backend сервис для сокращения ссылок с поддержкой:

* пользовательских alias
* TTL ссылок
* статистики переходов
* Redis cache
* автоматической очистки ссылок
* Celery background jobs

Стек: **FastAPI + PostgreSQL + Redis + Celery + Docker**

---

# 🚀 Features

### Core

* регистрация и авторизация пользователей (JWT)
* создание коротких ссылок
* кастомные alias
* редирект на оригинальную ссылку
* статистика переходов
* поиск по оригинальному URL

### Performance

* Redis cache для быстрых редиректов
* кеширование статистики

### Background jobs

Celery задачи:

* автоматическое удаление **expired links**
* автоматическое удаление **inactive links**

### Data lifecycle

```
Active link
    |
    | expired / inactive
    v
Archive table
```

Все удаленные ссылки сохраняются в **archive_links**.

---

# 🧱 Architecture

```
FastAPI API
    |
    | REST API
    v
PostgreSQL
    |
    | cache
    v
Redis
    |
    | background tasks
    v
Celery worker
```

Сервисы:

```
shortener_api
shortener_postgres
shortener_redis
shortener_worker
shortener_scheduler
```

---

# 🛠 Tech Stack

| Component        | Technology |
| ---------------- | ---------- |
| API              | FastAPI    |
| Database         | PostgreSQL |
| Cache            | Redis      |
| Background Jobs  | Celery     |
| Auth             | JWT        |
| ORM              | SQLAlchemy |
| Containerization | Docker     |

---

# 📂 Project Structure

```
app
 ├── api
 │   ├── auth.py
 │   ├── links.py
 │   └── redirect.py
 │
 ├── core
 │   ├── config.py
 │   ├── security.py
 │   ├── cache.py
 │   └── celery_app.py
 │
 ├── db
 │   ├── models
 │   │   ├── user.py
 │   │   ├── link.py
 │   │   └── archive.py
 │   └── session.py
 │
 ├── schemas
 │   ├── auth.py
 │   └── link.py
 │
 ├── services
 │   ├── auth_service.py
 │   ├── link_service.py
 │   ├── redirect_service.py
 │   └── cleanup_service.py
 │
 └── tasks
     └── cleanup_tasks.py
```

---

# 🐳 Run with Docker

### Build and start services

```
docker compose up --build
```

Services:

```
API → http://localhost:8000
Swagger → http://localhost:8000/docs
```

---

# 🔐 Authentication

### Register

```
POST /api/auth/register
```

```
{
 "email": "test@test.com",
 "username": "test",
 "password": "123456"
}
```

---

### Login

```
POST /api/auth/login
```

Response:

```
{
 "access_token": "...",
 "token_type": "bearer"
}
```

Используйте токен:

```
Authorization: Bearer <token>
```

---

# 🔗 Link API

### Create link

```
POST /api/links
```

```
{
 "original_url": "https://google.com",
 "custom_alias": "google",
 "expires_at": "2026-04-01T12:00:00"
}
```

---

### Redirect

```
GET /{short_code}
```

Example:

```
http://localhost:8000/google
```

---

### Link statistics

```
GET /api/links/{short_code}/stats
```

---

### Update link

```
PUT /api/links/{short_code}
```

---

### Delete link

```
DELETE /api/links/{short_code}
```

---

### Search by original URL

```
GET /api/links/search?url=https://google.com
```

---

# 📊 Link Statistics

Каждая ссылка хранит:

```
click_count
created_at
last_accessed_at
expires_at
```

---

# ⚡ Cache

Redis используется для:

```
redirect cache
stats cache
```

TTL:

```
CACHE_TTL_SECONDS=300
```

---

# 🔄 Background Jobs

Celery выполняет:

### Expired links cleanup

Удаляет ссылки у которых:

```
expires_at < now
```

### Inactive links cleanup

Удаляет ссылки которые не использовались:

```
last_accessed_at > INACTIVE_DAYS
```

По умолчанию:

```
INACTIVE_DAYS = 30
```

---

# 🗄 Archive

Удаленные ссылки сохраняются в:

```
archive_links
```

Причины:

```
expired
inactive
manual_delete
```

---

# 🧪 Healthcheck

```
GET /
```

Response:

```
{
 "status": "ok"
}
```

---

# 📈 Future Improvements

* rate limiting
* analytics dashboard
* QR code generation
* custom domains
* link preview

---

# 🧪 Testing

## Requirements

Install all dependencies (test deps are in `requirements.txt`):

```bash
pip install -r requirements.txt
```

## Running tests

### Unit + functional tests

```bash
# From the repository root
pytest tests/
```

### With coverage report (terminal)

```bash
coverage run -m pytest tests/
coverage report
```

### With HTML coverage report

```bash
coverage run -m pytest tests/
coverage html
# Open htmlcov/index.html in your browser
```

> The HTML report is committed/attached alongside the code so coverage
> is visible without running the tests locally.

### Run only unit tests

```bash
pytest tests/unit/
```

### Run only functional tests

```bash
pytest tests/functional/
```

## Test structure

```
tests/
├── conftest.py          # fixtures: SQLite DB, mock Redis, TestClient, auth helpers
├── unit/
│   ├── test_security.py     # hash/verify/JWT helpers
│   └── test_link_service.py # short-code generation, cache key helpers
├── functional/
│   ├── test_auth.py         # POST /api/auth/register, /api/auth/login
│   ├── test_links.py        # full CRUD + healthcheck
│   ├── test_redirect.py     # GET /{short_code} redirect logic
│   └── test_cleanup.py      # CleanupService (expired & inactive links)
└── load/
    └── locustfile.py        # Locust load scenarios
```

## How tests are isolated

## Как изолируются тесты

* **База данных** — SQLite файл (`test_url_shortener.db`) удаляется и создаётся заново перед каждым тестом с помощью фикстуры `db`. PostgreSQL не требуется.

* **Redis** — заменяется на `unittest.mock.MagicMock`, который внедряется до импорта любых модулей приложения. Состояние мока автоматически сбрасывается перед каждым тестом.

* **Аутентификация** — обе зависимости `get_db` (из `deps.py` и локальная из `auth.py`) переопределяются и используют одну и ту же тестовую сессию.

## Нагрузочное тестирование с Locust

Запустите приложение (например, через Docker Compose), затем:

```bash
# Интерактивный веб-интерфейс на http://localhost:8089
locust -f tests/load/locustfile.py --host http://localhost:8000

# Headless запуск — 50 пользователей, 10 новых пользователей/с, 60 секунд,
# сохраняет HTML-отчёт
locust -f tests/load/locustfile.py \
       --host http://localhost:8000 \
       --headless -u 50 -r 10 --run-time 60s \
       --html tests/load/report.html
```

Определены два класса пользователей:

| Class | Weight | Scenario |
|---|---|---|
| `AnonymousUser` | 4 | Массовое создание ссылок (60 %), редирект (30 %), статистика/поиск (10 %) |
| `AuthenticatedUser` | 1 | Полный жизненный цикл: регистрация → создание → редирект (тёплый кэш) → удаление |

---

# 👨‍💻 Author

TG: @jasterel

Maksim Anokhin