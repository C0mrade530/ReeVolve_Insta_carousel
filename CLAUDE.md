# RealPost Pro — CLAUDE.md

## Что это за проект

RealPost Pro — SaaS-платформа для риелторов. Автоматически генерирует Instagram-карусели (1080×1350, формат 4:5) с помощью AI и публикует их через Instagram API.

Полный цикл: тема → AI-текст (3-шаговый pipeline: генерация → самооценка → рефайн) → Pillow-рендеринг слайдов → публикация через instagrapi.

## Стек

### Backend (FastAPI + Python 3.12)
- **FastAPI** — async REST API с SSE для прогресса генерации
- **Supabase** — PostgreSQL + Auth (JWT). Admin-клиент для записи, anon-клиент для auth
- **CometAPI** — OpenAI-совместимый прокси для Claude. Модель: `claude-sonnet-4-6`
- **Extended thinking**: `extra_body={"thinking": {"type": "enabled", "budget_tokens": 2048}}`, temperature MUST be 1.0
- **Pillow** — генерация изображений 1080×1350
- **instagrapi 2.1.2** — публикация каруселей в Instagram
- **Fernet** — шифрование Instagram-сессий

### Frontend (React 18 + Vite + Tailwind)
- SPA с React Router
- Axios + глобальный error bus (Set<Function> listeners в client.js)
- Toast-система, ErrorBoundary
- HTML5 Drag & Drop календарь
- Страницы: Generator, Dashboard, Calendar, Competitors, Analytics, Accounts, Templates, ContentPlan, Parser

### Infrastructure
- Docker: `python:3.12-slim` + Pillow system deps
- Instagram proxy: `socks5h://` через mobileproxy.space
- Media хранение: локальная FS через StaticFiles

## Структура проекта

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, middlewares, routers
│   ├── config.py                  # Pydantic Settings, .env loading
│   ├── database.py                # Supabase singleton clients (thread-safe)
│   ├── api/
│   │   ├── deps.py                # Auth (JWT), DB dependency injection
│   │   ├── auth.py                # Login/register
│   │   ├── accounts.py            # Instagram accounts CRUD + login
│   │   ├── carousels.py           # Генерация, batch, publish, SSE (~1700 строк)
│   │   ├── listings.py            # Объекты недвижимости (CIAN парсер)
│   │   ├── analytics.py           # Dashboard stats, breakdown, recommendations
│   │   ├── competitors.py         # Scrape Reels → AI analyze → rewrite → carousel
│   │   ├── sessions.py            # Session pool + proxy management
│   │   ├── monitoring.py          # Task monitor + DLQ endpoints
│   │   ├── scheduler.py           # Publish scheduling
│   │   ├── templates.py           # Design templates
│   │   └── expert.py              # Expert template upload
│   ├── middleware/
│   │   └── rate_limit.py          # Token Bucket per user (JWT sub)
│   ├── services/
│   │   ├── task_monitor.py        # DLQ + running tasks (thread-safe)
│   │   ├── generator/
│   │   │   ├── content.py         # 3-step AI text: draft → evaluate → refine
│   │   │   ├── image.py           # Pillow slide rendering
│   │   │   ├── pipeline.py        # Full pipeline: text → slides → DB (asyncio.to_thread)
│   │   │   ├── expert_template.py # Expert photo/template resolution
│   │   │   ├── font_manager.py    # Font loading
│   │   │   └── ai_image.py        # AI image generation
│   │   ├── publisher/
│   │   │   ├── instagram.py       # instagrapi wrapper, login, publish, music
│   │   │   ├── safety.py          # Delays, daily limits, warmup
│   │   │   ├── session_pool.py    # Session rotation + Proxy pool (thread-safe)
│   │   │   └── stats.py           # Engagement stats fetcher
│   │   ├── competitor/
│   │   │   ├── scraper.py         # Instagram Reels scraper
│   │   │   └── parser.py          # AI analysis of viral Reels
│   │   └── parser/
│   │       └── cian.py            # CIAN listing parser
│   └── utils/
│       ├── encryption.py          # Fernet encrypt/decrypt session data
│       └── prompts.py             # AI prompt templates
├── requirements.txt
├── Dockerfile
└── .env

