# Architecture

## Phase 1 implementation

The monorepo has independently runnable frontend and backend applications. npm workspaces
manage the frontend; uv manages Python. Docker Compose provides development processes and one
PostgreSQL instance. The browser reaches FastAPI through a configured public API URL, and CORS
uses explicit origins. PostgreSQL is provisioned but unused by the application at this milestone.

```mermaid
flowchart LR
    Browser[Browser] --> Web[Next.js shell :3000]
    Browser -. future API requests .-> API[FastAPI bootstrap :8000]
    API -. database access in Phase 3 .-> PG[(PostgreSQL :5432)]
```

Phase 1 includes:

- Next.js 16, React 19, strict TypeScript, Tailwind 4, shadcn/ui configuration, and Lucide icons.
- A responsive application shell without business data or query execution.
- FastAPI application construction, Pydantic Settings validation, and development OpenAPI docs.
- Independent lint, typecheck, build, and backend bootstrap/configuration checks.
- Explicit dependency locks, environment templates, and local secret generation.
- Development Dockerfiles, reload mounts, startup checks, and a persistent PostgreSQL volume.

Database schemas, credentials for application roles, Alembic, SQLAlchemy integration, business
routes, authentication, providers, charts, query history, saved queries, and Redis are intentionally
introduced in their corresponding phases. Empty service implementations are not scaffolding.

## Target request flow

```mermaid
flowchart TD
    UI[Next.js query interface] --> API[FastAPI routes and request validation]
    API --> Auth[Trusted user and authorization scope]
    Auth --> NLQ[NLQ orchestration]
    NLQ --> Context[Relevant schema and bounded conversation context]
    Context --> Provider[LLMProvider interface]
    Provider --> JSON[Pydantic structured-output validation]
    JSON --> Policy[PostgreSQL parser and SQL security policy]
    Auth --> Policy
    Policy --> Execute[Read-only query execution with limits]
    Execute --> ERP[(ERP data)]
    ERP --> Results[Normalization, grounded summary, chart metadata]
    Results --> UI
    NLQ --> App[(Application records)]
    App --> Context
```

FastAPI remains a modular monolith. Routes handle HTTP concerns; services orchestrate business
behavior; repositories and dedicated execution services access persistence. Provider adapters
implement one typed interface. The model proposes SQL and chart metadata but has no execution
capability or authority to choose a user's permissions.

## Persistence boundary

Use one PostgreSQL database initially with separate `app` and `erp` schemas. Phase 2 creates
explicit roles and grants; Phase 3 adds separate SQLAlchemy engines. The existing Compose
`POSTGRES_USER` is a bootstrap administrator and must never become an API connection identity.

| Identity | Intended access |
| --- | --- |
| `nlq_app` | Application records only; controlled reads and writes |
| `nlq_reader` | SELECT on approved ERP relations; no application records |
| `nlq_migrator` | Controlled migrations; unavailable to API runtime |

`DATABASE_URL` and `ANALYTICS_DATABASE_URL` remain distinct settings. A future migration
environment holds `MIGRATION_DATABASE_URL` separately. The API's environment does not contain
bootstrap or migration credentials. Schema ownership, tenant scope, grants, and indexes are
designed with Phase 2 rather than retrofitted after query execution exists.

## NLQ safety boundary

Phase 4 must enforce authorization and SQL policy before execution, even though interactive
authentication is scheduled for Phase 7. Pre-auth operation is local development only.

SQL validation will parse PostgreSQL syntax and inspect all statements and nested expressions.
It must reject modifying CTEs, SELECT INTO, unauthorized relations, unsafe functions, and any
unsupported construct. Read-only privileges and transactions supplement this policy; neither
SELECT syntax nor a read-only transaction is a complete SQL sandbox.

Query timeout, returned-row count, response size, and pagination are independent controls.
Schema and result caches must include authorization scope. Conversation context must be bounded.
Tenant isolation and history/saved-query ownership are enforced by the backend, never by a prompt.

## Development container design

PostgreSQL, API, and frontend readiness are checked independently. The API's Phase 1 probe checks
`/openapi.json`; this is a process readiness check, not database readiness. Compose waits for
PostgreSQL before starting the API, then for API startup before the frontend.

The PostgreSQL 18 image stores data beneath `/var/lib/postgresql/18/docker`, so its persistent
volume is mounted at `/var/lib/postgresql`. API dependencies live in `/opt/venv`; host source
mounts cannot hide them. Frontend host dependencies and `.next` output are masked with named
volumes to keep Windows artifacts out of the Linux runtime.

The API and web containers receive only their respective environment files. Docker build
contexts exclude environment files, local tools, editor worktrees, and generated dependencies.
All published ports bind to loopback. Images use explicit versions; base runtime and PostgreSQL
images also pin registry digests. These are development containers, with production images,
deployment secrets, monitoring, and operational controls scheduled for Phase 8.

## References

- [Next.js 16 requirements and separate linting](https://nextjs.org/docs/app/guides/upgrading/version-16)
- [shadcn/ui installation for Next.js](https://ui.shadcn.com/docs/installation/next)
- [Next.js public environment variables](https://nextjs.org/docs/app/guides/environment-variables)
- [Compose readiness and startup ordering](https://docs.docker.com/compose/how-tos/startup-order/)
- [PostgreSQL image configuration and version 18 data directory](https://hub.docker.com/_/postgres)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
