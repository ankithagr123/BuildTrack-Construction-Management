"""Reports blueprint — data export endpoints."""
from __future__ import annotations

from flask import Blueprint, request, session, jsonify

from database import db as _db
from api.utils import ok, bad_request, login_required, camel_list, db_path, today_iso, assigned_project_ids
from api.risks import compute_risks

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

_REPORT_TYPES = {"progress", "finance", "labour", "materials", "payments", "tasks", "risk"}


@reports_bp.get("/<report_type>")
@login_required
def get_report(report_type: str):
    if report_type not in _REPORT_TYPES:
        return bad_request({"error": f"Unknown report type: {report_type!r}"})
    is_client = session.get("user_role") == "Client"
    is_engineer = session.get("user_role") == "Site Engineer"
    if is_client and report_type != "progress":
        return jsonify({"error": "Client accounts may only view assigned project progress reports"}), 403
    if is_engineer and report_type not in ("progress", "tasks"):
        return jsonify({"error": "Site Engineer accounts may only view assigned project progress and task reports"}), 403
    project_id = request.args.get("projectId") or request.args.get("project_id")
    if project_id == "all":
        project_id = None
    as_of = request.args.get("asOfDate") or request.args.get("date", today_iso())
    path = db_path()
    try:
        if report_type == "risk":
            records = compute_risks(project_id, path)
        else:
            records = _db.get_report_records(report_type, project_id, as_of, path)
        if is_client or is_engineer:
            allowed = assigned_project_ids()
            if project_id and project_id not in allowed:
                return jsonify({"error": "Project not found"}), 404
            records = [record for record in records if record.get("project_id") in allowed]
        return ok({"reportType": report_type, "records": camel_list(records)})
    except ValueError as exc:
        return bad_request({"error": str(exc)})

