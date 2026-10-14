# FieldDesk backend

Django 5.2 / Django REST Framework API. The API uses Django session authentication and PostgreSQL. Redis is used for shared throttling and Celery delivery; local uploads use Django's filesystem storage.

## Local operation

The repository-root Compose file supplies PostgreSQL and Redis. From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d db redis
docker compose run --rm api python manage.py migrate
docker compose run --rm api python manage.py seed_assessment
docker compose up --build api worker
```

Run the frontend separately or with Compose. The API is at `http://localhost:8000/api/`. `DJANGO_SECRET_KEY`, database credentials, `REDIS_URL`, allowed hosts and CORS origins are environment-configured. Do not use the example local credentials in a deployed environment. The `seed_assessment` command is intended only for assessment/development; it reads `SEED_PASSWORD` or uses the documented local sample password.

Seeded users:

| Organization | Role | Username |
| --- | --- | --- |
| Northstar Maintenance | Owner | `northstar_owner` |
| Northstar Maintenance | Dispatcher | `northstar_dispatcher` |
| Northstar Maintenance | Technician | `northstar_technician` |
| Harbor Services | Owner | `harbor_owner` |
| Harbor Services | Dispatcher | `harbor_dispatcher` |
| Harbor Services | Technician | `harbor_technician` |

Local seed password: `FieldDesk!2026` (or `SEED_PASSWORD`). Users have separate Django password hashes.

Apply migrations with `python manage.py migrate`. Run the backend suite with:

```powershell
python manage.py test apps
```

The test database must be PostgreSQL: tests cover PostgreSQL exclusion constraints and a simultaneous two-request scheduling race. Set the same `POSTGRES_*` variables as the API. Redis is not needed by the test suite. Useful checks are `python manage.py check` and `python manage.py makemigrations --check`.

## Authentication and API contract

All routes below are under `/api/`. Authentication is a Django session cookie; mutating requests require CSRF protection. Bootstrap with `GET /api/auth/csrf/`, which returns `204 No Content` and sets the readable `csrftoken` cookie. Send its value in `X-CSRFToken` on `POST`, `PUT`, `PATCH`, and `DELETE` requests. The current frontend's Vite config proxies `/api` to `http://api:8000` and does not rewrite the path. In that deployment the browser calls its own origin (`/api/...`), so this is a same-origin request: use `credentials: "include"` (as with the browser fetch client), and the browser will send/accept session and CSRF cookies without a cross-origin CORS grant. The proxy must preserve `Set-Cookie`, `Cookie`, and `X-CSRFToken`; the supplied Vite proxy forwards the path. If serving the API directly from a different browser origin, the origin must be explicitly listed in `CORS_ALLOWED_ORIGINS`; CORS credentials are enabled, and wildcard origins are not used. `CSRF_TRUSTED_ORIGINS` follows that configured list. Cross-site cookie deployment additionally requires `SESSION_COOKIE_SAMESITE=None`, `CSRF_COOKIE_SAMESITE=None` and secure cookies over HTTPS; same-origin Vite proxy uses the defaults (`Lax`). `EventSource` clients must set `withCredentials: true` when cross-origin. Enable `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and `SECURE_SSL_REDIRECT` behind HTTPS in deployment.

| Method/path | Description / access |
| --- | --- |
| `GET /auth/csrf/` | Obtain CSRF token (public). |
| `POST /auth/login/` | Session login with `{"username":"…","password":"…"}`. |
| `POST /logout/` | End session. |
| `GET /me/` | Current user, organization and role. |
| `GET /health/` | Liveness; does not require database. |
| `GET /ready/` | Database readiness. |
| `GET /dashboard/` | Work-order counts, limited to the caller's permitted records. |
| `GET /technicians/` | Same-organization technician choices (`id`, `username`, `email`). |
| `GET /organization/settings/` | Current organization name and storage quota/usage. |
| `PATCH /organization/settings/` | Owner updates organization `name` and/or `storage_limit_bytes`. |
| `GET /work-orders/` | List/search/filter/sort/page. |
| `POST /work-orders/` | Create (owner/dispatcher). |
| `GET /work-orders/{uuid}/` | Retrieve only within authorized scope. |
| `PATCH /work-orders/{uuid}/` | Update (owner/dispatcher). |
| `GET /reports/work-orders.csv` | Export list filters as streamed CSV. |
| `POST /work-orders/{uuid}/attachments/` | Multipart `file` upload (owner/dispatcher). |
| `GET /attachments/{id}/download/` | Authorized attachment download. |
| `POST /progress-events/` | Technician progress event; see below. |
| `GET /audit/` | Recent audit events for visible work orders; optional `work_order={uuid}` and `limit`. |
| `GET /events/stream/` | Authenticated, organization-scoped SSE stream. |
| `GET /users/`, `GET /users/{membership-id}/` | Organization users; every `/users/` action is owner-only. (`/members/` is a compatibility alias.) |
| `POST /users/` | Owner creates a user with `username`, `email`, `password`, `role`, optional `active`. |
| `PATCH /users/{membership-id}/` | Owner changes another member's `role` and/or `active`. (`/members/` alias also supported.) |

