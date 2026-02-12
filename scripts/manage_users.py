import sys
from pathlib import Path

from app import crud
from app.database import SessionLocal

# Add project root to sys.path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def list_users():
    db = get_db()
    users = crud.get_users(db)  # Need to create this function in crud.py
    if not users:
        print("No users found.")
        return

    print("--- Users ---")
    for user in users:
        print(f"ID: {user.id}, Email: {user.email}, Admin: {user.is_admin}")


def delete_user(user_id: int):
    db = get_db()
    success = crud.delete_user(db, user_id)  # Need to create this function in crud.py
    if success:
        print(f"User with ID {user_id} deleted successfully.")
    else:
        print(f"User with ID {user_id} not found.")


def set_admin_status(user_id: int, is_admin: bool):
    db = get_db()
    user = crud.update_user_admin_status(
        db, user_id, is_admin
    )  # Need to create this function in crud.py
    if user:
        print(f"User {user.email} (ID: {user_id}) admin status set to {is_admin}.")
    else:
        print(f"User with ID {user_id} not found.")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python manage_users.py [list|delete <user_id>|set_admin <user_id> <true/false>]"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        list_users()
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: python manage_users.py delete <user_id>")
            sys.exit(1)
        user_id = int(sys.argv[2])
        delete_user(user_id)
    elif command == "set_admin":
        if len(sys.argv) < 4:
            print("Usage: python manage_users.py set_admin <user_id> <true/false>")
            sys.exit(1)
        user_id = int(sys.argv[2])
        is_admin_str = sys.argv[3].lower()
        if is_admin_str == "true":
            is_admin = True
        elif is_admin_str == "false":
            is_admin = False
        else:
            print("Invalid value for is_admin. Use 'true' or 'false'.")
            sys.exit(1)
        set_admin_status(user_id, is_admin)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
