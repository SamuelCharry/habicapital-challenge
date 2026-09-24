# habicapital-challenge

Financial system — backend and frontend.

## Structure

```
backend/     application, domain, infrastructure, presentation
frontend/    client
.agents/     agent skills and reference material
AGENTS.md    agent workflow contract
PLAN.md      per-task architecture plan (generated per task)
```

## Working with agents

Architecture and implementation are split across two agents. Claude
writes `PLAN.md`; Codex implements it following
`.agents/skills/safe-financial-implementation/SKILL.md`.

Read `AGENTS.md` for the full contract.

## Design rules that outlive any single task

- Layered architecture; dependencies point inward toward the domain.
- Money as integer minor units or `Decimal` — never `float`.
- Ledger is append-only; balances are derived, corrections are
  compensating entries.
- The application layer owns the transaction boundary.
- Every money-touching change defends the invariants in
  `.agents/skills/safe-financial-implementation/references/invariants.md`.

## Setup

Install Docker with Docker Compose. Copy `.env.example` to `.env` at the
repository root, then start the stack:

```sh
cp .env.example .env
docker compose up --build
```

In PowerShell, use `Copy-Item .env.example .env` for the copy step.
Compose starts PostgreSQL 17, waits for database readiness, and starts the
backend and frontend. No migration step is needed for this foundation.

- Frontend: http://localhost:5173 — displays live backend and database status.
- Backend health: http://localhost:8000/api/health/

```sh
curl http://localhost:8000/api/health/
```

A reachable database returns HTTP 200 with
`{"status":"ok","database":"ok","version":"0.1.0"}`. A database failure
returns HTTP 503 with `status: "degraded"` and `database: "unavailable"`.

The example credentials and debug defaults are for local development only.
Set `DJANGO_DEBUG=false` and supply `DJANGO_SECRET_KEY` outside development;
startup fails without a key when debug is disabled. `.env` is ignored by Git.
Compose reads it automatically; native processes read environment variables
from the shell. `POSTGRES_HOST` defaults to `localhost` for native commands
and is overridden to `db` inside Compose.

### Verification with Docker

```sh
docker compose exec backend pytest
docker compose exec frontend npm run build
```

The four backend tests use real PostgreSQL, including a simulated database
failure and guards for the database engine and transaction configuration.
The frontend gate runs TypeScript checks and a production build; no frontend
unit-test runner is installed yet. CI runs these gates in two independent
jobs on pushes and pull requests, with PostgreSQL 17 for the backend.

### Native development

Use Python 3.12 and Node.js 22. Start PostgreSQL through Compose:

```sh
docker compose up -d db
python -m venv .venv
```

Activate the virtual environment (`.venv\Scripts\Activate.ps1` in PowerShell,
or `source .venv/bin/activate` on Linux/macOS), then:

```sh
cd backend
python -m pip install -r requirements-dev.txt
pytest
python manage.py runserver
```

The local defaults match `.env.example`. If you change the database values
in `.env`, export those same values into the shell running the backend.
The PostgreSQL role must be allowed to create the test database.

In a separate terminal:

```sh
cd frontend
npm install --package-lock=false
npm run dev
```

Optionally copy `frontend/.env.example` to `frontend/.env` to change
`VITE_API_BASE_URL`; it defaults to `http://localhost:8000`. The backend
allows the local frontend origins through `CORS_ALLOWED_ORIGINS`.
Run `npm run build` for the production build or `npm run lint` for linting.
On Windows where PowerShell blocks npm scripts, use `npm.cmd`.

Stop the stack with `docker compose down`. Database data persists in the
Compose volume across restarts.