Work-order list parameters: `search` (reference/title/description/site), `status`, `priority`, `technician`, `ordering` (one of `created_at`, `-created_at`, `scheduled_start`, `-scheduled_start`, `priority`, `-priority`, `title`, `-title`), `page`, and `page_size` (maximum 100). List response: `{"count":N,"page":1,"page_size":25,"results":[...]}`. Supported roles: owners and dispatchers can see and change all work orders in their organization; technicians can see only orders assigned to them and cannot use dispatcher/owner mutations. A technician can post progress only for an order currently assigned to them. Organization and role are never accepted as work-order authority from a client.

API errors use `{"error":{"code":"…","message":"Request failed.","details":…,"request_id":"…"}}`; validation details are preserved in `details`. Each response includes `X-Request-ID`. Login deliberately gives the same failure response for unknown users and incorrect passwords.

### Frontend response contract

The following shapes are the frontend-facing contract (all JSON responses are UTF-8). IDs are integer IDs unless marked `uuid`; all timestamps are ISO-8601 UTC strings. Fields not listed are not implied. API changes that alter these shapes should be coordinated with the frontend.

**Session bootstrap**

1. `GET /api/auth/csrf/` returns an empty `204` response and sets the `csrftoken` cookie (it does not return a token in JSON).
2. Send `POST /api/auth/login/` JSON `{"username":"northstar_dispatcher","password":"…"}` with `X-CSRFToken` equal to the cookie value and cookie credentials. Success `200`:

```json
{"user":{"id":"2","username":"northstar_dispatcher","email":"northstar_dispatcher@example.test","first_name":"","last_name":"","role":"dispatcher","organization_name":"Northstar Maintenance"}}
```

3. Use the session cookie and include `X-CSRFToken` for state-changing calls. `GET /api/me/` returns:

```json
{"id":"2","username":"northstar_dispatcher","email":"northstar_dispatcher@example.test",
 "first_name":"","last_name":"","role":"dispatcher","organization_name":"Northstar Maintenance"}
```

`POST /api/logout/` returns `204` with an empty body. Invalid login returns `400`; missing authentication returns `403` (session-authenticated DRF convention).

**Work orders**

`POST /api/work-orders/` accepts fields below other than server-owned `id`, `reference`, `created_by`, attachment metadata, and timestamps. `PATCH` accepts any subset; `assigned_technician` is a same-organization technician's integer user ID or `null`. Scheduled bounds must both be omitted/null or both valid ISO timestamps. Status: `open`, `scheduled`, `in_progress`, `completed`, `cancelled`; priority: `low`, `normal`, `high`, `urgent`.

```json
{
  "id": "a UUID",
  "reference": "FD-7K3M9QX2",
  "title": "Repair pump",
  "description": "",
  "priority": "normal",
  "status": "open",
  "assigned_technician": 3,
  "scheduled_start": null,
  "scheduled_end": null,
  "site_name": "Plant 1",
  "created_by": 2,
  "attachments": [{"id": "1", "name": "report.pdf", "size": 1234, "content_type": "application/pdf"}],
  "created_at": "2026-10-08T01:30:00Z",
  "updated_at": "2026-10-08T01:30:00Z"
}
```

Create returns `201` with one work-order object; retrieve/update returns `200` with one object. List returns `200`:

```json
{"count": 1, "page": 1, "page_size": 25, "results": [/* work-order objects */]}
```

