# BuildTrack backend branch review (read-only)

Review date: 2026-11-21  
Baseline: `feature/buildtrack-frontend` (checked out; unchanged)  
Reviewed refs: `origin/feature/auth-projects-tasks`, `origin/my`, `origin/labour-attendance-material`

## Scope and method

I inspected the committed source in each remote Git tree without checking out branches. I compared it with the checked-out frontend, `database/schema.sql`, `database/db.py`, and the browser data layer. Python files in all three branches passed in-memory Python AST parsing (syntax check); this does not prove imports or runtime behavior. The frontend/database suite was run locally; it uses temporary SQLite databases and cleans them up. No backend HTTP/API integration suite was run. The pre-existing untracked `api/` folder was left untouched and was not treated as part of any branch.

## Overall project status

The frontend is a working local prototype backed by browser `localStorage`, while the committed SQLite schema/access layer supports persistent records. The UI is not currently wired to any HTTP backend: `js/data.js` implements reads and writes locally (for example lines 970-1288), and frontend modules use `window.DataStore`. The login is explicitly a frontend-only prototype at `js/data.js:1255-1275`. All three backend branches need a deliberate API integration/adaptation before they can power this UI.

The backend branches are separate partial efforts, not a drop-in combined backend. Branch 1 has auth plus project/task APIs and the matching SQLite helper layer, branch 2 has finance/progress/risk/dashboard/report routes built for SQL Server, and branch 3 has worker/attendance/material APIs with a separate SQLite database and different schema. Combining them as-is creates incompatible database assumptions, URL prefixes, data shapes, and security policies.

## Baseline: frontend and database

- `database/schema.sql` defines `projects`, `tasks`, `workers`, `attendance`, `materials`, `stock_transactions`, `expenses`, `payments`, `progress_reports`, `company_settings`, and `user_profiles`. It uses text IDs for most business entities, snake_case columns, foreign keys, and constrained values.
- `database/db.py:11-12` points at `database/buildtrack.sqlite3`; `connect()` enables foreign keys at lines 112-121. The database file is not committed in the baseline; `database/init_db.py` must initialize it before API use.
- `js/data.js:970-1288` is the active storage interface. It returns camelCase fields such as `projectId`, `assignedProjectId`, `dailyWage`, `paymentRef`, and `progressPercentage`, but does not call `fetch()` or an API client.
- `js/app.js:9-29` describes role-based UI access. Since the current UI trusts a localStorage user, these client checks are not server-side security.
- The schema has no password/account table. `user_profiles` is explicitly a profile table, not credentials (schema comment immediately before that table).

## Findings by teammate branch

### 1. `origin/feature/auth-projects-tasks`

**Implemented correctly**

- `backend/app.py:184-357` provides registration, login, current-user, and logout routes. It uses Werkzeug password hashing/checking and Flask signed sessions. Registration requires an eight-character password and limits later account creation to an administrator.
- `backend/app.py:364-560` provides project and task list/get/create/update/delete routes, parameterized through the shared database helper. Project reads include a client filter; writes have role checks.
- `database/db.py` (757 lines) matches the baseline schema and contains reusable CRUD, stock, report, dashboard, finance, and attendance helpers. Its fixed table/column allow-lists and SQL parameters are good safeguards.
- Backend Python syntax parsed successfully.

**Errors and missing features**

- Only authentication, projects, and tasks are exposed as Flask routes. There are no HTTP routes for labour/attendance, inventory/materials, finance/payments, progress reports, risk intelligence, dashboard, or reporting. The corresponding helper functions in `database/db.py` are not endpoints.
- `backend/app.py:567` calls `initialize_auth_table()` at import time, but never calls `database.init_db.initialize_database()`. On a clean checkout, `db.connect()` creates an empty SQLite file and only `auth_accounts` is created. Project/profile tables are absent, so registration can fail when it checks `projects` (`app.py:231-238`) or inserts `user_profiles` (`app.py:264-270`); project/task API calls likewise fail.
- The Flask app imports `database.db` from the project root. Running it as `python backend/app.py` can make the root package import unavailable depending on the working directory/Python path; launch mode/package setup is not documented in requirements.
- No CORS configuration exists. The frontend is a static app, so a separately hosted Flask API will be blocked by browser CORS unless served same-origin or configured.
- `app.py:17-20` has a predictable development fallback secret; lines 22-24 disable secure cookies. Line 570 enables debug mode. These are local-development settings only and must not ship to production.
- Client authorization compares exact client names (`app.py:152-161`); there is no project membership/account linkage, and task endpoints do not apply client scoping because clients are excluded from task roles. Registration has no rate limit or email verification. First-admin bootstrap based on an empty account count should be made a one-time controlled setup to avoid race/operational issues.
- The UI accepts six-character passwords (`index.html:76`, `js/data.js:1265`), but this API requires eight. More fundamentally, UI login never calls the API, so the routes are not exercised by the existing frontend.

