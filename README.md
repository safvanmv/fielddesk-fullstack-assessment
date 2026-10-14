# FieldDesk Full-Stack Engineering Assessment

This practical assessment is conducted by **Gatlier** to evaluate full-stack engineering ability, with particular emphasis on backend correctness, security, database design, testing and production awareness.

FieldDesk is a fictional field-service application created solely for this assessment. Candidates are expected to build a working application, explain their technical decisions and take ownership of everything they submit.

## Start here

1. Read the complete [assessment brief](docs/ASSESSMENT.md).
2. Review the [evaluation criteria](docs/EVALUATION.md).
3. Follow the [submission instructions](docs/SUBMISSION.md).
4. Complete the [technical notes](candidate-submission/TECHNICAL_NOTES.md) and [AI usage disclosure](candidate-submission/AI_USAGE.md).
5. Raise questions or blockers through a GitHub Issue in this repository.

## Required stack

- React with TypeScript
- Python with Django REST Framework (approved alternative to Node.js with TypeScript; see [technical notes](candidate-submission/TECHNICAL_NOTES.md))
- PostgreSQL
- Redis with Celery for background jobs
- Docker Compose

The Django REST Framework backend and PostgreSQL combination was approved by Gatlier. All other assessment requirements remain unchanged. Libraries and architectural patterns are the candidate's choice. Significant decisions and trade-offs should be documented.

## Project structure

This repository is organized as a small monorepo. Each application has its own dependencies and tests, while Docker Compose provides one local entry point for the services.

```text
.
|-- frontend/                 React + TypeScript (Vite)
|   |-- src/
|   |   |-- app/              Application shell and page-level composition
|   |   |-- components/       Shared UI components
|   |   |-- features/         User-facing feature modules
|   |   |-- lib/              API client and shared utilities
|   |   `-- test/             Frontend test setup
|   |-- Dockerfile
|   `-- package.json
|-- backend/                  Django REST Framework API and Celery task code
|   |-- apps/
|   |   |-- common/           Cross-cutting API plumbing: error envelope, request IDs, JSON logs, health
|   |   |-- accounts/         Organizations, memberships/roles, login, users, organization settings
|   |   |-- work_orders/      Work orders, scheduling, progress events, attachments, CSV export
|   |   |-- notifications/    Assignment notification task (Celery worker) and mock provider
|   |   `-- activity/         Audit log, real-time events and the SSE stream
|   |-- config/               Django settings (base/local/test), URLs, ASGI/WSGI and Celery app
|   |-- Dockerfile
|   |-- README.md             API contract, data-integrity and operations notes
|   |-- manage.py
|   `-- requirements.txt
|-- docker-compose.yml        Frontend, API, worker, PostgreSQL and Redis
|-- .env.example              Local-only configuration template
|-- frontend/package-lock.json
|-- candidate-submission/
`-- docs/
```

The backend is split into one Django app per domain. Each app keeps its own models, migrations, serializers, views, URLs and tests. Transactional business logic lives in service modules rather than views, so each transaction boundary is a single named function (for example `apps/work_orders/services/progress_events.py`). Tenant and role scoping for work orders is centralised in `apps/work_orders/selectors.py`. Dependencies point one way: `common` <- `accounts` <- `work_orders` <- `notifications`, and every app records audit entries through `activity.services.record_change`.

Where the brief's suggested layout differs from Django conventions, the equivalents are:

| Brief | This repository |
| --- | --- |
| `worker/` | `backend/config/celery.py` (worker entry point) and `backend/apps/notifications/tasks.py`; the API and worker are separate processes built from the same backend image |
| `database/migrations/` | `backend/apps/*/migrations/` |
| `tests/` | `backend/apps/*/tests/` and `frontend/src/**/*.test.tsx` |

## Local development

Requirements: Docker Desktop with Docker Compose.

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell, or `cp .env.example .env` in a POSIX shell). The values in the example are for local development only.
2. Start the services from the repository root:

   ```sh
   docker compose up --build -d
   ```

3. Seed the two sample organisations and role accounts:

   ```sh
   docker compose exec api python manage.py seed_assessment
   ```

   The default local password is `FieldDesk!2026` for the seeded users; override it with `SEED_PASSWORD` in `.env`. Never use these credentials outside local assessment development.
4. Open the frontend at `http://localhost:5173`. The API health and readiness endpoints are `http://localhost:8000/api/health/` and `/api/ready/`.
5. Stop the services with `docker compose down`. To also remove the local PostgreSQL data volume, use `docker compose down --volumes`.

Compose keeps PostgreSQL and Redis on the internal network rather than publishing their ports on the host, avoiding collisions with locally installed services. Migrations run when the API container starts.

See [backend/README.md](backend/README.md) for the API endpoints, sample accounts, security behavior, scheduling constraint, event idempotency, background-job semantics, and known limitations.

## Development checks

Run frontend checks from the repository root:

```sh
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Run the backend tests against the Compose PostgreSQL service:

```sh
docker compose exec api python manage.py test apps
```

Check for unapplied model changes:

```sh
docker compose exec api python manage.py makemigrations --check --dry-run
```

## What to submit

- A working frontend, API and background worker
- Database migrations and seed data
- Automated tests
- Docker-based local setup
- Clear technical documentation
- Completed submission templates
- A pull request from the candidate's fork
- A 10–15 minute screen recording
- The final commit SHA

AI-assisted development tools are permitted. Every use must be disclosed clearly, including the tools used, the files or sections affected, the purpose of the assistance and how the output was verified. The candidate remains responsible for the correctness, security and maintainability of all submitted work.

There is no prescribed visual design. A clear, usable interface is sufficient; engineering quality is the main consideration.

## Communication

Use GitHub Issues for all assessment questions, assumptions and technical blockers. This keeps clarifications visible and ensures every candidate receives consistent information.

Please do not include confidential information, credentials or code from a current or previous employer.

---

**Conducted by Gatlier**
