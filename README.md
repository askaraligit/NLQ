# NLQ

A natural-language analytics workspace built with Next.js, FastAPI, and PostgreSQL.

**Current milestone: Phase 1 — project foundation.** The frontend shell, backend bootstrap,
validated environment settings, dependency locks, and local Docker configuration are implemented.
ERP tables, database access, SQL generation, authentication, and analytics are later milestones.

## Run with Docker

Install Docker Desktop with the Linux container engine and Docker Compose support. All commands
below run from the repository root. Local Node and Python installations are not required for this workflow.

In PowerShell:

```powershell
.\scripts\setup.ps1
docker compose config --quiet
docker compose up --build -d --wait
```

The setup script creates `.env`, `apps/web/.env.local`, and `apps/api/.env` from their templates,
generates a cryptographically random local PostgreSQL password, and preserves existing files.
It never prints the password. If local PowerShell script execution is restricted, run it for this
process with `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1`.

On other operating systems, copy the three templates to those same destinations and set a random
`POSTGRES_PASSWORD` in the root `.env` before starting Compose. Do not leave the password empty.

| Service | Address |
| --- | --- |
| Frontend | http://localhost:3000 |
| API documentation | http://localhost:8000/docs |
| OpenAPI document | http://localhost:8000/openapi.json |
| PostgreSQL | `127.0.0.1:5432` |

All published ports bind to the local machine. The root PostgreSQL credentials are used for
database provisioning only; they are not injected into the API or frontend. The API does not
connect to the database during Phase 1. Its Compose readiness probe uses the OpenAPI document;
the application health endpoint will arrive in Phase 3.

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
require PostgreSQL until database integration is added. To run PostgreSQL alone when needed:

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

Only `.env.example` templates are committed. `NEXT_PUBLIC_*` values are public and baked into
frontend builds. Backend environment loading is anchored to `apps/api`, independent of the
working directory. Optional future credentials remain unset until their feature is implemented.

The default future query limits are 10 seconds, 1,000 returned rows, 100 rows per page, and
5 MiB per response. They are validated configuration today, not an implemented query executor.

The Dockerfiles and Compose file are for local development. Production deployment hardening
belongs to Phase 8. No production-readiness or tenant-isolation guarantees are implied by the
Phase 1 scaffold.

## Layout and next milestones

```text
apps/web/          Next.js application and UI primitives
apps/api/          FastAPI application, settings, and bootstrap tests
scripts/          Local environment setup
docs/             Architecture and phase boundaries
compose.yaml      Development services and persistent PostgreSQL volume
```

See [architecture and implementation boundaries](docs/architecture.md).

Phase 2 adds the ERP schema, separate database roles, Alembic migrations, indexes, and realistic
seed data. Phase 3 adds database integration and health endpoints. Phase 4 introduces the
provider abstraction and secured NLQ pipeline. Each later phase requires its own agreed scope.
