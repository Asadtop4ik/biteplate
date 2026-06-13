# BitePlate (web)

BitePlate is the enterprise **FastAPI + HTMX** port of the original BitePlate
console OOP prototype (a design-patterns assignment). It keeps all **9 design
patterns** from the prototype intact in a pure `domain/` layer and maps each one
onto a real production tool — the Singleton history log becomes a Postgres-backed
repository, kitchen Commands run asynchronously on Celery, the Observer subject
publishes over Redis Pub/Sub and streams to the browser via SSE, and the
permission model is enforced on every request through a FastAPI dependency. The
patterns themselves were not rewritten; the infra layer rebuilds plain domain
objects from the database so the original OOP behaviour still runs on top of
Postgres, Redis and Celery.

## Pattern → tool

| Pattern | Where it lives | Production tool it maps to |
|---|---|---|
| **Singleton** (`OrderHistoryLog`) | `app/domain/history.py` → `app/infra/repositories.py` | `SqlAlchemyHistoryRepository` backed by Postgres (one shared audit log replaced by a single table). |
| **Command** (+ undo) | `app/domain/kitchen.py` → `app/infra/tasks.py` | Celery tasks (`prepare`/`cancel`/`expedite`); `revert_status_task` is the compensating undo. Broker = Redis (RabbitMQ optional). |
| **Observer** (`Order` subject) | `app/domain/orders.py` / `app/domain/notifications.py` → `app/infra/events.py` | `RedisPublishObserver` publishes status changes to Redis **Pub/Sub**; the SSE endpoint (`app/web/routers/sse.py`) streams them to HTMX. |
| **Strategy** | `app/domain/pricing.py` | Standard / Happy Hour / Loyalty pricing; selected at bill time. Pure domain. |
| **State** | `app/domain/tables.py` | Table lifecycle Free → Reserved → Occupied → Awaiting Bill → Cleared. Pure domain; state label persisted as a column. |
| **Factory Method** | `app/domain/menu.py` (`MenuFactory`) | Builds concrete `MenuItem` subclasses by *kind* when rebuilding rows from the DB. Pure domain. |
| **Composite** | `app/domain/menu.py` (`ComboMeal`) | A combo is a `MenuItem` composed of child items; rebuilt recursively in the repo. Pure domain. |
| **Facade** | `app/domain/billing.py` (`BillingFacade`) | One entry point over pricing + tax + tip + split. Pure domain. |
| **Iterator** | `app/domain/history.py` (`__iter__`) | Traversal independent of storage; the Postgres repo re-implements `__iter__` for the same analytics queries. |
| **Permission model** | `app/domain/staff.py` → `app/deps.py` | Session login stores `staff_code`; `require_permission(perm)` rebuilds the domain `Staff` and calls `staff.require(perm)`, raising `403` on denial. |

The domain `Order` (Observer subject) and `Bill` (Strategy context) also compose
smaller domain pieces, and `OrderItem` is COMPOSITION over its `Order` — these
relationships are preserved verbatim from the prototype.

## Architecture

```
            ┌─────────────────────────────────────────────┐
  browser   │  HTMX 2.x + SSE  (templates: pages/partials) │
   (HTTP)   └───────────────────────┬─────────────────────┘
                                     │
        ┌────────────────────────────▼────────────────────────────┐
  web   │  FastAPI routers  (app/web/routers/*, app/deps.py)        │
        │  session auth · require_permission · HTMX partials        │
        └────────────────────────────┬────────────────────────────┘
                                     │
      service ┌──────────────────────▼──────────────────────┐
              │  app/services/*  — orchestrate use cases     │
              └──────────────────────┬──────────────────────┘
                                     │   (rebuilds pure objects)
       domain ┌──────────────────────▼──────────────────────┐
              │  app/domain/*  — the 9 patterns, PURE PYTHON  │
              │  no DB / Redis / Celery / FastAPI imports     │
              └──────────────────────┬──────────────────────┘
                                     │
        infra ┌──────────────────────▼──────────────────────┐
              │  SQLAlchemy + Alembic (Postgres) · Redis      │
              │  Pub/Sub & sessions · Celery tasks (broker)   │
              │  db · models · repositories · events · tasks  │
              └─────────────────────────────────────────────┘
```

**Rule: the `domain/` layer is pure.** It imports nothing from `infra`, `web`,
SQLAlchemy, Redis, Celery or FastAPI. Infra rebuilds domain objects out of ORM
rows (Factory/Composite for the menu, State for tables, the Observer subject for
orders) so the patterns keep running unchanged on top of real services.

