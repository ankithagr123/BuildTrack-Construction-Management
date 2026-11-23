"""Finance / expenses blueprint."""
from __future__ import annotations

from flask import Blueprint, request

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path,
)

finance_bp = Blueprint("finance", __name__, url_prefix="/api/expenses")

_CATEGORIES = {"Materials", "Labour", "Equipment", "Transport", "Other"}
_FIELDS = {"id", "title", "project_id", "category", "amount", "date", "payment_method", "description"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not str(fields.get("title", "")).strip():
        errors["title"] = "Title is required"
    if not fields.get("project_id"):
        errors["projectId"] = "Project is required"
    if fields.get("category") not in _CATEGORIES:
        errors["category"] = "Invalid expense category"
    try:
        if float(fields.get("amount", 0)) <= 0:
            errors["amount"] = "Amount must be greater than 0"
    except (TypeError, ValueError):
        errors["amount"] = "Amount must be a number"
    if not fields.get("date"):
        errors["date"] = "Date is required"
    if not str(fields.get("payment_method", "")).strip():
        errors["paymentMethod"] = "Payment method is required"
    return errors


@finance_bp.get("")
@login_required
def list_expenses():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    expenses = _db.list_records("expenses", project_id=project_id, path=path)
    return ok({"expenses": camel_list(expenses)})


@finance_bp.get("/<expense_id>")
@login_required
def get_expense(expense_id: str):
    expense = _db.get_record("expenses", expense_id, db_path())
    if expense is None:
        return not_found(f"Expense '{expense_id}' not found")
    return ok({"expense": to_camel(expense)})


@finance_bp.post("")
@login_required
def create_expense():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    errors = _validate(fields)
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("exp-"))
    fields.setdefault("description", "")
    try:
        saved = _db.save_record("expenses", fields, db_path())
        return created({"expense": to_camel(saved)}, f"/api/expenses/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@finance_bp.put("/<expense_id>")
@finance_bp.patch("/<expense_id>")
@login_required
def update_expense(expense_id: str):
    path = db_path()
    existing = _db.get_record("expenses", expense_id, path)
    if existing is None:
        return not_found(f"Expense '{expense_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = expense_id
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_record("expenses", merged, path)
        return ok({"expense": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@finance_bp.delete("/<expense_id>")
@login_required
def delete_expense(expense_id: str):
    deleted = _db.delete_record("expenses", expense_id, db_path())
    if not deleted:
        return not_found(f"Expense '{expense_id}' not found")
    return ok({"message": "Expense deleted"}, 204)


@finance_bp.get("/summary")
@login_required
def financial_summary():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    summary = _db.get_financial_summary(project_id, path)
    return ok(summary)


@finance_bp.get("/chart-data")
@login_required
def chart_data():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    start = request.args.get("startDate") or request.args.get("start_date")
    end = request.args.get("endDate") or request.args.get("end_date")
    path = db_path()
    data = _db.get_expense_chart_data(project_id, start, end, path)
    return ok(data)

