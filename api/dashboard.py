"""Dashboard blueprint — aggregated KPIs and chart data."""
from __future__ import annotations

from flask import Blueprint, request

from database import db as _db
from api.utils import ok, login_required, db_path, today_iso

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.get("/stats")
@login_required
def dashboard_stats():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    as_of = request.args.get("asOfDate") or request.args.get("date", today_iso())
    path = db_path()
    summary = _db.get_dashboard_summary(project_id, as_of, path)
    return ok(summary)


@dashboard_bp.get("/chart-data")
@login_required
def chart_data():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    return ok({
        "projects": _db.get_project_chart_data(path),
        "expenses": _db.get_expense_chart_data(project_id, path=path),
    })


@dashboard_bp.get("/recent")
@login_required
def recent_activity():
    path = db_path()
    limit = int(request.args.get("limit", 10))
    expenses = _db.list_records("expenses", path=path)[:limit]
    payments = _db.list_records("payments", path=path)[:limit]
    reports = _db.list_records("progress_reports", path=path)[:limit]
    projects = _db.list_projects(path)
    today = today_iso()
    tasks = _db.list_records("tasks", path=path)
    overdue = [t for t in tasks if t["status"] != "completed" and t["due_date"] < today]
    upcoming = [t for t in tasks if t["status"] != "completed" and 0 <= (
        (lambda s: int(s.split("-")[2]) + int(s.split("-")[1]) * 30 + int(s.split("-")[0]) * 365)(t["due_date"])
        - (lambda s: int(s.split("-")[2]) + int(s.split("-")[1]) * 30 + int(s.split("-")[0]) * 365)(today)
    ) <= 7]
    materials = _db.list_records("materials", path=path)
    low_stock = [m for m in materials if float(m["quantity"]) <= float(m["min_stock_level"])]
    return ok({
        "recentExpenses": expenses[:5],
        "recentPayments": payments[:5],
        "recentReports": reports[:5],
        "overdueTaskCount": len(overdue),
        "lowStockMaterials": low_stock[:5],
        "projects": projects,
    })

