"""BuildTrack Flask application factory."""
from __future__ import annotations

import os
from flask import Flask, send_from_directory
from flask import request, session, jsonify

from config import Config, BASE_DIR
from database.init_db import initialize_database


def create_app(config_object: type | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

    # Load configuration
    if config_object is None:
        env = os.environ.get("FLASK_ENV", "development")
        from config import config_by_name
        config_object = config_by_name.get(env, Config)
    app.config.from_object(config_object)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Set SECRET_KEY before starting BuildTrack in production.")

    # Same-origin deployment is the supported setup; session cookies stay first-party.

    # Initialize / migrate the database on startup
    initialize_database(app.config["DATABASE_PATH"])

    # Register API blueprints
    from api.auth import auth_bp
    from api.projects import projects_bp
    from api.tasks import tasks_bp
    from api.labour import labour_bp
    from api.attendance import attendance_bp
    from api.materials import materials_bp
    from api.finance import finance_bp
    from api.payments import payments_bp
    from api.progress import progress_bp
    from api.risks import risks_bp
    from api.dashboard import dashboard_bp
    from api.reports import reports_bp
    from api.settings import settings_bp
    from api.demo_data import demo_bp
    from database import db as _db

    for bp in (
        auth_bp, projects_bp, tasks_bp, labour_bp, attendance_bp,
        materials_bp, finance_bp, payments_bp, progress_bp, risks_bp,
        dashboard_bp, reports_bp, settings_bp, demo_bp,
    ):
        app.register_blueprint(bp)

    @app.before_request
    def enforce_api_permissions():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None
        if request.path == "/api/health" and request.method == "GET":
            return None
        if request.path == "/api/auth/login":
            return None
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required"}), 401
        with _db.transaction(app.config["DATABASE_PATH"]) as connection:
            account = connection.execute(
                "SELECT role,is_active FROM user_profiles WHERE id=?", (session["user_id"],)
            ).fetchone()
        if account is None or not account["is_active"]:
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        session["user_role"] = account["role"]
        role = session.get("user_role")
        path = request.path
        if role in ("Client", "Site Engineer") and path.startswith(("/api/projects", "/api/tasks", "/api/workers", "/api/attendance", "/api/progress", "/api/reports")):
            from api.utils import assigned_project_ids
            allowed = assigned_project_ids()
            requested = request.args.get("projectId") or request.args.get("project_id")
            if requested and requested != "all" and requested not in allowed:
                return jsonify({"error": "Project not found"}), 404
        if request.method in ("GET", "HEAD"):
            read_access = {
                "Site Engineer": ("/api/auth/me", "/api/projects", "/api/tasks", "/api/workers", "/api/attendance", "/api/progress", "/api/reports"),
                "Storekeeper": ("/api/auth/me", "/api/projects", "/api/materials"),
                "Client": ("/api/auth/me", "/api/projects", "/api/progress", "/api/reports"),
            }
            if role != "Admin" and not path.startswith(read_access.get(role, ())):
                return jsonify({"error": "Your role cannot view this information"}), 403
            return None
        auth_self_service = path in ("/api/auth/logout", "/api/auth/me")
        permitted = role == "Admin" or auth_self_service
        if not auth_self_service and role == "Site Engineer":
            permitted = path.startswith(("/api/tasks", "/api/attendance", "/api/progress"))
        elif not auth_self_service and role == "Storekeeper":
            permitted = path.startswith("/api/materials")
        if not permitted:
            return jsonify({"error": "Your role cannot make this change"}), 403
        return None

    @app.after_request
    def prevent_api_caching(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Cookie"
        return response

    # Serve the SPA index for all non-API routes
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"service": "BuildTrack", "status": "ok"})

    @app.route("/")
    def index():
        return send_from_directory(BASE_DIR, "index.html")

    @app.route("/<path:path>")
    def static_files(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "API endpoint not found"}), 404
        import os as _os
        full = _os.path.join(BASE_DIR, path)
        if _os.path.isfile(full):
            return send_from_directory(BASE_DIR, path)
        return send_from_directory(BASE_DIR, "index.html")

    @app.errorhandler(404)
    def not_found_response(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "API endpoint not found"}), 404
        return error

    @app.errorhandler(500)
    def internal_error_response(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return error

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=application.config["SERVER_HOST"],
        port=application.config["SERVER_PORT"],
        use_reloader=False,
    )
