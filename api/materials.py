"""Materials / inventory blueprint."""
from __future__ import annotations

from flask import Blueprint, request

from database import db as _db
from api.utils import (
    ok, created, not_found, bad_request,
    login_required, new_id, to_snake, to_camel, camel_list, db_path, today_iso,
)

materials_bp = Blueprint("materials", __name__, url_prefix="/api/materials")

_CATEGORIES = {
    "Cement & Aggregates", "Steel & Structural Metals", "Bricks & Masonry",
    "Electrical & Lighting", "Plumbing & Sanitary", "Finishes & Paints",
    "Chemicals & Admixtures", "Safety & Site Gear",
}
_FIELDS = {"id", "name", "category", "unit", "quantity", "min_stock_level", "unit_price", "supplier", "assigned_project_id", "last_updated"}


def _validate(fields: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not str(fields.get("name", "")).strip():
        errors["name"] = "Material name is required"
    if fields.get("category") not in _CATEGORIES:
        errors["category"] = "Invalid category"
    if not str(fields.get("unit", "")).strip():
        errors["unit"] = "Unit is required"
    try:
        if float(fields.get("unit_price", -1)) < 0:
            errors["unitPrice"] = "Unit price must be >= 0"
    except (TypeError, ValueError):
        errors["unitPrice"] = "Unit price must be a number"
    try:
        if float(fields.get("min_stock_level", -1)) < 0:
            errors["minStockLevel"] = "Min stock level must be >= 0"
    except (TypeError, ValueError):
        errors["minStockLevel"] = "Min stock level must be a number"
    return errors


@materials_bp.get("")
@login_required
def list_materials():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    materials = _db.list_records("materials", project_id=project_id, path=path)
    transactions = _db.list_records("stock_transactions", path=path)
    for material in materials:
        material["usage_history"] = [
            {"date": row["date"], "type": row["type"], "quantity": row["quantity"],
             "notes": row["notes"], "project_id": row["project_id"]}
            for row in transactions if row["material_id"] == material["id"]
        ]
    return ok({"materials": camel_list(materials)})


@materials_bp.get("/<material_id>")
@login_required
def get_material(material_id: str):
    path = db_path()
    material = _db.get_record("materials", material_id, path)
    if material is None:
        return not_found(f"Material '{material_id}' not found")
    transactions = _db.list_records("stock_transactions", path=path)
    material["usage_history"] = [
        {"date": row["date"], "type": row["type"], "quantity": row["quantity"],
         "notes": row["notes"], "project_id": row["project_id"]}
        for row in transactions if row["material_id"] == material_id
    ]
    return ok({"material": to_camel(material)})


@materials_bp.post("")
@login_required
def create_material():
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    errors = _validate(fields)
    if errors:
        return bad_request(errors)
    fields["id"] = str(fields.get("id") or new_id("mat-"))
    fields.setdefault("quantity", 0)
    fields.setdefault("supplier", "")
    fields.setdefault("assigned_project_id", None)
    fields.setdefault("last_updated", today_iso())
    try:
        saved = _db.save_record("materials", fields, db_path())
        return created({"material": to_camel(saved)}, f"/api/materials/{saved['id']}")
    except Exception as exc:
        return bad_request({"error": str(exc)})


@materials_bp.put("/<material_id>")
@materials_bp.patch("/<material_id>")
@login_required
def update_material(material_id: str):
    path = db_path()
    existing = _db.get_record("materials", material_id, path)
    if existing is None:
        return not_found(f"Material '{material_id}' not found")
    data = request.get_json(silent=True) or {}
    fields = {k: v for k, v in to_snake(data).items() if k in _FIELDS}
    merged = dict(existing)
    merged.update(fields)
    merged["id"] = material_id
    errors = _validate(merged)
    if errors:
        return bad_request(errors)
    try:
        saved = _db.save_record("materials", merged, path)
        return ok({"material": to_camel(saved)})
    except Exception as exc:
        return bad_request({"error": str(exc)})


@materials_bp.delete("/<material_id>")
@login_required
def delete_material(material_id: str):
    deleted = _db.delete_record("materials", material_id, db_path())
    if not deleted:
        return not_found(f"Material '{material_id}' not found")
    return ok({"message": "Material deleted"}, 204)


# ---------------------------------------------------------------------------
# Stock movements
# ---------------------------------------------------------------------------

@materials_bp.post("/<material_id>/stock-in")
@login_required
def stock_in(material_id: str):
    data = request.get_json(silent=True) or {}
    try:
        qty = float(data.get("quantity", 0))
    except (TypeError, ValueError):
        return bad_request({"quantity": "Must be a positive number"})
    notes = str(data.get("notes", ""))
    project_id = data.get("projectId") or data.get("project_id")
    movement_date = data.get("movementDate") or data.get("date")
    try:
        result = _db.stock_in(material_id, qty, notes, project_id, db_path(), movement_date)
        return ok(result)
    except LookupError as exc:
        return not_found(str(exc))
    except ValueError as exc:
        return bad_request({"error": str(exc)})


@materials_bp.post("/<material_id>/stock-out")
@login_required
def stock_out(material_id: str):
    data = request.get_json(silent=True) or {}
    try:
        qty = float(data.get("quantity", 0))
    except (TypeError, ValueError):
        return bad_request({"quantity": "Must be a positive number"})
    notes = str(data.get("notes", ""))
    project_id = data.get("projectId") or data.get("project_id")
    movement_date = data.get("movementDate") or data.get("date")
    try:
        result = _db.stock_out(material_id, qty, notes, project_id, db_path(), movement_date)
        return ok(result)
    except LookupError as exc:
        return not_found(str(exc))
    except ValueError as exc:
        return bad_request({"error": str(exc)})


@materials_bp.get("/<material_id>/transactions")
@login_required
def material_transactions(material_id: str):
    path = db_path()
    # Confirm material exists
    if _db.get_record("materials", material_id, path) is None:
        return not_found(f"Material '{material_id}' not found")
    txns = _db.list_records("stock_transactions", path=path)
    txns = [t for t in txns if t["material_id"] == material_id]
    return ok({"transactions": txns})


@materials_bp.get("/inventory-summary")
@login_required
def inventory_summary():
    project_id = request.args.get("projectId") or request.args.get("project_id")
    path = db_path()
    summary = _db.get_inventory_summary(project_id, path)
    return ok(summary)

