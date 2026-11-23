"""Labour / workers blueprint."""
from __future__ import annotations

from flask import Blueprint, request, session

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path,
    assigned_project_ids, project_allowed, not_found,
)

labour_bp = Blueprint("labour", __name__, url_prefix="/api/workers")

_SKILLS = {
    "Head Mason", "Brickwork Mason", "Shuttering Carpenter",
    "Lead Bar Bender / Rebar", "Licensed Electrician", "Senior Plumber",
    "Civil Site Supervisor", "Concrete Pump Operator",
    "Structural Welder & Fabricator", "Specialist Tile & Paint Finisher",
    "Waterproofing Applicator", "General Civil Helper",
}
_AVAILABILITIES = {"On Site", "Available"}
_STATUSES = {"active", "inactive"}
_FIELDS = {"id", "name", "skill", "phone", "assigned_project_id", "daily_wage", "availability", "status"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not str(fields.get("name", "")).strip():
        errors["name"] = "Worker name is required"
    if fields.get("skill") not in _SKILLS:
        errors["skill"] = "Invalid skill selected"
    try:
        wage = float(fields.get("daily_wage", 0))
        if wage < 300:
            errors["dailyWage"] = "Daily wage must be at least ₹300"
    except (TypeError, ValueError):
        errors["dailyWage"] = "Daily wage must be a number"
    if fields.get("availability") not in _AVAILABILITIES:
        errors["availability"] = "Availability must be On Site or Available"
    if fields.get("status") not in _STATUSES:
        errors["status"] = "Status must be active or inactive"
    return errors


@labour_bp.get("")
@login_required
def list_workers():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    workers = _db.list_records("workers", project_id=project_id, path=path)
    if session.get("user_role") in ("Client", "Site Engineer"):
        workers = [worker for worker in workers if worker.get("assigned_project_id") in assigned_project_ids()]
    if session.get("user_role") == "Site Engineer":
        workers = [{key: value for key, value in worker.items() if key != "daily_wage"} for worker in workers]
    return ok({"workers": camel_list(workers)})


@labour_bp.get("/<worker_id>")
@login_required
def get_worker(worker_id: str):
    worker = _db.get_record("workers", worker_id, db_path())
    if worker is None:
        return not_found(f"Worker '{worker_id}' not found")
    if session.get("user_role") == "Site Engineer" and not project_allowed(worker.get("assigned_project_id")):
        return not_found("Worker not found")
    if session.get("user_role") == "Site Engineer":
        worker.pop("daily_wage", None)
    return ok({"worker": to_camel(worker)})


@labour_bp.post("")
@login_required
def create_worker():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    fields.setdefault("status", "active")
    fields.setdefault("availability", "Available")
    errors = _validate(fields)
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("wkr-"))
    fields.setdefault("phone", "")
    fields.setdefault("assigned_project_id", None)
    # Snap wage to nearest 50
    try:
        wage = float(fields["daily_wage"])
        fields["daily_wage"] = round(wage / 50) * 50
    except (TypeError, ValueError):
        pass
    try:
        saved = _db.save_record("workers", fields, db_path())
        return created({"worker": to_camel(saved)}, f"/api/workers/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@labour_bp.put("/<worker_id>")
@labour_bp.patch("/<worker_id>")
@login_required
def update_worker(worker_id: str):
    path = db_path()
    existing = _db.get_record("workers", worker_id, path)
    if existing is None:
        return not_found(f"Worker '{worker_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = worker_id
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_record("workers", merged, path)
        return ok({"worker": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@labour_bp.delete("/<worker_id>")
@login_required
def delete_worker(worker_id: str):
    deleted = _db.delete_record("workers", worker_id, db_path())
    if not deleted:
        return not_found(f"Worker '{worker_id}' not found")
    return ok({"message": "Worker deleted"}, 204)

