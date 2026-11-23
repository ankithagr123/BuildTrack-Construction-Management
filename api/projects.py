"""Projects blueprint — full CRUD with camelCase API boundary."""
from __future__ import annotations

from flask import Blueprint, request, session

from database import db as _db
from database.db import ProjectDeletionError
from api.utils import (
    ok, created, not_found, bad_request, conflict, server_error,
    login_required, new_id, to_snake, to_camel, camel_list, db_path,
    assigned_project_ids,
)

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")

_EDITABLE = {
    "name", "client", "location", "manager",
    "start_date", "expected_completion_date",
    "budget", "progress", "status", "description",
}


def _safe_project(project: dict) -> dict:
    """Do not disclose project budgets or spending to non-admin roles."""
    result = dict(project)
    if session.get("user_role") != "Admin":
        for field in ("budget", "spent", "remaining_budget"):
            result.pop(field, None)
    return result


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not str(fields.get("name", "")).strip():
        errors["name"] = "Project name is required"
    if not str(fields.get("client", "")).strip():
        errors["client"] = "Client name is required"
    if not str(fields.get("location", "")).strip():
        errors["location"] = "Location is required"
    if not str(fields.get("manager", "")).strip():
        errors["manager"] = "Project manager is required"
    start = fields.get("start_date", "")
    end = fields.get("expected_completion_date", "")
    if not start:
        errors["startDate"] = "Start date is required"
    if not end:
        errors["expectedCompletionDate"] = "Completion date is required"
    if start and end and start > end:
        errors["expectedCompletionDate"] = "Completion date must be after start date"
    try:
        budget = float(fields.get("budget", 0))
        if budget < 10000:
            errors["budget"] = "Budget must be at least ₹10,000"
    except (TypeError, ValueError):
        errors["budget"] = "Budget must be a number"
    status = fields.get("status", "")
    if status not in ("ongoing", "planning", "delayed", "completed"):
        errors["status"] = "Status must be ongoing, planning, delayed, or completed"
    return errors


@projects_bp.get("")
@login_required
def list_projects():
    path = db_path()
    projects = _db.list_projects(path)
    if session.get("user_role") in ("Client", "Site Engineer"):
        allowed = assigned_project_ids()
        projects = [project for project in projects if project["id"] in allowed]
    return ok({"projects": camel_list([_safe_project(project) for project in projects])})


@projects_bp.get("/<project_id>")
@login_required
def get_project(project_id: str):
    path = db_path()
    project = _db.get_project(project_id, path)
    if project is None:
        return not_found(f"Project '{project_id}' not found")
    if session.get("user_role") in ("Client", "Site Engineer") and project_id not in assigned_project_ids():
        return not_found("Project not found")
    return ok({"project": to_camel(_safe_project(project))})


@projects_bp.post("")
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    fields = to_snake(data)
    fields = {k: v for k, v in fields.items() if k in _EDITABLE or k == "id"}
    errors = _validate(fields)
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("proj-"))
    fields.setdefault("progress", 0)
    fields.setdefault("description", "")
    # Round budget to nearest 5000
    try:
        budget = float(fields["budget"])
        fields["budget"] = round(budget / 5000) * 5000 if budget >= 10000 else budget
    except (TypeError, ValueError):
        pass
    try:
        saved = _db.save_record("projects", fields, db_path())
        project = _db.get_project(saved["id"], db_path())
        return created(
            {"project": to_camel(project)},
            f"/api/projects/{saved['id']}",
        )
    except Exception as exc:
        return bad_request({"error": str(exc)})


@projects_bp.put("/<project_id>")
@projects_bp.patch("/<project_id>")
@login_required
def update_project(project_id: str):
    path = db_path()
    existing = _db.get_project(project_id, path)
    if existing is None:
        return not_found(f"Project '{project_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = to_snake(data)
    # For PUT replace editable fields; for PATCH merge
    merged = {k: existing[k] for k in _EDITABLE if k in existing}
    merged.update({k: v for k, v in fields.items() if k in _EDITABLE})
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    merged["id"] = project_id
    try:
        _db.save_record("projects", merged, path)
        project = _db.get_project(project_id, path)
        return ok({"project": to_camel(project)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@projects_bp.delete("/<project_id>")
@login_required
def delete_project(project_id: str):
    path = db_path()
    try:
        _db.delete_project(project_id, path)
        return ok({"message": "Project deleted"}, 204)
    except ProjectDeletionError as exc:
        if exc.not_found:
            return not_found(str(exc))
        return conflict(str(exc))
    except Exception as exc:
        return server_error(str(exc))

