# Architecture

## Phase 1 implementation

The monorepo has independently runnable frontend and backend applications. npm workspaces
manage the frontend; uv manages Python. Docker Compose provides development processes and one
PostgreSQL instance. The browser reaches FastAPI through a configured public API URL, and CORS
uses explicit origins. Phase 2 adds the database schema and maintenance commands. Phase 3 adds
isolated runtime database engines and health endpoints.

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

## Phase 2 implementation

SQLAlchemy metadata and an immutable Alembic revision define 12 ERP tables and three application
metadata tables. Separate administrator, migrator, application, and reader credentials keep
maintenance operations outside the running API. Explicit Compose task profiles run configuration,
role provisioning, migration, and sample-data loading.

All ERP relationships include tenant identity. Reader RLS resolves a tenant through a protected
database-login mapping using `session_user`. Changing a custom session setting cannot change the
tenant. The initial reader login belongs to one tenant; future multi-tenant query connections
must preserve this login-to-tenant boundary rather than reuse a single global reader login.

Deterministic seeds create two synthetic tenants, exact decimal monetary values, historical
orders, invoices, payments, and inventory snapshots. Seed markers and an advisory transaction
lock make loading atomic and repeatable. See [database design and operations](database.md).

Business routes, authentication, providers, charts, query history, saved queries, and Redis are
introduced in subsequent phases.

## Phase 3 implementation

FastAPI creates two independent SQLAlchemy engine pools during its lifespan: `DATABASE_URL` must
authenticate as `nlq_app`; `ANALYTICS_DATABASE_URL` must authenticate as `nlq_reader`. Neither
accepts migration or bootstrap identities. Application and analytics session dependencies are
provided for later repositories/services, but no business route can access data yet.

`GET /api/v1/health/live` checks only API process liveness. `GET /api/v1/health/ready` tests each
runtime identity and verifies that the analytics role defaults to a read-only transaction. It
returns only `ok`, `unconfigured`, or `unavailable` status for each path—never connection strings,
credentials, or database exceptions. Liveness remains available if runtime URLs are absent or
malformed so operational diagnosis does not depend on database availability.

## Phase 4 implementation

`POST /api/v1/nlq/query` accepts a natural-language question and runs one fixed pipeline:

1. `SchemaService` ranks the curated ERP catalog and sends only the relevant relations, columns,
   relationships, and business rules to the provider.
2. The `LLMProvider` interface isolates OpenAI from future adapters. The current OpenAI adapter
   uses the Responses API `text.format` JSON-schema mode with strict output validation.
3. `SQLValidator` parses PostgreSQL with SQLGlot and rejects non-SELECT statements, multiple
   statements, CTEs, comments, unsafe functions, `SELECT *`, unauthorized relations, and columns
   outside the selected context.
4. `QueryExecutor` runs the validated statement only through the `nlq_reader` session factory.
   It applies a transaction-local statement timeout, an outer row limit, and a measured response
   byte limit. The database role and RLS remain independent enforcement layers.

The route returns normalized JSON rows, a result-grounded summary, and visualization metadata.
It returns a non-sensitive `NLQ_UNAVAILABLE` error until both the restricted analytics connection
and an OpenAI key/model are configured. It accepts `conversationId` for forward compatibility;
conversation storage and reuse begin in Phase 7.

## Phase 5 implementation

The Next.js home page keeps the shell and static route on the server while `QueryWorkspace` is a
small client boundary for input state and the one-shot query mutation. Its dedicated API client
validates the public API URL and validates the shape of every successful response before rendering
it. The browser receives only `NEXT_PUBLIC_API_URL`; database URLs, reader credentials, and LLM
credentials remain exclusively in the API environment.

The workspace supports suggested questions, Enter-to-submit with Shift+Enter for a newline, clear
and disabled states, and non-sensitive API errors. A result includes a grounded summary, query
metadata, a responsive table with client-side sorting and pagination, and a read-only SQL view
with copy support. Fixed chart rendering and the result-grounded summary are extended in Phase 6;
history, saved queries, and conversations are deferred to Phase 7.

