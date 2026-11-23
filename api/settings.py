"""Company settings blueprint."""
from __future__ import annotations

from flask import Blueprint, request

from database import db as _db
from api.utils import ok, bad_request, login_required, to_snake, to_camel, db_path

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_DEFAULT_SETTINGS = {
    "id": 1,
    "company_name": "",
    "contractor_name": "",
    "email": "",
    "phone": "",
    "gstin": "",
    "license_number": "",
    "currency": "INR",
    "currency_symbol": "₹",
    "date_format": "DD/MM/YYYY",
    "theme": "light",
    "budget_threshold": 85,
    "overdue_tasks": 1,
    "low_stock_alerts": 1,
    "deadline_alerts_days": 14,
}


def _get_settings(path: str) -> dict:
    rows = _db.list_records("company_settings", path=path)
    if rows:
        return rows[0]
    return dict(_DEFAULT_SETTINGS)


@settings_bp.get("")
@login_required
def get_settings():
    path = db_path()
    settings = _get_settings(path)
    return ok({"settings": to_camel(settings)})


@settings_bp.put("")
@settings_bp.patch("")
@login_required
def update_settings():
    path = db_path()
    data = request.get_json(silent=True) or {}
    fields = to_snake(data)
    current = _get_settings(path)
    merged = dict(current)
    # Only allow known setting keys
    allowed_keys = set(_DEFAULT_SETTINGS.keys()) - {"id"}
    for key in allowed_keys:
        if key in fields:
            merged[key] = fields[key]
    merged["id"] = 1
    # Validate theme
    if merged.get("theme") not in ("light", "dark"):
        return bad_request({"theme": "Theme must be light or dark"})
    try:
        saved = _db.save_record("company_settings", merged, path)
        return ok({"settings": to_camel(saved), "message": "Settings saved"})
    except Exception as exc:
        return bad_request({"error": str(exc)})

