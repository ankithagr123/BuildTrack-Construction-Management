"""Tasks blueprint."""
from __future__ import annotations

from flask import Blueprint, request, session

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path,
    assigned_project_ids, project_allowed,
)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

_STATUSES = {"todo", "in-progress", "completed"}
_PRIORITIES = {"high", "medium", "low"}
_FIELDS = {"id", "project_id", "title", "description", "assigned_to", "start_date", "due_date", "priority", "status"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not str(fields.get("title", "")).strip():
        errors["title"] = "Task title is required"
    if not fields.get("project_id"):
        errors["projectId"] = "Project is required"
    if not fields.get("due_date"):
        errors["dueDate"] = "Due date is required"
    if fields.get("priority") not in _PRIORITIES:
        errors["priority"] = "Priority must be high, medium, or low"
    if fields.get("status") not in _STATUSES:
        errors["status"] = "Status must be todo, in-progress, or completed"
    return errors


@tasks_bp.get("")
@login_required
def list_tasks():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    tasks = _db.list_records("tasks", project_id=project_id, path=path)
    if session.get("user_role") in ("Client", "Site Engineer"):
        tasks = [task for task in tasks if task["project_id"] in assigned_project_ids()]
    return ok({"tasks": camel_list(tasks)})


@tasks_bp.get("/<task_id>")
@login_required
def get_task(task_id: str):
    task = _db.get_record("tasks", task_id, db_path())
    if task is None:
        return not_found(f"Task '{task_id}' not found")
    if not project_allowed(task["project_id"]):
        return not_found("Task not found")
    return ok({"task": to_camel(task)})


@tasks_bp.post("")
@login_required
def create_task():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    fields.setdefault("status", "todo")
    fields.setdefault("priority", "medium")
    errors = _validate(fields)
    if fields.get("project_id") and not project_allowed(fields["project_id"]):
        return not_found("Project not found")
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("task-"))
    fields.setdefault("description", "")
    fields.setdefault("assigned_to", "")
    fields.setdefault("start_date", None)
    try:
        saved = _db.save_record("tasks", fields, db_path())
        return created({"task": to_camel(saved)}, f"/api/tasks/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@tasks_bp.put("/<task_id>")
@tasks_bp.patch("/<task_id>")
@login_required
def update_task(task_id: str):
    path = db_path()
    existing = _db.get_record("tasks", task_id, path)
    if existing is None:
        return not_found(f"Task '{task_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = task_id
    if not project_allowed(merged.get("project_id")):
        return not_found("Task not found")
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_record("tasks", merged, path)
        return ok({"task": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@tasks_bp.delete("/<task_id>")
@login_required
def delete_task(task_id: str):
    existing = _db.get_record("tasks", task_id, db_path())
    if existing and not project_allowed(existing["project_id"]):
        return not_found("Task not found")
    path = db_path()
    deleted = _db.delete_record("tasks", task_id, path)
    if not deleted:
        return not_found(f"Task '{task_id}' not found")
    return ok({"message": "Task deleted"}, 204)

