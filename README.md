# NLQ

A natural-language analytics workspace built with Next.js, FastAPI, and PostgreSQL.

**Current milestone: Phase 7 — authenticated workspace.** Users sign in to run queries, continue
bounded conversations, revisit persisted results, save common questions, and retain preferences.

## Run with Docker

Install Docker Desktop with the Linux container engine and Docker Compose support. All commands
below run from the repository root. Local Node and Python installations are not required for this workflow.

In PowerShell:

```powershell
.\scripts\setup.ps1
docker compose --profile database run --build --rm db-configure
docker compose --profile database run --build --rm db-bootstrap
docker compose --profile database run --build --rm migrate
docker compose --profile database run --build --rm seed
docker compose up --build -d --wait
```

The setup script creates `.env`, `apps/web/.env.local`, and `apps/api/.env` from their templates,
generates a cryptographically random local PostgreSQL password, and preserves existing files.
It never prints the password. `db-configure` adds separate application, reader, and migration
credentials only where settings are missing. `db-bootstrap` provisions roles/schemas, `migrate`
applies versioned DDL, and `seed` loads synthetic development data. Database tasks are explicit
one-off commands; starting the API does not run migrations or seeds.

If local PowerShell script execution is restricted, run the setup script for this
process with `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1`.

On other operating systems, copy the three templates to those same destinations and set a random
`POSTGRES_PASSWORD` in the root `.env` before starting Compose. Do not leave the password empty.

| Service | Address |
| --- | --- |
| Frontend | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |
| OpenAPI document | http://localhost:8000/openapi.json |
| API liveness | http://localhost:8000/api/v1/health/live |
| API readiness | http://localhost:8000/api/v1/health/ready |
| PostgreSQL | `127.0.0.1:5432` |

All published ports bind to the local machine. The root PostgreSQL credentials are used for
database provisioning only; they are not injected into the API or frontend. The API creates
separate database engine pools when both restricted URLs are configured. Its Compose health
probe uses the liveness endpoint; readiness checks the database identities without exposing
connection details.

```powershell
docker compose ps
docker compose logs -f web api
docker compose down
```

`down` preserves the PostgreSQL volume. Database credentials are initialized only on a new data
volume; changing `.env` does not rotate an existing database password.

Source changes reload in development. Changes to dependencies, Dockerfiles, or backend project
configuration require `docker compose up --build -d --wait`. The Python virtual environment lives
outside source mounts. Frontend dependency/cache volumes are separate from host dependencies.

## Run applications on the host

Use Node.js **24.21.0**, npm **11.19.0**, Python **3.12**, and uv **0.12.23**.
Version managers may supply these without changing your system defaults. Python patch updates
within 3.12 are supported; the container uses 3.12.15.

Initialize configuration with `scripts/setup.ps1` first. Host application development does not
require PostgreSQL until database integration is added. To provision the Phase 2 database,
start PostgreSQL through Compose or provide a local PostgreSQL 18 installation:

```powershell
docker compose up -d postgres
```

Frontend, from the repository root:

```powershell
npm ci
npm run dev:web
```

Backend, in a second terminal:

