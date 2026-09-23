# PLAN — GOAL 0: Project foundation

Status: awaiting implementation by Codex.

## Goal

Stand up the minimum executable skeleton for the wallet: a Django + DRF
backend talking to PostgreSQL, a React + TypeScript frontend, a pytest
suite that runs against a real PostgreSQL instance, Docker Compose to
run all three locally, and a GitHub Actions workflow that executes both
test suites. The only endpoint is a health check that proves the
database connection is live. No money, no accounts, no domain logic.

The foundation also locks in three framework-level settings that later
financial correctness depends on, so they are decided once, here, rather
than discovered during GOAL 3.

## Affected components

Everything is new. Nothing existing is modified except `README.md`.

**Repository root**

- `.env.example`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `README.md` — replace the "Setup" placeholder with real instructions

**backend/** (presentation + config only; other layers are not created yet)

- `backend/manage.py`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/pytest.ini`
- `backend/Dockerfile`
- `backend/config/__init__.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/config/wsgi.py`
- `backend/config/asgi.py`
- `backend/src/__init__.py`
- `backend/src/presentation/__init__.py`
- `backend/src/presentation/controllers/__init__.py`
- `backend/src/presentation/controllers/health.py`
- `backend/tests/__init__.py`
- `backend/tests/test_health.py`

**frontend/**

- `frontend/package.json`
- `frontend/tsconfig.json`, `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/Dockerfile`
- `frontend/.env.example`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/theme/tokens.css`
- `frontend/src/index.css`

## Layer assignment

| Unit | Layer | Why |
|---|---|---|
| `config/*` | infrastructure (config) | Django wiring, settings, URL root. Framework concern, nothing else. |
| `src/presentation/controllers/health.py` | presentation | An HTTP endpoint. It performs one trivial DB liveness query and returns a status document. It has no business meaning, so it needs no layer beneath it. |
| `src/api/client.ts` | frontend infrastructure | Single place that knows the backend base URL and error shape. |
| `tests/test_health.py` | tests | Integration test; touches the real database. |

`domain/`, `application/`, and `infrastructure/persistence/` are **not**
created in this goal. They appear in GOAL 1 when there is something real
to put in them. Do not create empty packages in anticipation.

## Patterns

None are introduced. This goal is plumbing.

The health endpoint is deliberately *not* routed through a facade, a
command, or a repository. Doing so would be the first instance of
pattern theater this project is explicitly trying to avoid. A liveness
probe has no domain behavior to protect.

Layered architecture and the presentation/business separation exist
structurally from this point on and are enforced from GOAL 1 forward.

## Invariants at risk

No `INV-*` invariant is exercised by this goal — there is no money in
the system yet. Stating that plainly is more honest than manufacturing
citations.

However, three settings decided here determine whether INV-3, INV-4 and
INV-5 are *achievable* later, and getting them wrong is expensive to
undo:

- **`ATOMIC_REQUESTS = False`** — relates to INV-4 (atomicity). Django's
  `ATOMIC_REQUESTS = True` wraps every HTTP request in a transaction,
  which moves the transaction boundary into the presentation layer and
  directly contradicts `references/architecture.md` ("exactly one place
  opens the transaction: the application use case"). It must be off, and
  the setting must carry a comment saying why.
- **Isolation level `READ COMMITTED`** (PostgreSQL default, set
  explicitly) — relates to INV-3 (sufficient funds). Our concurrency
  strategy is pessimistic row locking via `SELECT ... FOR UPDATE`, which
  is correct under READ COMMITTED. Setting it explicitly documents that
  we are relying on locks, not on serializable retries.
- **Tests run on PostgreSQL, never SQLite** — relates to INV-3 and
  INV-5. SQLite silently ignores `select_for_update` and has different
  unique-constraint and concurrency semantics. A green suite on SQLite
  would be evidence of nothing.

## Decisions

Codex implements these as given and does not relitigate them.

1. **Money representation is deferred to GOAL 1.** Do not add a `Money`
   type, a currency field, or a decimal setting in this goal. The
   representation is already decided (integer minor units of COP, never
   float) but it belongs to the domain layer, which this goal does not
   create.
2. **PostgreSQL 17** via the official image, owned by Docker Compose.
   Chosen for ACID transactions, row-level locking, and real constraint
   enforcement — the properties the financial core depends on. This is
   our justification, not a claim about HabiCapital's internal stack.
3. **Python 3.12, Django 5.2 LTS, DRF 3.15+, psycopg 3** (`psycopg[binary]`,
   not `psycopg2`). LTS for the framework; psycopg 3 is the supported
   driver for new Django projects.
4. **Config via environment variables**, read in `settings.py` with
   explicit defaults for local development only. `.env.example` is
   committed; `.env` is git-ignored. No secrets in the repository.
   `DJANGO_SECRET_KEY` has no production-safe default — if it is missing
   and `DEBUG` is false, startup fails loudly.
5. **`backend/src/` is a plain Python package, not a Django app.** The
   Django project lives in `backend/config/`. `src` holds our
   architecture. Django apps are registered later, in GOAL 1, only for
   the ORM models that need migrations
   (`src.infrastructure.persistence`). The health controller is a plain
   DRF `APIView` referenced from `config/urls.py` and needs no app.
6. **Frontend toolchain mirrors `daily-fitness-platform`**: Vite, React
   19, TypeScript, `react-router-dom`, `oxlint`, plain CSS with custom
   properties in a `theme/` directory. No Tailwind, no component
   library. Rationale: Samuel has to defend this code live in a pairing
   session, and reusing a toolchain he already operates is worth more
   than a marginally nicer one he does not.
7. **Two CI jobs, not one**: `backend` (with a PostgreSQL service
   container) and `frontend`. They are independent and should fail
   independently.
8. **Frontend styling in this goal is minimal but not ugly.** Define the
   colour tokens (purple / teal / neutral), the type scale, radius and
   spacing scale in `theme/tokens.css` now, because every later screen
   consumes them. Do not build components yet.

## Interfaces

**`GET /api/health/`**

```
200 OK
{
  "status": "ok",
  "database": "ok",
  "version": "<string>"
}
```

```
503 Service Unavailable
{
  "status": "degraded",
  "database": "unavailable",
  "version": "<string>"
}
```

The database check executes `SELECT 1` through Django's default
connection. A driver exception is caught and mapped to the 503 body — it
must not surface as an unhandled 500.

**`frontend/src/api/client.ts`**

```ts
export type HealthResponse = {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  version: string;
};

export function getHealth(): Promise<HealthResponse>;
```

Base URL comes from `import.meta.env.VITE_API_BASE_URL`, defaulting to
`http://localhost:8000`.

## Required tests

Backend, in `backend/tests/test_health.py`:

1. `test_health_returns_ok_when_database_reachable` — 200 and
   `status == "ok"`. Defends the acceptance criterion that the backend
   genuinely reaches PostgreSQL, rather than merely booting.
2. `test_health_reports_degraded_when_database_unavailable` — patch the
   connection so `SELECT 1` raises; assert 503 and
   `database == "unavailable"`. Defends the failure mode of a health
   probe that lies, or that leaks a 500.
3. `test_settings_do_not_wrap_requests_in_transactions` — assert
   `connections["default"].settings_dict["ATOMIC_REQUESTS"] is False`.
   This is a guard test for the INV-4 decision above: it fails loudly if
   someone later flips `ATOMIC_REQUESTS` on and quietly relocates the
   transaction boundary into the presentation layer.
4. `test_test_database_is_postgresql` — assert the engine in use is
   `django.db.backends.postgresql`. Guards the INV-3 / INV-5 decision
   that the suite must never silently fall back to SQLite.

Frontend: no unit tests in this goal. `tsc -b` must pass and the
production build must succeed; that is the frontend gate for GOAL 0.
A test runner is introduced in GOAL 6 when there are components worth
testing.

## Acceptance criteria

1. `docker compose up` brings up `db`, `backend` and `frontend` with no
   manual steps beyond copying `.env.example` to `.env`.
2. `curl http://localhost:8000/api/health/` returns 200 with
   `"database": "ok"`.
3. The frontend at `http://localhost:5173` renders a page that displays
   the live backend status fetched from the API — not a hardcoded value.
4. `pytest` from `backend/` runs the four tests above and they pass
   against PostgreSQL.
5. `npm run build` succeeds from `frontend/` with no TypeScript errors.
6. The CI workflow runs both jobs on push and on pull request, and both
   pass on a clean checkout.
7. `backend/src/` contains only `presentation/`. No empty `domain/`,
   `application/` or `infrastructure/` packages exist.
8. No secret value is committed. `.env` is git-ignored.

## Out of scope

Deliberately not touched in this goal:

- accounts, balances, ledger, transfers, shared expenses — any money
- the `Money` value object and the minor-units vs `Decimal` decision
- authentication, users, sessions, permissions
- repositories, facades, commands, domain events, strategies
- database models and migrations of any kind
- the design-pattern documentation file (starts in GOAL 1, when the
  first pattern is actually used)
- README challenge answers (GOAL 9)
- frontend pages, routing beyond a single route, and components
