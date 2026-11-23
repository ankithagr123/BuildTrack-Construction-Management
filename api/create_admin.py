"""Create the first BuildTrack administrator interactively."""
from __future__ import annotations

import getpass
import re

from werkzeug.security import generate_password_hash

from config import Config
from database import db
from database.init_db import initialize_database


def main() -> None:
    path = Config.DATABASE_PATH
    initialize_database(path)
    name = input("Administrator name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass.getpass("Password (minimum 8 characters): ")
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Enter a name and valid email address.")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters.")
    with db.transaction(path) as connection:
        if connection.execute("SELECT 1 FROM auth_accounts LIMIT 1").fetchone():
            raise SystemExit("An account already exists. Sign in as an administrator to add users.")
        profile = connection.execute("SELECT id FROM user_profiles WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if profile:
            profile_id = profile["id"]
            connection.execute("UPDATE user_profiles SET name=?,role='Admin' WHERE id=?", (name, profile_id))
        else:
            cursor = connection.execute(
                "INSERT INTO user_profiles(name,role,email,avatar) VALUES(?,?,?,?)",
                (name, "Admin", email, ""),
            )
            profile_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO auth_accounts(profile_id,password_hash) VALUES(?,?)",
            (profile_id, generate_password_hash(password)),
        )
    print(f"Administrator account created for {email}.")


if __name__ == "__main__":
    main()
