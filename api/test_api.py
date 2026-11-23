"""HTTP integration checks against an isolated temporary SQLite database."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from api.app import create_app
from database import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "integration-test-only"
    DATABASE_PATH = ""
    SESSION_COOKIE_SECURE = False


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        TestConfig.DATABASE_PATH = str(Path(self.temp.name) / "api.sqlite3")
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with db.transaction(TestConfig.DATABASE_PATH) as connection:
            cur = connection.execute(
                "INSERT INTO user_profiles(name,role,email) VALUES(?,?,?)",
                ("Test Admin", "Admin", "admin@test.local"),
            )
            connection.execute(
                "INSERT INTO auth_accounts(profile_id,password_hash) VALUES(?,?)",
                (cur.lastrowid, generate_password_hash("test-password-123")),
            )

    def tearDown(self):
        self.temp.cleanup()

    def login(self):
        response = self.client.post("/api/auth/login", json={
            "email": "admin@test.local", "password": "test-password-123"
        })
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_auth_and_all_primary_crud_flows(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"BuildTrack", home.data)
        self.assertIn(b"js/app.js?v=auth-fix-1", home.data)
        home.close()
        auth_script = self.client.get("/js/app.js?v=auth-fix-1")
        self.assertEqual(auth_script.status_code, 200)
        self.assertIn(b"window.ApiService.auth.login(email, pass)", auth_script.data)
        self.assertNotIn(b"loginSuccess", auth_script.data)
        auth_script.close()
        worker = self.client.get("/service-worker.js")
        self.assertEqual(worker.status_code, 200)
        self.assertIn(b"buildtrack-shell-v13", worker.data)
        worker.close()
        script = self.client.get("/js/api.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn(b"ApiService", script.data)
        script.close()
        manifest = self.client.get("/manifest.json")
        self.assertEqual(manifest.status_code, 200)
        self.assertIn(b'"short_name": "BuildTrack"', manifest.data)
        manifest.close()
        offline = self.client.get("/offline.html")
        self.assertEqual(offline.status_code, 200)
        self.assertIn(b"You\xe2\x80\x99re offline", offline.data)
        offline.close()
        self.assertEqual(self.client.get("/api/projects").status_code, 401)
        self.login()

        project = self.client.post("/api/projects", json={
            "id": "project-test", "name": "Test Site", "client": "Client",
            "location": "Pune", "manager": "Engineer", "startDate": "2026-01-01",
            "expectedCompletionDate": "2027-01-01", "budget": 100000,
            "progress": 5, "status": "ongoing", "description": ""
        })
        self.assertEqual(project.status_code, 201, project.get_json())
        pid = project.get_json()["project"]["id"]

        task = self.client.post("/api/tasks", json={"id":"task-test", "projectId":pid,
            "title":"Foundation", "dueDate":"2026-12-31", "priority":"high", "status":"todo"})
        self.assertEqual(task.status_code, 201, task.get_json())
        self.assertEqual(self.client.patch("/api/tasks/task-test", json={"status":"completed"}).status_code, 200)

        worker = self.client.post("/api/workers", json={"id":"worker-test", "name":"Mason",
            "skill":"Head Mason", "dailyWage":500, "availability":"Available", "status":"active",
            "assignedProjectId":pid})
        self.assertEqual(worker.status_code, 201, worker.get_json())
        self.assertEqual(self.client.get("/api/workers/worker-test").status_code, 200)
        self.assertEqual(self.client.patch("/api/workers/worker-test", json={"dailyWage":550}).status_code, 200)
        self.assertEqual(self.client.post("/api/attendance", json={"date":"2026-11-23",
            "attendance":{"worker-test":"present"}}).status_code, 200)
        self.assertEqual(self.client.get("/api/attendance/records?date=2026-11-23").status_code, 200)
        self.assertEqual(self.client.get("/api/attendance/summary?date=2026-11-23").status_code, 200)
        self.assertEqual(self.client.post("/api/attendance", json={"date":"2026-11-23",
            "attendance":{"worker-test":"absent"}}).status_code, 200)
        half_day = self.client.post("/api/attendance", json={"date":"2026-11-23",
            "attendance":{"worker-test":"half-day"}})
        self.assertEqual(half_day.status_code, 200, half_day.get_json())
        self.assertEqual(self.client.get("/api/attendance/summary?date=2026-11-23").get_json()["half_day"], 1)

        material = self.client.post("/api/materials", json={"id":"mat-test", "name":"Cement",
            "category":"Cement & Aggregates", "unit":"bags", "quantity":10,
            "minStockLevel":2, "unitPrice":400})
        self.assertEqual(material.status_code, 201, material.get_json())
        self.assertEqual(self.client.post("/api/materials/mat-test/stock-in", json={"quantity":5}).status_code, 200)
        self.assertEqual(self.client.post("/api/materials/mat-test/stock-out", json={"quantity":3,
            "projectId":pid}).status_code, 200)
        self.assertEqual(self.client.post("/api/materials/mat-test/stock-out", json={"quantity":50}).status_code, 400)
        self.assertEqual(self.client.get("/api/materials/mat-test/transactions").status_code, 200)
        self.assertEqual(self.client.patch("/api/materials/mat-test", json={"unitPrice":410}).status_code, 200)

        expense = self.client.post("/api/expenses", json={"id":"expense-test", "title":"Cement",
            "projectId":pid, "category":"Materials", "amount":1000, "date":"2026-11-23",
            "paymentMethod":"UPI"})
        self.assertEqual(expense.status_code, 201, expense.get_json())
        self.assertEqual(self.client.patch("/api/expenses/expense-test", json={"amount":1100}).status_code, 200)
        self.assertEqual(self.client.get("/api/expenses/summary").status_code, 200)
        self.assertEqual(self.client.get("/api/expenses/chart-data").status_code, 200)
        payment = self.client.post("/api/payments", json={"id":"payment-test", "projectId":pid,
            "recipient":"Supplier", "amount":500, "date":"2026-11-23", "status":"Pending",
            "paymentMethod":"UPI"})
        self.assertEqual(payment.status_code, 201, payment.get_json())
        self.assertEqual(self.client.get("/api/payments/payment-test").status_code, 200)
        self.assertEqual(self.client.patch("/api/payments/payment-test", json={"amount":600}).status_code, 200)
        progress = self.client.post("/api/progress", json={"id":"dpr-test", "projectId":pid,
            "date":"2026-11-23", "workCompleted":"Foundation completed", "progressPercentage":20,
            "milestonesAchieved":"Footings signed off", "weatherConditions":"Clear"})
        self.assertEqual(progress.status_code, 201, progress.get_json())
        self.assertEqual(progress.get_json()["report"]["milestonesAchieved"], "Footings signed off")
        self.assertEqual(progress.get_json()["report"]["weatherConditions"], "Clear")
        self.assertEqual(self.client.get("/api/progress/dpr-test").status_code, 200)
        self.assertEqual(self.client.patch("/api/progress/dpr-test", json={"workCompleted":"Foundation and columns completed", "progressPercentage":20}).status_code, 200)
        self.assertEqual(self.client.get("/api/risks").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/stats").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/finance").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/risk").status_code, 200)
        self.assertEqual(self.client.patch("/api/settings", json={"companyName":"BuildTrack Test"}).status_code, 200)
        self.assertEqual(self.client.get("/api/projects/project-test").get_json()["project"]["progress"], 20)
        self.assertEqual(self.client.patch("/api/projects/project-test", json={"name":"Updated Site"}).status_code, 200)
        self.assertEqual(self.client.get("/api/projects/project-test").get_json()["project"]["name"], "Updated Site")
        self.assertEqual(self.client.delete("/api/projects/project-test").status_code, 409)
        self.assertEqual(self.client.delete("/api/expenses/expense-test").status_code, 204)
        self.assertEqual(self.client.delete("/api/payments/payment-test").status_code, 204)
        self.assertEqual(self.client.delete("/api/progress/dpr-test").status_code, 204)
        self.assertEqual(self.client.get("/api/projects/project-test").get_json()["project"]["progress"], 0)
        self.assertEqual(self.client.delete("/api/materials/mat-test").status_code, 204)
        self.assertEqual(self.client.delete("/api/workers/worker-test").status_code, 204)
        self.assertEqual(self.client.delete("/api/tasks/task-test").status_code, 204)

    def test_login_uses_password_hash_and_role_permissions(self):
        self.assertEqual(self.client.post("/api/auth/login", json={"email":"admin@test.local",
            "password":"wrong-password"}).status_code, 401)
        login_response = self.client.post("/api/auth/login", json={"email":"admin@test.local",
            "password":"test-password-123"})
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("session=", login_response.headers.get("Set-Cookie", ""))
        self.assertIn("no-store", login_response.headers.get("Cache-Control", ""))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        # Registration is limited to an authenticated administrator.
        response = self.client.post("/api/auth/register", json={"name":"Engineer",
            "email":"engineer@test.local", "password":"engineer-password", "role":"Site Engineer"})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={"email":"engineer@test.local",
            "password":"engineer-password"}).status_code, 200)
        self.assertEqual(self.client.post("/api/projects", json={}).status_code, 403)
        self.assertEqual(self.client.post("/api/tasks", json={}).status_code, 400)
        self.assertEqual(self.client.patch("/api/auth/me", json={"name":"Engineer Updated", "email":"engineer@test.local"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_admin_account_management_and_client_project_membership(self):
        self.login()
        project_ids = []
        for project_id in ("assigned-site", "private-site"):
            response = self.client.post("/api/projects", json={
                "id": project_id, "name": project_id, "client": "Owner", "location": "Pune",
                "manager": "Engineer", "startDate": "2026-01-01", "expectedCompletionDate": "2027-01-01",
                "budget": 100000, "progress": 0, "status": "ongoing"
            })
            self.assertEqual(response.status_code, 201, response.get_json())
            project_ids.append(project_id)
        created = self.client.post("/api/auth/register", json={
            "name": "Restricted Client", "email": "client@test.local", "password": "client-password",
            "role": "Client", "assignedProjectIds": [project_ids[0]]
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        client_id = created.get_json()["user"]["id"]
        self.assertEqual(self.client.get("/api/auth/users").status_code, 200)
        # Account editing accepts the current form payload and preserves hashed-password semantics.
        edited = self.client.patch(f"/api/auth/users/{client_id}", json={
            "name": "Client One", "email": "client@test.local", "role": "Client",
            "isActive": True, "assignedProjectIds": [project_ids[0]], "password": "updated-password"
        })
        self.assertEqual(edited.status_code, 200, edited.get_json())
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "email": "client@test.local", "password": "updated-password"
        }).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        visible = self.client.get("/api/projects").get_json()["projects"]
        self.assertEqual([project["id"] for project in visible], [project_ids[0]])
        self.assertNotIn("budget", visible[0])
        self.assertNotIn("spent", visible[0])
        self.assertEqual(self.client.get(f"/api/projects/{project_ids[1]}").status_code, 404)
        self.assertEqual(self.client.post("/api/projects", json={}).status_code, 403)
        self.assertEqual(self.client.get("/api/reports/finance").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/register", json={}).status_code, 403)
        self.client.post("/api/auth/logout")
        self.login()
        deactivated = self.client.patch(f"/api/auth/users/{client_id}", json={
            "name": "Client One", "email": "client@test.local", "role": "Client",
            "isActive": False, "assignedProjectIds": [project_ids[0]]
        })
        self.assertEqual(deactivated.status_code, 200, deactivated.get_json())
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "email": "client@test.local", "password": "updated-password"
        }).status_code, 401)

    def test_site_engineer_assignment_scopes_projects_tasks_and_writes(self):
        self.login()
        for project_id in ("engineer-assigned", "engineer-private"):
            response = self.client.post("/api/projects", json={
                "id": project_id, "name": project_id, "client": "Owner", "location": "Site",
                "manager": "Engineer", "startDate": "2026-01-01", "expectedCompletionDate": "2027-01-01",
                "budget": 100000, "progress": 0, "status": "ongoing"
            })
            self.assertEqual(response.status_code, 201, response.get_json())
        for task_id, project_id in (("assigned-task", "engineer-assigned"), ("private-task", "engineer-private")):
            response = self.client.post("/api/tasks", json={"id": task_id, "projectId": project_id,
                "title": "Foundation", "dueDate": "2026-12-31", "priority": "high", "status": "todo"})
            self.assertEqual(response.status_code, 201, response.get_json())
        account = self.client.post("/api/auth/register", json={
            "name": "Assigned Engineer", "email": "assigned-engineer@test.local", "password": "engineer-password",
            "role": "Site Engineer", "assignedProjectIds": ["engineer-assigned"]
        })
        self.assertEqual(account.status_code, 201, account.get_json())
        engineer_id = account.get_json()["user"]["id"]
        self.assertEqual(account.get_json()["user"]["assignedProjectIds"], ["engineer-assigned"])
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "email": "assigned-engineer@test.local", "password": "engineer-password"
        }).status_code, 200)
        engineer_projects = self.client.get("/api/projects").get_json()["projects"]
        self.assertEqual([p["id"] for p in engineer_projects], ["engineer-assigned"])
        self.assertNotIn("budget", engineer_projects[0])
        self.assertNotIn("spent", engineer_projects[0])
        self.assertEqual([t["id"] for t in self.client.get("/api/tasks").get_json()["tasks"]], ["assigned-task"])
        self.assertEqual(self.client.get("/api/tasks/private-task").status_code, 404)
        self.assertEqual(self.client.post("/api/tasks", json={"projectId":"engineer-private",
            "title":"Unauthorized", "dueDate":"2026-12-31", "priority":"high", "status":"todo"}).status_code, 404)
        self.assertEqual(self.client.get("/api/reports/finance").status_code, 403)
        self.assertEqual(self.client.post("/api/materials", json={}).status_code, 403)
        self.client.post("/api/auth/logout")
        self.login()
        self.assertEqual(self.client.patch(f"/api/auth/users/{engineer_id}", json={
            "name":"Assigned Engineer", "email":"assigned-engineer@test.local", "role":"Site Engineer",
            "isActive":True, "assignedProjectIds":["engineer-private"]
        }).status_code, 200)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "email":"assigned-engineer@test.local", "password":"engineer-password"
        }).status_code, 200)
        self.assertEqual([p["id"] for p in self.client.get("/api/projects").get_json()["projects"]], ["engineer-private"])

    def test_storekeeper_can_manage_inventory_but_not_unrelated_modules(self):
        self.login()
        account = self.client.post("/api/auth/register", json={
            "name": "Store Team", "email": "store@test.local", "password": "store-password",
            "role": "Storekeeper"
        })
        self.assertEqual(account.status_code, 201, account.get_json())
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "email": "store@test.local", "password": "store-password"
        }).status_code, 200)
        self.assertEqual(self.client.get("/api/materials").status_code, 200)
        self.assertEqual(self.client.get("/api/finance/summary").status_code, 403)
        self.assertEqual(self.client.get("/api/auth/users").status_code, 403)
        self.assertEqual(self.client.post("/api/projects", json={}).status_code, 403)
        created = self.client.post("/api/materials", json={"id":"store-material", "name":"Cement",
            "category":"Cement & Aggregates", "unit":"bag", "quantity":20, "minStockLevel":5, "unitPrice":400})
        self.assertEqual(created.status_code, 201, created.get_json())

    def test_admin_demo_data_is_confirmed_additive_and_duplicate_safe(self):
        self.login()
        self.assertFalse(self.client.get("/api/demo-data/status").get_json()["loaded"])
        existing = self.client.post("/api/projects", json={
            "id": "existing-kept", "name": "Keep Existing", "client": "Client", "location": "Site",
            "manager": "Manager", "startDate": "2026-01-01", "expectedCompletionDate": "2027-01-01",
            "budget": 100000, "progress": 0, "status": "ongoing"
        })
        self.assertEqual(existing.status_code, 201)
        unconfirmed = self.client.post("/api/demo-data", json={"confirm": False})
        self.assertEqual(unconfirmed.status_code, 400)
        loaded = self.client.post("/api/demo-data", json={"confirm": True})
        self.assertEqual(loaded.status_code, 201, loaded.get_json())
        self.assertEqual(loaded.get_json()["counts"], {
            "projects": 4, "workers": 12, "attendance": 60, "tasks": 12,
            "materials": 8, "stockTransactions": 16, "expenses": 16,
            "payments": 8, "progressReports": 8
        })
        self.assertTrue(self.client.get("/api/demo-data/status").get_json()["loaded"])
        self.assertEqual(self.client.get("/api/projects/existing-kept").status_code, 200)
        projects = self.client.get("/api/projects").get_json()["projects"]
        self.assertEqual(sum(project["id"].startswith("DEMO-") for project in projects), 4)
        finance = self.client.get("/api/expenses/summary?projectId=DEMO-COM-02").get_json()
        self.assertEqual(finance["spent"], 17_100_000)
        self.assertEqual(finance["remaining_budget"], 900_000)
        risk_types = {risk["type"] for risk in self.client.get("/api/risks?projectId=DEMO-COM-02").get_json()["risks"]}
        self.assertIn("high_expenditure", risk_types)
        self.assertIn("low_stock", risk_types)
        delayed_risks = self.client.get("/api/risks?projectId=DEMO-VIL-04").get_json()["risks"]
        self.assertIn("project_delay", {risk["type"] for risk in delayed_risks})
        duplicate = self.client.post("/api/demo-data", json={"confirm": True})
        self.assertEqual(duplicate.status_code, 409)
        # A later user-added child record blocks project removal instead of being deleted.
        extra_task = self.client.post("/api/tasks", json={
            "id": "user-task-on-demo", "projectId": "DEMO-APT-01", "title": "User follow-up",
            "dueDate": "2027-01-01", "priority": "low", "status": "todo"
        })
        self.assertEqual(extra_task.status_code, 201, extra_task.get_json())
        blocked = self.client.delete("/api/demo-data", json={"confirm": True})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.client.get("/api/projects/DEMO-APT-01").status_code, 200)
        self.assertEqual(self.client.get("/api/tasks/user-task-on-demo").status_code, 200)
        self.assertEqual(self.client.delete("/api/tasks/user-task-on-demo").status_code, 204)
        removed = self.client.delete("/api/demo-data", json={"confirm": True})
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertEqual(removed.get_json()["removed"]["projects"], 4)
        self.assertEqual(removed.get_json()["removed"]["removedRecords"], 144)
        self.assertEqual(self.client.get("/api/projects/existing-kept").status_code, 200)
        self.assertFalse(self.client.get("/api/demo-data/status").get_json()["loaded"])
        self.assertEqual(len(self.client.get("/api/projects").get_json()["projects"]), 1)


if __name__ == "__main__":
    unittest.main()
