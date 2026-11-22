# Command-line utility to safely create user accounts with hidden password input.
import argparse
import getpass
import sys
from pathlib import Path

# Ensure application package is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create a new user for XRay Report AI")
    parser.add_argument("--username", required=True, help="Unique username for the account")
    parser.add_argument("--role", default="doctor", choices=["doctor", "admin"], help="User role (doctor or admin)")

    args = parser.parse_args()
    username = args.username.strip()

    if not username:
        print("Error: Username cannot be blank.", file=sys.stderr)
        sys.exit(1)

    # Initialize tables if not already created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: User '{username}' already exists.", file=sys.stderr)
            sys.exit(1)

        password = getpass.getpass("Enter password: ")
        if not password or len(password) < 6:
            print("Error: Password must be at least 6 characters long.", file=sys.stderr)
            sys.exit(1)

        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

        pw_hash = hash_password(password)
        user = User(
            username=username,
            password_hash=pw_hash,
            role=args.role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Success: User '{username}' created with role '{args.role}' (ID: {user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
