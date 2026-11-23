# BuildTrack

BuildTrack is a Flask and SQLite construction project management app with a same-origin HTML/CSS/JavaScript frontend. Projects, tasks, workers, attendance, materials, stock movements, expenses, payments, progress reports, risk findings, dashboard data, reports, and company settings use `database/buildtrack.sqlite3` as the persisted source of truth. Risk findings use explainable rules; no machine-learning model is claimed.

## Windows setup

Run these commands from the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m database.init_db
python -m api.create_admin
python -m api.app
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). Create the first administrator in the terminal prompt. Passwords are hashed in SQLite. Later accounts can be created and managed by an authenticated administrator in the account management panel on Projects. Admins can assign stakeholder roles and client projects, edit account details, activate or deactivate accounts, and reset passwords. Public registration is disabled.

## Start BuildTrack when Windows signs in

Double-click `Install BuildTrack Auto Start.bat` once to add the existing launcher to the current user's Startup folder (or use the equivalent per-user Run entry if the Startup folder is unavailable). At sign-in, the visible launcher starts a single supervisor from the existing `.venv`; it checks the BuildTrack health endpoint, starts or recovers Flask on port 5001, and opens the installed BuildTrack PWA only after the health check succeeds. The console stays open with Flask output and errors, which are also written to `%LOCALAPPDATA%\BuildTrack\logs\startup.log`. Closing the PWA does not stop Flask. Run `Uninstall BuildTrack Auto Start.bat` to disable automatic startup.

## Install BuildTrack as a PWA

BuildTrack includes a web app manifest, 192px and 512px app icons, and a versioned service worker. Serve it from Flask at `http://127.0.0.1:5001` or from HTTPS; service workers are disabled on ordinary insecure LAN/HTTP origins. In a supported desktop browser, use the **Install app** button when it appears or choose **Install app** from the browser menu. On iPhone or iPad, use **Share → Add to Home Screen**. The installed app opens in standalone mode with Projects, Tasks, and Materials shortcuts where the platform supports shortcuts.

The service worker precaches the app shell and an offline notice, revalidates frontend files so installed clients pick up fixes, and uses the notice only when navigation cannot reach Flask. The offline notice retries the server automatically. Same-origin `/api/` requests always go to Flask and are never cached; API responses are marked `no-store`. Offline sign-in and SQLite updates are unavailable.

For production, set a strong `SECRET_KEY` in the process environment and serve over HTTPS. For local development, Flask uses a development-only key. The application serves the frontend and `/api/` from the same origin; do not open `index.html` directly or use a separate static server because cookie authentication requires the Flask origin.

The initializer runs numbered, transactional migrations. Version 6 adds the separate `auth_accounts` table; version 7 adds account activation and client project memberships; version 8 adds Half-day attendance while copying existing attendance records; version 9 adds an ownership manifest for safely removable demo rows; version 10 normalizes the four role labels in place; version 11 adds structured DPR milestone and weather fields without rebuilding report rows. Migrations preserve existing profile and project records and never drop the business tables. Existing accounts migrate as active, with no implicit client project assignments. The first administrator command can attach credentials to an existing profile by email when that profile has no login account.

## Authentication and roles

Sign in with the administrator account created during setup. If its password is forgotten, run `python -m api.reset_admin_password` from the project directory, enter the existing Admin email, type `RESET`, then enter and confirm a new password. The command only updates the password hash for a matching active Admin and refuses if the database file is missing. The role selected on the sign-in form is only a display preference; the server-assigned account role controls access. Administrators manage users with `/api/auth/users`, `/api/auth/register`, and `/api/auth/users/<id>`. The user-profile page updates the signed-in profile. API requests use a Flask session cookie; logout clears the session.

| Role | Server permissions |
|---|---|
| Admin | All modules and account administration |
| Site Engineer | View projects, tasks, workers, attendance, progress, and reports; edit tasks, attendance, and progress |
| Storekeeper | View projects and inventory; edit inventory and record stock movements |
| Client | Read-only project, progress, and report routes |

Client accounts are read-only and can access only projects explicitly assigned by an administrator. Project list, direct project, progress, and progress-report endpoints enforce membership on the server. Clients do not receive dashboard or finance access.

## API areas

All routes use `/api/`: `/auth`, `/projects`, `/tasks`, `/workers`, `/attendance`, `/materials`, `/expenses`, `/payments`, `/progress`, `/risks`, `/dashboard`, `/reports`, and `/settings`. The API accepts the existing frontend camelCase fields and maps them to the SQLite schema. Validation and foreign keys are enforced in the route/database layers; stock movements and progress updates use atomic database helpers.

The existing synchronous frontend controllers continue to use `DataStore`. After successful authentication it hydrates their view cache from the API. Edits are sent to Flask and errors are shown in the UI. Before the first hydration, existing browser data is copied to a LocalStorage backup. The Settings page has a manual, duplicate-aware import action for that backup; nothing is imported automatically. Browser cache data is not synchronized while offline.

Administrators can choose **Load Demo Data** in Settings to append one realistic, linked sample dataset to SQLite. It requires confirmation, runs as a single transaction, and cannot be loaded twice. A confirmed Remove Demo Data action deletes only registered sample rows and refuses removal if unregistered child records have been added. It adds four projects and related labour, half-day-capable attendance, stock transactions, expenses, payment entries, tasks, and progress reports. Demo data is never inserted automatically at startup.

## Tests

Run all database helper, Flask API integration, authentication, migration, and password-reset tests. They use isolated temporary databases and leave the project's SQLite file untouched:

```powershell
python -m unittest discover -v
```

Check JavaScript syntax with:

```powershell
Get-ChildItem js -Filter *.js | ForEach-Object { node --check $_.FullName }
node api/test_service_worker.js
```

## Existing data and backup

Back up `database/buildtrack.sqlite3` before deploying code changes. Migrations 6–10 preserve existing accounts and business records; migration 8 copies existing attendance rows while enabling the Half-day status, and migration 9 adds the demo-data ownership manifest. Existing `user_profiles` entries have no passwords until an administrator account is explicitly provisioned. Existing browser LocalStorage remains in that browser as a one-time pre-sync backup and can be imported from Settings; records with IDs already present in SQLite are skipped.

## Limitations

- Client accounts need explicit project assignments; accounts migrated without assignments see no projects until an administrator assigns them.
- The first administrator is provisioned from the terminal; later account management is available in the Projects view for administrators.
- Frontend rendering uses a LocalStorage view cache hydrated from SQLite after sign-in. Server writes are asynchronous through the shared service layer; visible API errors indicate a failed save.
- The PWA shell can load offline, but the application API and data changes require the Flask server.
