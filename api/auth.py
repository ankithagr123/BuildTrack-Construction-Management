"""Session authentication and administrator-managed accounts."""
from __future__ import annotations

import re

from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from api.utils import assigned_project_ids, bad_request, db_path, ok, to_camel
from database import db as _db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
_ROLES = {
    "Admin", "Site Engineer",
    "Storekeeper", "Client",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _profile_with_credentials(email: str, path: str) -> dict | None:
    with _db.transaction(path) as connection:
        row = connection.execute(
            """SELECT p.id,p.name,p.role,p.email,p.avatar,p.is_active,a.password_hash
               FROM user_profiles p JOIN auth_accounts a ON a.profile_id=p.id
               WHERE p.email=? COLLATE NOCASE""", (email,)
        ).fetchone()
        return dict(row) if row else None


def _user_payload(profile: dict) -> dict:
    result = {key: value for key, value in profile.items() if key != "password_hash"}
    result["assigned_project_ids"] = sorted(assigned_project_ids(result["id"]))
    return to_camel(result)


def _is_admin() -> bool:
    return bool(session.get("user_id") and session.get("user_role") == "Admin")


def _requested_project_ids(value: object) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return sorted(set(value))


def _projects_exist(connection, project_ids: list[str]) -> bool:
    if not project_ids:
        return True
    marks = ",".join("?" for _ in project_ids)
    count = connection.execute(
        f"SELECT COUNT(*) FROM projects WHERE id IN ({marks})", project_ids
    ).fetchone()[0]
    return count == len(project_ids)


def _replace_memberships(connection, profile_id: int, project_ids: list[str]) -> None:
    connection.execute("DELETE FROM user_project_access WHERE profile_id=?", (profile_id,))
    connection.executemany(
        "INSERT INTO user_project_access(profile_id,project_id) VALUES(?,?)",
        [(profile_id, project_id) for project_id in project_ids],
    )


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or not password:
        return bad_request({"email": "Email and password are required"})
    account = _profile_with_credentials(email, db_path())
    if not account or not account["is_active"] or not check_password_hash(account["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    session.clear()
    session.permanent = True
    session["user_id"] = account["id"]
    session["user_email"] = account["email"]
    session["user_role"] = account["role"]
    return ok({"user": _user_payload(account), "message": "Login successful"})


@auth_bp.post("/logout")
def logout():
    session.clear()
    return ok({"message": "Logged out"})


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    with _db.transaction(db_path()) as connection:
        row = connection.execute(
            "SELECT id,name,role,email,avatar,is_active FROM user_profiles WHERE id=?", (user_id,)
        ).fetchone()
    if not row or not row["is_active"]:
        session.clear()
        return jsonify({"error": "Not authenticated"}), 401
    return ok({"user": _user_payload(dict(row))})


@auth_bp.patch("/me")
def update_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return bad_request({"error": "A JSON object is required"})
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    if not name or not _EMAIL.fullmatch(email):
        return bad_request({"error": "Name and a valid email are required"})
    try:
        with _db.transaction(db_path()) as connection:
            cursor = connection.execute("UPDATE user_profiles SET name=?,email=? WHERE id=? AND is_active=1", (name,email,user_id))
            if not cursor.rowcount:
                session.clear()
                return jsonify({"error": "Account not found or inactive"}), 401
            row = connection.execute(
                "SELECT id,name,role,email,avatar,is_active FROM user_profiles WHERE id=?", (user_id,)
            ).fetchone()
        session["user_email"] = email
        return ok({"user": _user_payload(dict(row))})
    except Exception:
        return jsonify({"error": "Email is already in use or the profile could not be updated"}), 409


@auth_bp.get("/users")
def list_users():
    if not _is_admin():
        return jsonify({"error": "Administrator access required"}), 403
    with _db.transaction(db_path()) as connection:
        rows = connection.execute(
            "SELECT id,name,role,email,avatar,is_active FROM user_profiles ORDER BY name,id"
        ).fetchall()
    return ok({"users": [_user_payload(dict(row)) for row in rows]})


@auth_bp.post("/register")
def register():
    """Public Admin registration is disabled. Logged-in admins create accounts here."""
    if not _is_admin():
        return jsonify({"error": "Administrator access required"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return bad_request({"error": "A JSON object is required"})
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = data.get("role", "Site Engineer")
    project_ids = _requested_project_ids(data.get("assignedProjectIds", []))
    errors = {}
    if not name:
        errors["name"] = "Name is required"
    if not _EMAIL.fullmatch(email):
        errors["email"] = "A valid email is required"
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if role not in _ROLES:
        errors["role"] = "Invalid stakeholder role"
    if project_ids is None:
        errors["assignedProjectIds"] = "Project assignments must be a list of project IDs"
    elif role not in ("Client", "Site Engineer") and project_ids:
        errors["assignedProjectIds"] = "Only Client and Site Engineer accounts can have project assignments"
    if errors:
        return bad_request(errors)
    try:
        with _db.transaction(db_path()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not _projects_exist(connection, project_ids):
                return bad_request({"assignedProjectIds": "One or more projects do not exist"})
            cursor = connection.execute(
                "INSERT INTO user_profiles(name,role,email,avatar,is_active) VALUES(?,?,?,?,1)",
                (name, role, email, ""),
            )
            profile_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO auth_accounts(profile_id,password_hash) VALUES(?,?)",
                (profile_id, generate_password_hash(password)),
            )
            _replace_memberships(connection, profile_id, project_ids)
            row = connection.execute(
                "SELECT id,name,role,email,avatar,is_active FROM user_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        return ok({"user": _user_payload(dict(row)), "message": "Account created"}, 201)
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            return jsonify({"error": "Email already registered"}), 409
        return jsonify({"error": "Could not create account"}), 400


@auth_bp.patch("/users/<int:user_id>")
def update_user(user_id: int):
    if not _is_admin():
        return jsonify({"error": "Administrator access required"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return bad_request({"error": "A JSON object is required"})
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    role = data.get("role")
    password = str(data.get("password", ""))
    active = data.get("isActive")
    project_ids = _requested_project_ids(data.get("assignedProjectIds")) if "assignedProjectIds" in data else None
    errors = {}
    if not name:
        errors["name"] = "Name is required"
    if not _EMAIL.fullmatch(email):
        errors["email"] = "A valid email is required"
    if role not in _ROLES:
        errors["role"] = "Invalid stakeholder role"
    if password and len(password) < 8:
        errors["password"] = "Reset password must be at least 8 characters"
    if active is not None and active not in (True, False, 0, 1):
        errors["isActive"] = "Account active state must be true or false"
    if "assignedProjectIds" in data and project_ids is None:
        errors["assignedProjectIds"] = "Project assignments must be a list of project IDs"
    elif project_ids is not None and role not in ("Client", "Site Engineer") and project_ids:
        errors["assignedProjectIds"] = "Only Client and Site Engineer accounts can have project assignments"
    if errors:
        return bad_request(errors)
    try:
        with _db.transaction(db_path()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT role,is_active,name,email FROM user_profiles WHERE id=?", (user_id,)
            ).fetchone()
            if not current:
                return jsonify({"error": "User not found"}), 404
            name = name or current["name"]
            email = email or current["email"]
            role = role or current["role"]
            active = current["is_active"] if active is None else active
            if project_ids is None:
                project_ids = [row[0] for row in connection.execute(
                    "SELECT project_id FROM user_project_access WHERE profile_id=? ORDER BY project_id", (user_id,)
                ).fetchall()]
            if current["role"] == "Admin" and (role != "Admin" or not bool(active)):
                active_admins = connection.execute(
                    "SELECT COUNT(*) FROM user_profiles WHERE role='Admin' AND is_active=1"
                ).fetchone()[0]
                if current["is_active"] and active_admins <= 1:
                    return jsonify({"error": "Cannot deactivate or demote the last active administrator"}), 409
            if not _projects_exist(connection, project_ids):
                return bad_request({"assignedProjectIds": "One or more projects do not exist"})
            connection.execute(
                "UPDATE user_profiles SET name=?,email=?,role=?,is_active=? WHERE id=?",
                (name,email,role,int(bool(active)),user_id),
            )
            if password:
                cursor = connection.execute(
                    "UPDATE auth_accounts SET password_hash=? WHERE profile_id=?",
                    (generate_password_hash(password), user_id),
                )
                if not cursor.rowcount:
                    raise RuntimeError("Password account changed during reset")
            _replace_memberships(connection, user_id, project_ids)
            row = connection.execute(
                "SELECT id,name,role,email,avatar,is_active FROM user_profiles WHERE id=?", (user_id,)
            ).fetchone()
        if user_id == session.get("user_id") and not bool(active):
            session.clear()
        return ok({"user": _user_payload(dict(row)), "message": "Account updated"})
    except Exception:
        return jsonify({"error": "Could not update account; email may already be in use"}), 409


@auth_bp.delete("/users/<int:user_id>")
def delete_user(user_id: int):
    if not _is_admin():
        return jsonify({"error": "Administrator access required"}), 403
    if user_id == session.get("user_id"):
        return bad_request({"error": "You cannot delete your own account"})
    with _db.transaction(db_path()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT role,is_active FROM user_profiles WHERE id=?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        if row["role"] == "Admin" and row["is_active"]:
            count = connection.execute(
                "SELECT COUNT(*) FROM user_profiles WHERE role='Admin' AND is_active=1"
            ).fetchone()[0]
            if count <= 1:
                return jsonify({"error": "Cannot delete the last active administrator"}), 409
        connection.execute("DELETE FROM user_profiles WHERE id=?", (user_id,))
    return ok({"message": "User deleted"})