## Phase 6 implementation

The API already returns a bounded `visualization` object after checking that its axes match result
columns. The frontend maps only its `bar`, `line`, `area`, and `pie` values to fixed Recharts
components; it never accepts chart code, expressions, or configuration from the model. It converts
only finite numeric response values into chart series and shows an explanatory state when the
backend selects a table, lacks axes, or returns nonnumeric values.

The Phase 4 result-grounded summary remains the analytics summary. It is displayed alongside
the row count and execution duration, so the prose and visual result remain tied to the same
validated, read-only query response.

In Docker Compose, URL credentials remain in `apps/api/.env`, while container-only host/port
overrides route both runtime pools to the `postgres` service. The API never receives bootstrap or
migration credentials. The Compose health check uses liveness, leaving readiness meaningful for
deployments that require the database.

## Phase 7 implementation

The API now protects NLQ, history, saved-query, and settings routes with expiring HS256 bearer
tokens. It stores only Argon2 password hashes and has no public registration endpoint; an
administrator provisions users through the local CLI after migration. JWT validation requires the
configured issuer, audience, expiry, issue time, and subject before loading an active user.

Each NLQ request creates or continues a user-owned conversation. The service retrieves only the
most recent configured query/summary pairs for that conversation and sends that bounded context to
the provider. It stores the question, approved SQL, normalized result snapshot, summary, and safe
visualization metadata in the application schema only after successful execution. History and saved
query handlers always filter by the authenticated user, preventing cross-user access by guessed IDs.

The Next.js workspace keeps its access token in session storage, exposes sign-in/sign-out, and adds
working navigation for query history, saved queries, and settings. The browser supplies the bearer
token on every private request; it never sees database, LLM, or JWT signing secrets.

## User-managed data connections

Authenticated users can add a PostgreSQL or MongoDB connection from the Data connections workspace
screen. The browser sends the URL only to the API over its configured origin. The API validates the
URL, tests connectivity, inspects a PostgreSQL schema or MongoDB database, and encrypts the
normalized URL with its server-only Fernet key before storing it. Responses contain only connection
names, source type, schema or database name, active state, and timestamps.

At query time, the active connection is decrypted in memory, introspected into a bounded schema
context, and disposed after use. PostgreSQL uses the SQL parser and a read-only transaction.
MongoDB uses a stage/operator allow-list for aggregation pipelines and rejects write, JavaScript,
cross-collection, and output stages. Both paths retain timeout, row, and response-size enforcement.
Connection owners should always provide a dedicated least-privilege, read-only database account.

## Target request flow

```mermaid
flowchart TD
    UI[Next.js query interface] --> API[FastAPI routes and request validation]
    API --> Auth[Trusted user and authorization scope]
    Auth --> NLQ[NLQ orchestration]
    NLQ --> Context[Relevant schema and bounded conversation context]
    Context --> Provider[LLMProvider interface]
    Provider --> JSON[Pydantic structured-output validation]
    JSON --> Policy[SQL parser or MongoDB aggregation policy]
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

Use one PostgreSQL database initially with separate `app` and `erp` schemas. Phase 2 implements
explicit roles and grants; Phase 3 adds separate SQLAlchemy runtime engines. The existing Compose
`POSTGRES_USER` is a bootstrap administrator and must never become an API connection identity.

| Identity | Intended access |
| --- | --- |
| `nlq_app` | Application records only; controlled reads and writes |
| `nlq_reader` | SELECT on approved ERP relations; no application records |
| `nlq_migrator` | Controlled migrations; unavailable to API runtime |

`DATABASE_URL` and `ANALYTICS_DATABASE_URL` remain distinct settings. The migration
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

PostgreSQL, API, and frontend readiness are checked independently. The API liveness probe checks
`/api/v1/health/live`; it proves the process is available without making deployment health depend
on database configuration. `/api/v1/health/ready` separately tests both restricted database
identities. Compose waits for PostgreSQL before starting the API, then for API liveness before the
frontend.

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
