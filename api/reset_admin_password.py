"""Safely reset an existing active BuildTrack administrator password locally."""
from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

from config import Config
from database import db


def reset_admin_password(database_path: str | Path, email: str, password: str, *, confirmed: bool) -> bool:
    """Reset a matching active admin's password; return False if not confirmed."""
    if not confirmed:
        return False
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("BuildTrack database does not exist; refusing to create a new database.")
    normalized_email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        raise ValueError("Enter a valid administrator email address.")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    with db.transaction(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        account = connection.execute(
            """SELECT p.id FROM user_profiles AS p
               JOIN auth_accounts AS a ON a.profile_id=p.id
               WHERE p.email=? COLLATE NOCASE
                 AND p.role='Admin' AND p.is_active=1""",
            (normalized_email,),
        ).fetchone()
        if account is None:
            raise LookupError("No active administrator login account matched that email.")
        cursor = connection.execute(
            "UPDATE auth_accounts SET password_hash=? WHERE profile_id=?",
            (generate_password_hash(password), account["id"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("The administrator password was not updated.")
    return True


def main() -> int:
    database_path = Path(Config.DATABASE_PATH).expanduser().resolve()
    if not database_path.is_file():
        print("BuildTrack database was not found; no database was created or changed.", file=sys.stderr)
        return 1
    email = input("Existing Admin email: ").strip()
    print("This will replace the password for the matching active Admin account.")
    if input('Type RESET to continue: ').strip() != "RESET":
        print("Reset cancelled. No data was changed.")
        return 1
    password = getpass.getpass("New password (minimum 8 characters): ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        print("Passwords did not match. No data was changed.", file=sys.stderr)
        return 1
    try:
        reset_admin_password(database_path, email, password, confirmed=True)
    except (FileNotFoundError, ValueError, LookupError, RuntimeError) as error:
        print(f"Password reset failed: {error}", file=sys.stderr)
        return 1
    print("Administrator password reset successfully. Existing accounts and project data were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
