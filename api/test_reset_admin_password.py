"""Safety tests for the local administrator password reset command."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from api.reset_admin_password import reset_admin_password
from database import db
from database.init_db import initialize_database


class AdminPasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.path = Path(self.temp.name) / "reset-test.sqlite3"
        initialize_database(self.path)
        with db.transaction(self.path) as connection:
            profile = connection.execute(
                "INSERT INTO user_profiles(name,role,email) VALUES(?,?,?)",
                ("Reset Test Admin", "Admin", "reset-admin@test.local"),
            )
            connection.execute(
                "INSERT INTO auth_accounts(profile_id,password_hash) VALUES(?,?)",
                (profile.lastrowid, generate_password_hash("old-password-123")),
            )
            connection.execute(
                "INSERT INTO projects(id,name,client,location,manager,start_date,expected_completion_date,budget,progress,status,description) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("kept-project", "Kept project", "Client", "Site", "Manager", "2026-01-01", "2027-01-01", 10000, 0, "ongoing", ""),
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_confirmation_and_password_replacement_preserve_records(self):
        self.assertFalse(reset_admin_password(self.path, "reset-admin@test.local", "new-password-123", confirmed=False))
        with db.transaction(self.path) as connection:
            row = connection.execute("SELECT password_hash FROM auth_accounts").fetchone()
            self.assertTrue(check_password_hash(row["password_hash"], "old-password-123"))

        self.assertTrue(reset_admin_password(self.path, "reset-admin@test.local", "new-password-123", confirmed=True))
        with db.transaction(self.path) as connection:
            row = connection.execute("SELECT password_hash FROM auth_accounts").fetchone()
            self.assertTrue(check_password_hash(row["password_hash"], "new-password-123"))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM projects WHERE id='kept-project'").fetchone()[0], 1)

    def test_only_matching_active_administrator_can_be_reset(self):
        with self.assertRaises(LookupError):
            reset_admin_password(self.path, "missing@test.local", "new-password-123", confirmed=True)
        with db.transaction(self.path) as connection:
            connection.execute("UPDATE user_profiles SET is_active=0")
        with self.assertRaises(LookupError):
            reset_admin_password(self.path, "reset-admin@test.local", "new-password-123", confirmed=True)


if __name__ == "__main__":
    unittest.main()
