#!/usr/bin/env python3
import os
import json
from getpass import getpass

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def main():
    users = load_users()

    username = input("New username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    if username in users:
        print(f"User '{username}' already exists.")
        return

    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        return

    if not password:
        print("Password cannot be empty.")
        return

    role = input("Role [user/admin] (default: user): ").strip().lower() or "user"
    if role not in ("user", "admin"):
        role = "user"

    users[username] = {
        "password_hash": generate_password_hash(password),
        "role": role,
    }

    save_users(users)
    print(f"User '{username}' added with role '{role}'.")


if __name__ == "__main__":
    main()



