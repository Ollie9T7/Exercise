import os
import json
from datetime import datetime
from functools import wraps

from flask import request, redirect, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs.jsonl")


def log_action(username, action, details=None):
    """Append a single log entry to logs.jsonl."""
    entry = {
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "username": username or "anonymous",
        "action": action,
        "ip": request.remote_addr,
        "path": request.path,
        "details": details or {},
        "user_agent": request.headers.get("User-Agent", ""),
    }

    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        # Don't break the app if logging fails
        pass


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)
    return wrapped_view