`GET /api/dashboard/` returns `{"total":1,"by_status":{"open":1}}`; zero-count statuses are omitted. `GET /api/technicians/` returns `[{"id":3,"username":"northstar_technician","email":"…"}]`, excluding inactive users. `GET /api/organization/settings/` returns `{"id":1,"name":"Northstar Maintenance","storage_limit_bytes":1073741824,"storage_used_bytes":1234}`; the endpoint is readable to organization members, but `PATCH` is owner-only and accepts only `name` (1–120 characters) and/or nonnegative integer `storage_limit_bytes`. It rejects a limit lower than current attachment usage. Validation returns `400`; invalid technician ID or malformed scheduling bounds are client errors; schedule overlap is `409` with a user-displayable `detail`.

**Events, files, members and activity**

`POST /api/progress-events/` success is `201 {"eventId":"evt-10001","duplicate":false}`; a previously accepted event ID is `200 {"eventId":"evt-10001","duplicate":true}`. Unassigned/cross-organization work orders are `404`.

Attachment upload is `multipart/form-data` with a `file` part. Success `201`:
`{"id":1,"original_name":"report.pdf","content_type":"application/pdf","size":1234,"created_at":"…"}`.
Download returns file bytes, not JSON. Missing/cross-tenant files return `404`.

`GET /api/users/` (owner-only; `/api/members/` alias) returns an array such as `[{"id":1,"username":"northstar_owner","email":"…","role":"owner","active":true}]`. `POST /api/users/` accepts username (Django username characters, at most 150), optional email, password (at least 12 characters and passing Django's password validators, including similarity to the username/email), role and optional boolean `active` (defaults true), and returns one user object with `201`. Validation errors are reported per field in `error.details`, for example `{"password": ["This password is entirely numeric."]}`. `PATCH /api/users/{membership-id}/` accepts `{"role":"dispatcher"}`, `{"active":false}`, or both; it returns the member object with `200`. Any other field, or an empty body, is rejected with `400`. Owners may assign any supported role to another user but cannot change their own account through this endpoint. Assigned users must have active work orders reassigned/closed before deactivation (`409`). Member changes are serialized on the organization row lock, and under that lock the acting owner is re-checked, so an owner demoted by a concurrent request cannot complete a change (`403`). Because the actor must be an active owner and cannot change themselves, an organization always retains an active owner. There is no `DELETE`: users are deactivated, never deleted (see below). Passwords are never included. Create/role/active changes are audited. `GET /api/audit/?work_order={uuid}` returns a list of records shaped as `{"id":1,"action":"work_order.created","target_type":"WorkOrder","target_id":"…","actor":"northstar_dispatcher","changes":{},"created_at":"…"}`. Owner audit access also includes membership and organization-settings changes.

`GET /api/reports/work-orders.csv` returns `text/csv` attachment data. `GET /api/events/stream/` returns `text/event-stream`, with standard `id`, `event`, and JSON `data` lines; reconnect with `Last-Event-ID`. It accepts a browser `EventSource`'s `Accept: text/event-stream` (the view adds an event-stream renderer to DRF content negotiation; without it DRF answers `406`). Events are named after the audit action (`work_order.created`, `work_order.updated`, `work_order.status_changed`, `work_order.note_added`, `attachment.added`, `membership.created`, `membership.updated`, `organization.settings_updated`), so clients must use `addEventListener(<name>, …)`; `onmessage` only receives unnamed events. Data is `{"target_type":…,"target_id":…}`. `GET /api/health/` returns `{"status":"ok"}`, `GET /api/ready/` returns `{"status":"ready"}` or `503 {"status":"unavailable"}`.

## Data integrity and operations

`Membership` associates one Django account with an organization and role. Every queryset is scoped from that membership, including attachment downloads, activity, stream and export. Work-order references and event IDs are unique per organization. The server assigns each reference (`FD-` plus 8 random characters from an alphabet without 0/O/1/I) and ignores any client-supplied value. Uniqueness comes from the `(organization, reference)` constraint rather than a prior lookup: a colliding insert fails inside its own savepoint and is retried with a new reference (up to 5 attempts), so duplicates cannot be stored even across API instances. Django stores password hashes using its configured password hashers.

Scheduling windows are half-open `[start,end)` intervals and both bounds are required together; start must precede end. PostgreSQL installs `btree_gist` and enforces a partial GiST exclusion constraint on technician equality and `tstzrange` overlap, ignoring unassigned/completed/cancelled orders. Thus concurrent API instances rely on the database constraint, not process-local locks. A conflicting write is returned as HTTP 409. Because PostgreSQL checks an exclusion constraint after inserting the row, two simultaneous overlapping writes can each wait on the other's uncommitted row; PostgreSQL then aborts one as a deadlock victim (SQLSTATE `40P01`). At most one row ever commits, and the service retries the victim's transaction once, by which point the other write has committed, so the loser receives the normal 409 rather than a 500. Retries are logged as warnings. The exclusion is per technician across the database; organization membership validation prevents cross-organization assignments.

Progress event body:

```json
{
  "eventId": "evt-10001",
  "workOrderId": "work-order-uuid",
  "type": "status_changed",
  "occurredAt": "2026-08-04T10:30:00Z",
  "payload": {"status": "in_progress", "note": "Work started"}
}
```

Allowed types are `status_changed` (status `in_progress` or `completed`, optional note) and `note` (non-empty note). The event is validated before opening a transaction. Within one transaction, the order row is locked, assignment/tenant authority is checked, the event is inserted, the order is updated if applicable, and immutable-by-API audit/realtime rows are added. Unique `(organization,event_id)` plus the transaction provides idempotency under simultaneous retries; repeats return the existing ID with `duplicate:true` and do not apply a second update. A failed operation rolls back the event and order update together.

Assignment notifications are sent to Celery only after the work-order transaction commits. The worker records attempt/outcome rows; temporary provider errors retry with exponential delay and a maximum of four retries, and permanent errors terminate. Set `NOTIFICATION_PROVIDER_MODE=success|temporary|permanent` to control the mock. A stable `{work-order}:{assignment-revision}` provider idempotency key and a unique simulated receipt suppress duplicate delivery; a stale `processing` claim can be retried after ten minutes. The mock receipt models provider-side idempotency; a real integration must pass that key to a provider that honors it. If the broker is unavailable at commit, the API keeps the order write and logs the publish failure; this baseline has no durable outbox/redrive worker, so the notification must be retried operationally. Start an independent worker with `celery -A config worker --loglevel=INFO`.

Uploads accept signature-checked PDF/JPEG/PNG/GIF/WebP only, with a configurable per-file limit (`ATTACHMENT_MAX_BYTES`, default 10 MiB) and per-organization quota (`Organization.storage_limit_bytes`, default 1 GiB). The stored identifier is generated; original names are display/download metadata only. Production should move the file to private object storage and use short-lived authorized downloads; filesystem paths are not returned. CSV uses the same role/tenant filters, streams database chunks, and prefixes spreadsheet-formula-leading cells.

SSE checks the session and organization before streaming, filters every event by that organization, uses persisted event IDs and honors `Last-Event-ID` for reconnect. The connection emits keep-alives and ends after 25 seconds so clients reconnect with their cursor. It is a polling implementation; updates may be delayed by up to about one second, and a disconnected client can catch up only while events are retained. A missed connection does not block normal API operation.

## Tests, monitoring and known scope limits

The backend tests exercise login, role/tenant boundaries, order validation/listing, event idempotency and rollback, upload validation/quota/access, formula-safe tenant CSV, notification outcomes/deduplication, SSE isolation, and concurrent scheduling/event submission. Run them against PostgreSQL, not SQLite. For host-run commands, export `DJANGO_SECRET_KEY`, `POSTGRES_*` and `REDIS_URL` from the root `.env`; `manage.py test` always selects `config.settings.test` (in-memory cache, in-memory file storage and eager Celery), so Redis and the worker are not needed. Health/readiness and JSON-structured Django/Celery logs are provided; request IDs are included in responses, errors and request-context logs. Redis-backed DRF throttles are 10 login attempts/minute/IP and 120 progress events/minute/user, shared between API instances.

This backend-only baseline does **not** implement password reset/MFA, a forced password change after the owner-set initial password, user deletion (by design: users are deactivated so that work orders, attachments, progress events and audit entries keep a valid actor; personal-data erasure would anonymise the user row instead), audit-log retention/archival, malware scanning, object storage, an actual notification provider, or a production ASGI/SSE broker. Organization name and storage quota are owner-manageable; broader billing/security settings are not included. SSE polling and local media storage are suitable for the assessment baseline, not large deployments. Configure a production WSGI/ASGI server, shared private object storage, TLS/secure cookie policy, secrets manager, managed PostgreSQL/Redis, provider-side notification idempotency, monitoring/alerts and verified backups before deployment. Graceful process orchestration and restore drills belong to the deployment environment and are not claimed as implemented here.
