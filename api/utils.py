"""Shared utilities for BuildTrack API blueprints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from flask import jsonify, request, session, current_app, Response

from database import db as _db


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def new_id(prefix: str = "") -> str:
    """Generate a short unique ID compatible with the frontend format."""
    short = uuid.uuid4().hex[:8]
    return f"{prefix}{short}" if prefix else short


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def ok(data: dict | list, status: int = 200) -> Response:
    return jsonify(data), status


def created(data: dict, location: str = "") -> Response:
    response = jsonify(data)
    response.status_code = 201
    if location:
        response.headers["Location"] = location
    return response


def not_found(message: str = "Not found") -> Response:
    return jsonify({"error": message}), 404


def bad_request(errors: dict | str) -> Response:
    if isinstance(errors, str):
        errors = {"error": errors}
    return jsonify(errors), 400


def conflict(message: str) -> Response:
    return jsonify({"error": message}), 409


def server_error(message: str = "Internal server error") -> Response:
    return jsonify({"error": message}), 500


# ---------------------------------------------------------------------------
# camelCase ↔ snake_case conversion
# ---------------------------------------------------------------------------

_CAMEL_TO_SNAKE: dict[str, str] = {
    "projectId": "project_id",
    "assignedProjectId": "assigned_project_id",
    "startDate": "start_date",
    "expectedCompletionDate": "expected_completion_date",
    "dueDate": "due_date",
    "assignedTo": "assigned_to",
    "dailyWage": "daily_wage",
    "minStockLevel": "min_stock_level",
    "unitPrice": "unit_price",
    "lastUpdated": "last_updated",
    "paymentRef": "payment_ref",
    "paymentMethod": "payment_method",
    "workCompleted": "work_completed",
    "progressPercentage": "progress_percentage",
    "workersPresent": "workers_present",
    "milestonesAchieved": "milestones_achieved",
    "weatherConditions": "weather_conditions",
    "materialsConsumed": "materials_consumed",
    "issuesEncountered": "issues_encountered",
    "delayBlockers": "delay_blockers",
    "nextDayPlan": "next_day_plan",
    "reportedBy": "reported_by",
    "companyName": "company_name",
    "contractorName": "contractor_name",
    "licenseNumber": "license_number",
    "currencySymbol": "currency_symbol",
    "dateFormat": "date_format",
    "budgetThreshold": "budget_threshold",
    "overdueTasks": "overdue_tasks",
    "lowStockAlerts": "low_stock_alerts",
    "deadlineAlertsDays": "deadline_alerts_days",
    "workerId": "worker_id",
    "materialId": "material_id",
    "movementDate": "movement_date",
    "assignedProject": "assigned_project_id",
    "usageHistory": "usage_history",
    "isActive": "is_active",
    "assignedProjectIds": "assigned_project_ids",
}

_SNAKE_TO_CAMEL: dict[str, str] = {v: k for k, v in _CAMEL_TO_SNAKE.items()}


def to_snake(data: dict) -> dict:
    """Convert incoming camelCase JSON keys to snake_case for the DB layer."""
    return {_CAMEL_TO_SNAKE.get(k, k): v for k, v in data.items()}


def to_camel(data: dict) -> dict:
    """Convert snake_case DB keys to camelCase for JSON responses."""
    return {_SNAKE_TO_CAMEL.get(k, k): v for k, v in data.items()}


def camel_list(rows: list[dict]) -> list[dict]:
    return [to_camel(row) for row in rows]


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required"}), 401
        with _db.transaction(db_path()) as connection:
            profile = connection.execute(
                "SELECT role,email,is_active FROM user_profiles WHERE id = ?", (session["user_id"],)
            ).fetchone()
        if profile is None or not profile["is_active"]:
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        session["user_role"] = profile["role"]
        session["user_email"] = profile["email"]
        return f(*args, **kwargs)
    return decorated


def db_path() -> str:
    return current_app.config["DATABASE_PATH"]


def assigned_project_ids(user_id: int | None = None) -> set[str]:
    """Return project memberships for project-scoped stakeholder accounts."""
    profile_id = user_id if user_id is not None else session.get("user_id")
    if not profile_id:
        return set()
    with _db.transaction(db_path()) as connection:
        rows = connection.execute(
            "SELECT project_id FROM user_project_access WHERE profile_id = ? ORDER BY project_id",
            (profile_id,),
        ).fetchall()
    return {row["project_id"] for row in rows}


def project_allowed(project_id: str | None) -> bool:
    """Check an object's project against the signed-in stakeholder's assignments."""
    return session.get("user_role") not in ("Client", "Site Engineer") or bool(
        project_id and project_id in assigned_project_ids()
    )


def client_can_access_project(project_id: str, user_id: int | None = None) -> bool:
    return project_id in assigned_project_ids(user_id)