frontend/
├── src/
│   ├── api/client.js              # Axios + error bus + 401 retry
│   ├── contexts/
│   │   ├── ToastContext.jsx        # Toast notifications
│   │   └── AccountContext.jsx      # Current account state
│   ├── pages/
│   │   ├── Generator.jsx          # Основная генерация (topic + property tabs)
│   │   ├── Dashboard.jsx          # Главная с метриками
│   │   ├── Calendar.jsx           # Drag & drop публикационный календарь
│   │   ├── Competitors.jsx        # Анализ конкурентов, Reels → карусели
│   │   ├── Analytics.jsx          # Breakdown, графики, рекомендации
│   │   ├── Accounts.jsx           # Управление IG аккаунтами
│   │   ├── WeekGenerator.jsx      # Batch генерация на неделю
│   │   ├── ContentPlan.jsx        # Контент-план с approval workflow
│   │   ├── Parser.jsx             # CIAN парсер
│   │   ├── CarouselEditor.jsx     # Редактор карусели
│   │   ├── Templates.jsx          # Шаблоны дизайна
│   │   └── Login.jsx
│   └── components/
│       ├── Accounts/
│       ├── Analytics/
│       ├── Carousels/
│       ├── ContentPlan/
│       ├── Layout/
│       ├── Parser/
│       └── MusicPicker.jsx
└── vite.config.js
```

## Ключевые паттерны

### Auth
- Supabase JWT → `get_current_user()` в deps.py
- `get_db()` возвращает admin-клиент (bypass RLS)
- Rate limiter извлекает user_id из JWT `sub` claim

### Генерация каруселей
- SSE через `StreamingResponse` + `asyncio.Queue` → React `fetch` + `ReadableStream`
- Pipeline: async LLM call → CPU-bound Pillow через `asyncio.to_thread()` → DB update
- 7 слайдов (topic) или 6 слайдов (property)

### Instagram
- Session Pool: round-robin с cooldown 30 мин, max 3 failures → auto-disable
- Proxy Pool: health monitoring, latency tracking, max 5 failures
- Safety: min 7200 сек между постами, max 5 постов/день

### In-memory синглтоны (thread-safe с threading.Lock)
- SessionPool, ProxyPool — `session_pool.py`
- TaskMonitor + DLQ — `task_monitor.py`
- Database clients — `database.py`
- Rate limit buckets — `rate_limit.py`

## Таблицы БД (Supabase/PostgreSQL)

- `instagram_accounts` — owner_id, username, session_data (encrypted), proxy, is_active
- `carousels` — owner_id, account_id, type, status, slides (JSONB), caption, generation_params
- `publish_schedules` — carousel_id, account_id, scheduled_time, status
- `property_listings` — created_by, source_url, title, price, photos, carousel_generated
- `post_stats` — carousel_id, account_id, likes, comments, saves, reach, engagement_rate
- `failed_tasks` — task_id, task_type, owner_id, error, retry_count, status

## Что уже сделано

### Фичи (все работают)
1. Переход с GPT на Claude через CometAPI
2. 3-шаговая система промптов (draft → evaluate → refine)
3. Progress UI через SSE
4. Полная система property каруселей (CIAN парсер → генерация → рендеринг)
5. Toast-уведомления + глобальный API error interceptor
6. Drag & drop интерактивный календарь публикаций
7. Instagram session rotation + proxy pool management
8. Rate-limiting на эндпоинтах генерации
9. Task monitoring + Dead Letter Queue
10. Content analytics: breakdown по типу/времени/шаблону с рекомендациями
11. AI competitor analysis: парсинг Reels конкурентов → перегенерация каруселей
12. Batch генерация на неделю с approval workflow

### Исправленные баги (12 штук)
- aiohttp в requirements.txt
- Mismatched frontend defaults в Competitors
- Формула частоты в analytics
- traceback.format_exception вместо format_exc
- Fragile account data mutation в competitors
- Расширенные color schemes
- Thread-safe синглтоны (SessionPool, ProxyPool, TaskMonitor, Database)
- Rate limiter: JWT sub вместо token fragment
- Dashboard: count-запросы вместо полной выборки
- Data isolation: user_id фильтрация в listings
- Pipeline: asyncio.to_thread для CPU-bound Pillow
- Double-check locking для всех singleton init

## Что уже обновлено (v2.1, Март 2026)

### Критические фиксы (10 штук — сделано в Claude Code)
- Structured JSON logging + RequestIdMiddleware
- CORS из settings вместо hardcode
- Encryption key обязателен в production
- Dockerfile: non-root user, --workers 4, без --reload
- Health-check: /health с проверкой DB/storage/LLM
- Password hashing (bcrypt)
- Input validation (Pydantic strict)
- Error correlation через request_id
- Secure headers middleware
- Production config validation

### Промпты (частично обновлено)
- TOPIC_STRATEGIST_SYSTEM обновлён: алгоритм Instagram 2026, 14 формул, триггеры пересылки
- TOPIC_STRATEGIST_USER обновлён: `hook_title_alt`, `share_trigger`, `{top_posts_context}`
- SLIDES_WRITER, VIRAL_ANALYST, REFINE — ЕЩЁ НЕ ОБНОВЛЕНЫ (задача для Claude Code)

## Что НЕ сделано — ТЕКУЩИЙ ПЛАН

Следующий этап: Универсальная мульти-нишевая платформа + виральность.
Подробности в TODO.md.

## Команды

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Docker
docker-compose up --build
```

## Правила для Claude

1. Язык интерфейса — русский. Код и комментарии — английский
2. НЕ менять CometAPI конфигурацию (openai_base_url, model names)
3. Extended thinking: temperature MUST be 1.0, `extra_body={"thinking": {"type": "enabled", "budget_tokens": 4096}}`
4. Pillow рендеринг: всегда 1080×1350 (4:5 формат Instagram)
5. Все in-memory синглтоны должны быть thread-safe (threading.Lock)
6. Все DB запросы к user-owned данным ОБЯЗАТЕЛЬНО фильтруются по user_id/owner_id/created_by
7. CPU-bound операции (Pillow, file I/O) через asyncio.to_thread()
8. Не использовать bare `except: pass` — всегда логировать, использовать конкретные типы исключений
9. Выполняй задачи поэтапно, не параллельно. После каждого изменения — проверяй синтаксис
10. Все API ответы в едином формате: `{"detail": "message"}` для ошибок
