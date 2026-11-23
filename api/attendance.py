"""Attendance blueprint."""
from __future__ import annotations

from flask import Blueprint, request, session

from database import db as _db
from api.utils import (
    ok, bad_request, login_required, to_snake, db_path, today_iso,
    assigned_project_ids,
)

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


@attendance_bp.get("/records")
@login_required
def stored_attendance_records():
    date = request.args.get("date", today_iso())
    attendance = _db.get_attendance_for_date(date, db_path())
    if session.get("user_role") == "Site Engineer":
        with _db.transaction(db_path()) as connection:
            rows = connection.execute("SELECT id,assigned_project_id FROM workers").fetchall()
        allowed_workers = {row["id"] for row in rows if row["assigned_project_id"] in assigned_project_ids()}
        attendance = {worker_id: status for worker_id, status in attendance.items() if worker_id in allowed_workers}
    return ok({"date": date, "attendance": attendance})


@attendance_bp.get("")
@login_required
def get_attendance():
    date = request.args.get("date", today_iso())
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    # Return workers with their attendance status for the given date
    workers = _db.list_records("workers", project_id=project_id, path=path)
    if session.get("user_role") == "Site Engineer":
        workers = [worker for worker in workers if worker.get("assigned_project_id") in assigned_project_ids()]
    attendance_map = _db.get_attendance_for_date(date, path)
    result = []
    for w in workers:
        status = attendance_map.get(
            w["id"],
            "present" if w["availability"] == "On Site" else "absent",
        )
        result.append({"workerId": w["id"], "name": w["name"], "status": status})
    return ok({"date": date, "attendance": result})


@attendance_bp.post("")
@login_required
def save_attendance():
    """Accept {date, attendance: {workerId: status}} and save atomically."""
    data = request.get_json(silent=True) or {}
    date = data.get("date", today_iso())
    attendance_raw = data.get("attendance", {})

    # Support both {workerId: status} and [{workerId, status}] formats
    if isinstance(attendance_raw, list):
        attendance_map = {item["workerId"]: item["status"] for item in attendance_raw}
    else:
        attendance_map = {str(k): str(v) for k, v in attendance_raw.items()}

    allowed = {"present", "absent", "half-day", "leave"}
    errors = {wid: "Invalid status" for wid, s in attendance_map.items() if s not in allowed}
    if errors:
        return bad_request({"attendance": errors})

    try:
        if session.get("user_role") == "Site Engineer":
            with _db.transaction(db_path()) as connection:
                rows = connection.execute("SELECT id,assigned_project_id FROM workers").fetchall()
            allowed_workers = {row["id"] for row in rows if row["assigned_project_id"] in assigned_project_ids()}
            if set(attendance_map) - allowed_workers:
                return bad_request({"error": "Attendance can only be changed for workers on assigned projects"})
        saved = _db.save_attendance_for_date(date, attendance_map, db_path())
        return ok({"date": date, "attendance": saved})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@attendance_bp.get("/summary")
@login_required
def attendance_summary():
    date = request.args.get("date", today_iso())
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    if session.get("user_role") == "Site Engineer" and not project_id:
        allowed = assigned_project_ids()
        with _db.transaction(path) as connection:
            rows = connection.execute(
                "SELECT id FROM workers WHERE assigned_project_id IN (" + ",".join("?" for _ in allowed) + ")" if allowed else "SELECT id FROM workers WHERE 1=0",
                tuple(allowed),
            ).fetchall()
        worker_ids = {row["id"] for row in rows}
        statuses = _db.get_attendance_for_date(date, path)
        summary = {"total": len(worker_ids), "present": 0, "absent": 0, "half_day": 0, "leave": 0}
        with _db.transaction(path) as connection:
            workers = connection.execute(
                "SELECT id,availability FROM workers WHERE id IN (" + ",".join("?" for _ in worker_ids) + ")" if worker_ids else "SELECT id,availability FROM workers WHERE 1=0",
                tuple(worker_ids),
            ).fetchall()
        for worker in workers:
            status = statuses.get(worker["id"], "present" if worker["availability"] == "On Site" else "absent")
            key = {"half-day": "half_day"}.get(status, status)
            if key in summary:
                summary[key] += 1
    else:
        summary = _db.get_attendance_summary(date, project_id, path)
    return ok(summary)

