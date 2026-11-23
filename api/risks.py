"""Risk Intelligence blueprint — deterministic rule-based risk engine."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from flask import Blueprint, request

from database import db as _db
from api.utils import ok, login_required, db_path

risks_bp = Blueprint("risks", __name__, url_prefix="/api/risks")

_SEVERITY_WEIGHTS = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _days_until(date_str: str, today: str) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        t = datetime.strptime(today, "%Y-%m-%d").date()
        return (d - t).days
    except (ValueError, TypeError):
        return 999


def compute_risks(project_id: str | None, path: str) -> list[dict]:
    """Calculate all risk alerts from live database records."""
    today = _today()
    projects = _db.list_projects(path)
    if project_id and project_id != "all":
        projects = [p for p in projects if p["id"] == project_id]

    all_tasks = _db.list_records("tasks", path=path)
    all_materials = _db.list_records("materials", path=path)
    all_expenses = _db.list_records("expenses", path=path)
    all_reports = _db.list_records("progress_reports", path=path)
    all_workers = _db.list_records("workers", path=path)
    attendance_today = _db.get_attendance_for_date(today, path)

    risks: list[dict] = []

    # Build lookup sets
    projects_with_reports: set[str] = {r["project_id"] for r in all_reports}
    report_dates_by_project: dict[str, list[str]] = {}
    for r in all_reports:
        report_dates_by_project.setdefault(r["project_id"], []).append(r["date"])

    for project in projects:
        pid = project["id"]
        pname = project["name"]
        budget = float(project["budget"])
        spent = float(project.get("spent", 0))
        status = project["status"]
        progress = int(project.get("progress", 0))
        end_date = project.get("expected_completion_date", "")

        tasks = [t for t in all_tasks if t["project_id"] == pid]
        materials = [m for m in all_materials if m.get("assigned_project_id") == pid]
        expenses = [e for e in all_expenses if e["project_id"] == pid]
        workers = [w for w in all_workers if w.get("assigned_project_id") == pid]

        # --- Overdue tasks ---
        overdue_tasks = [t for t in tasks if t["status"] != "completed" and t["due_date"] < today]
        if overdue_tasks:
            risks.append({
                "id": f"risk-overdue-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "overdue_tasks",
                "severity": "high" if len(overdue_tasks) >= 3 else "medium",
                "title": f"{len(overdue_tasks)} overdue task{'s' if len(overdue_tasks) > 1 else ''}",
                "reason": f"{len(overdue_tasks)} task(s) past due date in project {pname!r}",
                "recommendation": "Review and reschedule overdue tasks; communicate with assignees",
                "affectedCount": len(overdue_tasks),
            })

        # --- Project delay ---
        days_left = _days_until(end_date, today)
        if status == "delayed" or (status == "ongoing" and days_left < 0):
            risks.append({
                "id": f"risk-delay-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "project_delay",
                "severity": "critical" if days_left < -30 else "high",
                "title": "Project delayed",
                "reason": f"{pname!r} deadline was {end_date} ({abs(days_left)} days ago)",
                "recommendation": "Update project schedule and brief client on revised timeline",
                "affectedCount": 1,
            })
        elif status == "ongoing" and 0 <= days_left <= 14:
            risks.append({
                "id": f"risk-deadline-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "upcoming_deadline",
                "severity": "medium" if days_left >= 7 else "high",
                "title": f"Deadline in {days_left} day{'s' if days_left != 1 else ''}",
                "reason": f"{pname!r} is due on {end_date}",
                "recommendation": "Confirm completion plan and prepare handover documentation",
                "affectedCount": 1,
            })

        # --- Budget overrun ---
        if budget > 0:
            utilization = spent / budget * 100
            if utilization >= 100:
                risks.append({
                    "id": f"risk-budget-overrun-{pid}",
                    "projectId": pid,
                    "projectName": pname,
                    "type": "budget_overrun",
                    "severity": "critical",
                    "title": "Budget exceeded",
                    "reason": f"Spent ₹{spent:,.0f} of ₹{budget:,.0f} ({utilization:.0f}%)",
                    "recommendation": "Raise a change order or find cost savings immediately",
                    "affectedCount": 1,
                })
            elif utilization >= 85:
                risks.append({
                    "id": f"risk-budget-high-{pid}",
                    "projectId": pid,
                    "projectName": pname,
                    "type": "high_expenditure",
                    "severity": "high",
                    "title": f"Budget {utilization:.0f}% utilized",
                    "reason": f"Spent ₹{spent:,.0f} of ₹{budget:,.0f}",
                    "recommendation": "Review remaining scope and forecast final cost",
                    "affectedCount": 1,
                })

        # --- Low material stock ---
        low_stock = [
            m for m in materials
            if float(m["quantity"]) <= float(m["min_stock_level"]) and float(m["quantity"]) > 0
        ]
        out_of_stock = [m for m in materials if float(m["quantity"]) <= 0]
        if out_of_stock:
            risks.append({
                "id": f"risk-outofstock-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "out_of_stock",
                "severity": "critical",
                "title": f"{len(out_of_stock)} material(s) out of stock",
                "reason": ", ".join(m["name"] for m in out_of_stock[:5]),
                "recommendation": "Place emergency purchase orders immediately",
                "affectedCount": len(out_of_stock),
            })
        elif low_stock:
            risks.append({
                "id": f"risk-lowstock-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "low_stock",
                "severity": "medium",
                "title": f"{len(low_stock)} material(s) below reorder level",
                "reason": ", ".join(m["name"] for m in low_stock[:5]),
                "recommendation": "Raise purchase orders before stock runs out",
                "affectedCount": len(low_stock),
            })

        # --- Labour shortage ---
        active_workers = [w for w in workers if w["status"] == "active"]
        if status == "ongoing" and len(active_workers) == 0:
            risks.append({
                "id": f"risk-labour-{pid}",
                "projectId": pid,
                "projectName": pname,
                "type": "no_labour",
                "severity": "critical",
                "title": "No workers assigned",
                "reason": f"Project {pname!r} has no active workers assigned",
                "recommendation": "Assign workers to this project immediately",
                "affectedCount": 0,
            })

        if status == "ongoing" and active_workers:
            statuses = [
                attendance_today.get(worker["id"], "present" if worker["availability"] == "On Site" else "absent")
                for worker in active_workers
            ]
            present = sum(status == "present" for status in statuses)
            turnout = sum(1.0 if status == "present" else 0.5 if status == "half-day" else 0.0 for status in statuses) / len(active_workers)
            if turnout < 0.6:
                risks.append({
                    "id": f"risk-attendance-{pid}",
                    "projectId": pid,
                    "projectName": pname,
                    "type": "low_attendance",
                    "severity": "high" if turnout < 0.35 else "medium",
                    "title": f"Low workforce attendance ({turnout:.0%})",
                    "reason": f"{present} full-day equivalent(s) plus {sum(status == 'half-day' for status in statuses)} half-day worker(s), from {len(active_workers)} active assigned workers",
                    "recommendation": "Confirm worker availability and arrange substitute crews for critical activities",
                    "affectedCount": len(active_workers) - present,
                })

        # --- Missing progress updates ---
        if status == "ongoing":
            last_dates = sorted(report_dates_by_project.get(pid, []), reverse=True)
            if not last_dates:
                risks.append({
                    "id": f"risk-noprogress-{pid}",
                    "projectId": pid,
                    "projectName": pname,
                    "type": "missing_progress",
                    "severity": "medium",
                    "title": "No daily progress reports",
                    "reason": f"No DPR has been filed for {pname!r}",
                    "recommendation": "File a daily progress report to keep records current",
                    "affectedCount": 0,
                })
            else:
                days_since = _days_until(today, last_dates[0]) * -1 if last_dates[0] < today else 0
                if days_since >= 7:
                    risks.append({
                        "id": f"risk-staleprogress-{pid}",
                        "projectId": pid,
                        "projectName": pname,
                        "type": "stale_progress",
                        "severity": "low",
                        "title": f"No progress update for {days_since} days",
                        "reason": f"Last DPR for {pname!r} was on {last_dates[0]}",
                        "recommendation": "File an updated progress report today",
                        "affectedCount": 0,
                    })

    # Sort by severity weight descending
    risks.sort(key=lambda r: _SEVERITY_WEIGHTS.get(r["severity"], 0), reverse=True)
    return risks


@risks_bp.get("")
@login_required
def list_risks():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    risks = compute_risks(project_id, path)
    critical = sum(1 for r in risks if r["severity"] == "critical")
    high = sum(1 for r in risks if r["severity"] == "high")
    return ok({
        "risks": risks,
        "summary": {
            "total": len(risks),
            "critical": critical,
            "high": high,
            "medium": sum(1 for r in risks if r["severity"] == "medium"),
            "low": sum(1 for r in risks if r["severity"] == "low"),
        }
    })