**Database / contract**

- SQLite and table names align with the baseline schema, including `user_profiles`; auth adds a separate `auth_accounts` table.
- Project/task API uses snake_case request/response fields, while the UI's data objects are camelCase. A mapping adapter is needed (for example `expected_completion_date` ↔ `expectedCompletionDate`, `project_id` ↔ `projectId`, `due_date` ↔ `dueDate`). UI local IDs are also generated client-side and this API generates IDs on create.
- The project/task routes use `/api/projects` and `/api/tasks`; there are no matching frontend calls today.

**Verdict: NEEDS FIXES.** This is the closest backend foundation to the committed SQLite code, but initialization, security hardening, missing domain routes, and frontend integration are required before merge/use.

### 2. `origin/my`

**Implemented correctly**

- `backend/app.py:9-18` creates a Flask app, enables CORS, registers a team blueprint, and has a health endpoint.
- `backend/routes/team3_routes.py` contains finance/payment, progress-report, heuristic risk, dashboard summary, and report endpoints. The risk logic has budget burn, schedule, stock, and labour rules (`285-411`).
- Python syntax parsed successfully.

**Errors and missing features**

- This branch targets SQL Server, not this app's SQLite database: `backend/db.py:2-29` requires `pyodbc` and constructs a SQL Server ODBC connection. The project schema is SQLite. The requirements (`backend/requirements.txt:1-4`) include SQL Server-specific dependencies and do not make it compatible with the baseline database.
- SQL assumes different schema names/columns: `expenses.expense_date`, `payments.payment_date`, `daily_progress_reports`, `labour`, and a stored `projects.spent` column. Baseline tables instead use `expenses.date`, `payments.date`, `progress_reports`, `workers`, and compute spending via `project_financial_summary`.
- The risk/dashboard/report queries (`team3_routes.py:286-312, 423-437, 508-509`) consequently fail against the current schema even if SQL Server connectivity were replaced with SQLite. The risk endpoint also assumes dates are present/valid and can error on nulls.
- `backend/app.py:3,13` imports/registers `routes.team3_routes`, but the tracked path is `backend/routes/team3_routes.py`; the imports are top-level `routes` and `db` (`team3_routes.py:4`) rather than package-relative. Starting from repository root will generally fail to import. Branch tree has no root `routes/` or `db.py`.
- Finance/progress routes use `/api/v1` prefix (`app.py:13`) and `projectId` query keys, while branch 1 uses `/api` and the baseline database helper expects `project_id`. Endpoint writes often return camelCase JSON, but backend SQL mappings vary.
- Expense/payment/progress writes use multiple independent connections. For progress, report insertion and project update are separate commits (`team3_routes.py:244-269`), so partial updates can leave inconsistent progress. Expense recalculation writes a `spent` column absent in baseline (`12-20`).
- There are no login/session/role checks on any routes. `CORS(app)` is unrestricted and server binds all interfaces with debug enabled (`app.py:10,22`).
- Numeric parsing of amount/progress can raise unhandled errors (e.g. payment amount at `team3_routes.py:140`, progress conversion at `233-234`); random IDs can collide. DELETE endpoints frequently return success even when the record did not exist.

**Correctly covered functions**

- Finance expenses/payments and status toggle; progress report create/list/delete; rule-based project risk assessments; dashboard KPI summary; progress/finance/payments/labour/material/task report data are present in source.
- These functions are not compatible with current database/schema and cannot run as-is.

**Verdict: NOT READY.** It is a SQL Server prototype with import/package errors and schema mismatches, and it lacks authentication/authorization. Port it to the existing SQLite schema or explicitly redesign/migrate the whole app first.

### 3. `origin/labour-attendance-material`

**Implemented correctly**

- `backend/app.py:167-317` provides worker CRUD, `325-386` attendance read/write, and `394-648` material CRUD, stock movement, and history routes.
- Stock-out checks available quantity before subtraction (`app.py:584-591`); movement history records are written with the balance update.
- It enables SQLite foreign keys for its own connection (`app.py:18-22`) and uses parameterized record values. Python syntax parsed successfully.

**Errors and missing features**

