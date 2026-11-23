"""Daily Progress Report (DPR) blueprint."""
from __future__ import annotations

from flask import Blueprint, request, session

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path, assigned_project_ids, not_found, project_allowed,
)

progress_bp = Blueprint("progress", __name__, url_prefix="/api/progress")
_FIELDS = {"id", "project_id", "date", "work_completed", "progress_percentage", "workers_present", "milestones_achieved", "weather_conditions", "materials_consumed", "issues_encountered", "delay_blockers", "next_day_plan", "reported_by"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not fields.get("project_id"):
        errors["projectId"] = "Project is required"
    if not fields.get("date"):
        errors["date"] = "Date is required"
    if not str(fields.get("work_completed", "")).strip():
        errors["workCompleted"] = "Work completed description is required"
    try:
        pct = int(fields.get("progress_percentage", -1))
        if not 0 <= pct <= 100:
            errors["progressPercentage"] = "Progress must be 0–100"
    except (TypeError, ValueError):
        errors["progressPercentage"] = "Progress must be a number 0–100"
    return errors


@progress_bp.get("")
@login_required
def list_reports():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    if project_id == "all":
        project_id = None
    path = db_path()
    reports = _db.list_records("progress_reports", project_id=project_id, path=path)
    if session.get("user_role") in ("Client", "Site Engineer"):
        allowed = assigned_project_ids()
        if project_id and project_id not in allowed:
            return not_found("Project not found")
        reports = [report for report in reports if report["project_id"] in allowed]
    return ok({"reports": camel_list(reports)})


@progress_bp.get("/<report_id>")
@login_required
def get_report(report_id: str):
    report = _db.get_record("progress_reports", report_id, db_path())
    if report is None:
        return not_found(f"Report '{report_id}' not found")
    if session.get("user_role") in ("Client", "Site Engineer") and report["project_id"] not in assigned_project_ids():
        return not_found("Report not found")
    return ok({"report": to_camel(report)})


@progress_bp.post("")
@login_required
def create_report():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    fields["id"] = str(fields.get("id") or new_id("dpr-"))
    errors = _validate(fields)
    if fields.get("project_id") and not project_allowed(fields["project_id"]):
        return not_found("Project not found")
    if errors:
        return bad_request(errors)
    fields.setdefault("workers_present", 0)
    fields.setdefault("milestones_achieved", "")
    fields.setdefault("weather_conditions", "")
    fields.setdefault("materials_consumed", "")
    fields.setdefault("issues_encountered", "")
    fields.setdefault("delay_blockers", "")
    fields.setdefault("next_day_plan", "")
    fields.setdefault("reported_by", "")
    try:
        saved = _db.save_progress_report(fields, db_path())
        return created({"report": to_camel(saved)}, f"/api/progress/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@progress_bp.put("/<report_id>")
@progress_bp.patch("/<report_id>")
@login_required
def update_report(report_id: str):
    path = db_path()
    existing = _db.get_record("progress_reports", report_id, path)
    if existing is None:
        return not_found(f"Report '{report_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = report_id
    if not project_allowed(merged.get("project_id")):
        return not_found("Report not found")
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_progress_report(merged, path)
        return ok({"report": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@progress_bp.delete("/<report_id>")
@login_required
def delete_report(report_id: str):
    existing = _db.get_record("progress_reports", report_id, db_path())
    if existing and not project_allowed(existing["project_id"]):
        return not_found("Report not found")
    deleted = _db.delete_record("progress_reports", report_id, db_path())
    if not deleted:
        return not_found(f"Report '{report_id}' not found")
    return ok({"message": "Report deleted"}, 204)

