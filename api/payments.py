"""Payments blueprint."""
from __future__ import annotations

from flask import Blueprint, request

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

_STATUSES = {"Paid", "Pending", "Failed"}
_FIELDS = {"id", "payment_ref", "project_id", "recipient", "amount", "date", "status", "payment_method", "notes"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not fields.get("project_id"):
        errors["projectId"] = "Project is required"
    if not str(fields.get("recipient", "")).strip():
        errors["recipient"] = "Recipient is required"
    try:
        if float(fields.get("amount", 0)) <= 0:
            errors["amount"] = "Amount must be greater than 0"
    except (TypeError, ValueError):
        errors["amount"] = "Amount must be a number"
    if not fields.get("date"):
        errors["date"] = "Date is required"
    if fields.get("status") not in _STATUSES:
        errors["status"] = "Status must be Paid, Pending, or Failed"
    if not str(fields.get("payment_method", "")).strip():
        errors["paymentMethod"] = "Payment method is required"
    return errors


@payments_bp.get("")
@login_required
def list_payments():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    payments = _db.list_records("payments", project_id=project_id, path=path)
    return ok({"payments": camel_list(payments)})


@payments_bp.get("/<payment_id>")
@login_required
def get_payment(payment_id: str):
    payment = _db.get_record("payments", payment_id, db_path())
    if payment is None:
        return not_found(f"Payment '{payment_id}' not found")
    return ok({"payment": to_camel(payment)})


@payments_bp.post("")
@login_required
def create_payment():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    fields.setdefault("status", "Pending")
    # Auto-generate payment reference if not provided
    if not fields.get("payment_ref"):
        fields["payment_ref"] = f"PAY-{new_id().upper()}"
    errors = _validate(fields)
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("pay-"))
    fields.setdefault("notes", "")
    try:
        saved = _db.save_record("payments", fields, db_path())
        return created({"payment": to_camel(saved)}, f"/api/payments/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@payments_bp.put("/<payment_id>")
@payments_bp.patch("/<payment_id>")
@login_required
def update_payment(payment_id: str):
    path = db_path()
    existing = _db.get_record("payments", payment_id, path)
    if existing is None:
        return not_found(f"Payment '{payment_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = payment_id
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_record("payments", merged, path)
        return ok({"payment": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@payments_bp.delete("/<payment_id>")
@login_required
def delete_payment(payment_id: str):
    deleted = _db.delete_record("payments", payment_id, db_path())
    if not deleted:
        return not_found(f"Payment '{payment_id}' not found")
    return ok({"message": "Payment deleted"}, 204)