- It uses a second database, `backend/buildtrack.db` (`app.py:14`), rather than baseline `database/buildtrack.sqlite3`. The branch also commits a binary `backend/buildtrack.db`; the API will not read the user's baseline database.
- Its initializer creates reduced, differently shaped `workers`, `attendance`, and `materials` tables (`42-71`) and adds columns ad hoc. Baseline has text worker/material IDs, `assigned_project_id`, constraints, and a `stock_transactions` table. This code uses integer internal IDs plus `frontend_id`, `project_id`, and `material_history`. It is a parallel schema, not a compatible migration.
- `get_workers()` selects `dailyWage` and `assignedProjectId` aliases (`172-184`), while POST expects mixed snake_case/camelCase. The UI is localStorage-only and does not call these endpoints.
- Attendance accepts `P/A/L` and returns those codes (`325-366`), while baseline stores `present/absent/leave`; UI stores a date-keyed map of those words (`js/data.js:1055-1064`). GET returns a flat array with `worker_id`, not the UI map format.
- Worker/material project assignments use empty strings for unassigned values (`app.py:229-230, 463-464`), while baseline uses nullable foreign keys. The smaller schema has no project foreign keys, so assignments are not validated.
- No APIs exist for projects/tasks/finance/payments/progress/risk/dashboard/reports and no authentication or authorization exists. Wildcard CORS is enabled (`app.py:7-12`); debug mode is enabled at line 654.
- In `initialize_database()`, the schema is committed, but it is only run in the `__main__` path (`651-654`). Importing the module for a WSGI server leaves the separate database uninitialized.
- Database connections are manually closed in many handlers; unexpected SQL exceptions can leak a connection. Creating rows and linking history lacks consistent transaction/error handling.
- Stock history API is additional functionality, but its `material_history` table does not match the baseline `stock_transactions` schema.

**Verdict: NEEDS FIXES.** Useful isolated labour/material prototypes, but they require a proper migration/adaptation to the baseline SQLite schema, consistent field formats, server-side authorization, and frontend wiring.

## Integration compatibility

| Pair / combination | Assessment |
|---|---|
| Branch 1 + Branch 2 | Not directly compatible. Branch 2 uses SQL Server and imports files from paths absent in branch 1; its routes use `/api/v1`, and its tables differ. |
| Branch 1 + Branch 3 | Possible only after reworking branch 3 to use branch 1's database helpers/schema and resolving endpoint contracts. Both define Flask apps and separate SQLite paths now. |
| Branch 2 + Branch 3 | Not compatible as-is: SQL Server vs SQLite, distinct endpoint prefixes, table contracts, and no shared authentication. |
| All three | Not integration-ready. Merge would leave duplicate backend entry points, separate DB connection code, inconsistent route prefixes, and no common security/serialization layer. |

The first branch has no direct route-name collision with the third because it currently exposes only projects/tasks/auth. If all are mounted together, normalize to one Flask app, a single SQLite access layer, one API prefix, consistent snake_case/camelCase serialization, and a shared authentication/role policy. Do not merge the SQL Server route set unchanged.

## Tests and what was not tested

- **PASS:** `python -m unittest database.test_db` on the checked-out baseline: 29 tests passed. These cover schema initialization/migration, database constraints, CRUD helpers, financial/inventory/dashboard queries, stock movements, progress synchronization, and project deletion.
- **PASS:** In-memory syntax parsing for Python files found in the three backend branch trees.
- **NOT TESTED:** Backend Flask app startup, imports, dependency installation, live HTTP requests, authentication/session flows, CORS behavior, actual teammate SQLite/SQL Server availability, and API-to-frontend browser flows. Backend code was not copied or executed because these checks could write database files or require unavailable external services.
- **NOT TESTED:** End-to-end combined backend. It is not currently safe/meaningful to start because the branches point at different databases and schemas.

## Exact corrections required before integration

1. Pick the baseline SQLite schema as the source of truth (or document and implement a deliberate database migration). Use one database path and call `initialize_database()` before serving requests, including under WSGI.
2. Keep one Flask app and register blueprints with a single documented prefix. Fix branch 2 imports to package-relative paths and eliminate the SQL Server-only `CONVERT`/`GETDATE` queries or consciously port the database.
3. Implement missing APIs for each domain against baseline table names, including `workers`, `attendance`, `materials`, `stock_transactions`, `expenses`, `payments`, and `progress_reports`; expose rule-based risk, dashboard, and report routes.
4. Add a frontend API client and explicit serializers matching the current `DataStore` camelCase objects. Update authentication UI to call login/logout/current-user; align the six/eight-character password rules.
5. Use server-enforced authentication and per-route role/project checks for all branches. Remove default production secrets, debug mode, and wildcard/unrestricted CORS; add CSRF protection if cookie sessions are used cross-origin.
6. Make multi-row operations transactional (especially progress report plus project progress; stock balance plus transaction row), validate input types/enums/dates, handle missing IDs consistently, and avoid random short IDs that can collide.
7. Add backend tests for route imports/startup, request/response contracts, role denials, validation, and each API against temporary copies of the baseline SQLite schema.

## Final verdicts

- `origin/feature/auth-projects-tasks`: **NEEDS FIXES**
- `origin/my`: **NOT READY**
- `origin/labour-attendance-material`: **NEEDS FIXES**
- Combined integration: **NOT READY**