## Run with Docker

```bash
# from the repo root (one level up from backend/)
docker compose up --build
```

Open http://localhost:8000 and log in as **M01 / manager** (the manager has every
permission, so it can reach all screens). The web container runs Alembic
migrations and seeds the database on start (`RUN_MIGRATIONS=1`), so no extra steps
are needed.

Seeded logins (password == role):

| Code | Role | Password |
|---|---|---|
| `W01` | waiter | `waiter` |
| `C01` | chef | `chef` |
| `K01` | cashier | `cashier` |
| `M01` | manager | `manager` |

Optional profiles:

```bash
# Flower (Celery UI) :5555  +  Adminer (DB UI) :8080
docker compose --profile monitoring up

# add a RabbitMQ broker (management UI :15672), then point Celery at it:
docker compose --profile rabbitmq up
#   set BROKER_URL=amqp://guest:guest@rabbitmq:5672// for web + worker
```

## Run locally (no Docker)

Needs a local **PostgreSQL** and **Redis** running. From `backend/`:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'

# point at your local services (see .env.example for the localhost variants)
export DATABASE_URL='postgresql+psycopg://biteplate:biteplate@localhost:5432/biteplate'
export REDIS_URL='redis://localhost:6379/0'

.venv/bin/alembic upgrade head        # create schema
.venv/bin/python -m app.infra.seed     # seed staff / menu / tables
.venv/bin/uvicorn app.main:app --reload
```

To process kitchen Commands locally, also run a Celery worker:

```bash
.venv/bin/celery -A app.infra.tasks.celery_app worker -l info
```

## Tests

The full suite runs on **SQLite** with Celery forced into eager mode — **no
Postgres, Redis or broker required**:

```bash
cd backend
.venv/bin/python -m pytest -q     # 39 passed
```

(A locally reachable Redis is only used by the session-roundtrip auth test; most
tests override the `current_staff` dependency and never touch Redis.)

## The 7 flows

- **Login** — session auth (`POST /login`); credentials checked against bcrypt
  hashes, `staff_code` + `role` stored in the Redis-backed session.
- **Tables / State** — table cards advance through the State machine
  (Free → Reserved → Occupied → Awaiting Bill → Cleared).
- **Order / Factory + Composite** — build an order from menu items rebuilt via
  `MenuFactory`; combos are `ComboMeal` composites priced from their children.
- **Kitchen / Command + Celery** — prepare / cancel / expedite are Commands
  dispatched as Celery tasks; `revert_status_task` is the compensating undo.
- **Pricing / Strategy** — choose Standard, Happy Hour, or Loyalty pricing when
  building the bill.
- **Bill / Facade** — `BillingFacade` assembles subtotal + tax + tip + split
  behind one call.
- **Report / Iterator** — analytics (revenue, top items, per-table) iterate the
  history repository regardless of its storage.

Plus: **live SSE kitchen updates** — every Command publishes to Redis Pub/Sub and
the `/sse/kitchen` stream pushes pre-rendered HTMX cards onto the board in real
time; and **permission security** — every protected route is guarded by
`require_permission(...)`, which reuses the domain `Staff.require()` check and
returns `403` when a role lacks the permission.

## Project layout

```
backend/
├── app/
│   ├── main.py            FastAPI app: session middleware, static, routers
│   ├── config.py          settings (DATABASE_URL, REDIS_URL, BROKER_URL, ...)
│   ├── deps.py            DB/Redis deps, current_staff, require_permission
│   ├── domain/           PURE patterns: menu, orders, tables, pricing,
│   │                      kitchen, billing, staff, history, notifications
│   ├── services/         use-case orchestration (auth, tables, ordering,
│   │                      kitchen, billing, reporting)
│   ├── infra/            db · models · repositories · events · tasks · seed
│   └── web/
│       ├── routers/      auth, seat, order, kitchen, billing, report, sse
│       ├── templates/    base · pages/* · partials/*
│       ├── static/       htmx.min.js · sse.js · app.css
│       ├── htmx.py        render helpers (full page vs HTMX partial)
│       └── schemas.py
├── alembic/              migrations (env.py, versions/)
├── tests/               pytest suite (SQLite, eager Celery)
├── pyproject.toml
├── Dockerfile
└── entrypoint.sh        runs migrations + seed when RUN_MIGRATIONS=1
```