```powershell
Set-Location apps/api
uv sync --frozen
uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Database setup from `apps/api`, with PostgreSQL already running and the root `.env` matching
its administrator login:

```powershell
uv run --frozen python -m app.db.configure
uv run --frozen python -m app.db.bootstrap
uv run --frozen alembic upgrade head
uv run --frozen python -m seeds
uv run --frozen alembic check
```

Phase 7 adds a workspace user table but deliberately has no public registration route. Set a
random `JWT_SECRET` of at least 32 characters in `apps/api/.env`, then create the first user after
migration and seeding:

```powershell
uv run --frozen python -m app.auth.create_user --email analyst@example.com --tenant deccan-demo
```

The command prompts for a password (minimum 12 characters), so it does not place the password in
shell history. Sign in at http://localhost:3000/login. Access tokens are kept in browser session
storage and expire after `JWT_ACCESS_TOKEN_MINUTES` (60 by default).

The sample dataset is fixed as of **2026-09-30**. The main tenant has 600 sales orders,
300 purchase orders, 80 products, 60 customers, and 20 suppliers. A smaller second tenant
supports isolation tests. Repeating the seed command skips completed versions without replacing
records. See [database setup, schema, and data semantics](docs/database.md).

Run one workflow at a time on the default ports. To change published Docker ports, edit the root
`.env`; update `NEXT_PUBLIC_API_URL` in `apps/web/.env.local` and `CORS_ORIGINS` in `apps/api/.env`
to match the browser addresses. Docker containers use `postgres` as the future database hostname;
host processes use `localhost`.

## Validate

From the repository root:

```powershell
npm run lint
npm run typecheck
npm run build
```

From `apps/api`:

```powershell
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

PostgreSQL integration tests skip unless explicit `TEST_DATABASE_URL`,
`TEST_READER_DATABASE_URL`, and `TEST_APP_DATABASE_URL` values point to the same migrated,
seeded database named `nlq_test*`. These must use their respective restricted identities;
runtime and migration configuration are never reused implicitly. Additional provisioning
tests use optional `TEST_ADMIN_DATABASE_URL`. See the database guide for the test workflow.

With the Docker stack running, the equivalent checks are:

```powershell
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec api uv run --frozen ruff check .
docker compose exec api uv run --frozen ruff format --check .
docker compose exec api uv run --frozen pytest
```

Run frontend production builds on the host or in a separate container so they do not share the
development server's `.next` directory. Dependency installs use committed `package-lock.json`
and `apps/api/uv.lock`; update those locks deliberately when upgrading dependencies.

The initial production npm audit reports zero vulnerabilities. The full audit reports a
development-tooling advisory in `braces`, reached through the ESLint configuration's glob
dependencies. Upstream has no patched release as of 2026-10-05; track
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) when updating the lockfile.
ESLint 9 is retained for the current Next.js lint plugins' declared peer compatibility.

## Configuration

| File | Responsibility |
| --- | --- |
| `.env` | Compose ports and PostgreSQL provisioning credentials |
| `apps/web/.env.local` | Public browser API URL |
| `apps/api/.env` | Backend settings and future provider/runtime credentials |
| `apps/api/migrations/.env` | Migration/seed identity only; excluded from the API environment |

Only `.env.example` templates are committed. `NEXT_PUBLIC_*` values are public and baked into
frontend builds. Backend environment loading is anchored to `apps/api`, independent of the
working directory. Optional future credentials remain unset until their feature is implemented.

The default query limits are 10 seconds, 1,000 returned rows, 100 rows per page, and 5 MiB per
response. `POST /api/v1/nlq/query` requires a bearer token, a reader URL, and `LLM_API_KEY` plus
`LLM_MODEL`. The Phase 4 OpenAI adapter uses the Responses API with strict structured output; set
`LLM_PROVIDER=openai`. It never executes unparsed model text. Follow-up questions supply at most
`CONVERSATION_MAX_TURNS` prior question/summary pairs to the model.

The Dockerfiles and Compose file are for local development. Production deployment hardening
belongs to Phase 8. No production-readiness or tenant-isolation guarantees are implied by the
application foundation.

## Layout and next milestones

```text
apps/web/          Next.js application and UI primitives
apps/api/          FastAPI application, SQLAlchemy models, database commands, and tests
apps/api/migrations/  Versioned Alembic schema changes
apps/api/seeds/     Deterministic synthetic ERP dataset
scripts/          Local environment setup
docs/             Architecture and phase boundaries
compose.yaml      Development services and persistent PostgreSQL volume
```

See [architecture and implementation boundaries](docs/architecture.md).

Phase 8 covers production deployment hardening. Each later phase requires its own agreed scope.
