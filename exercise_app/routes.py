import os
import random
from flask import render_template, request, redirect, url_for, session, current_app

from . import exercise_bp
from .storage import ensure_data_files, load_json, save_json
from .generate import generate_workout

# Import existing helpers from main app.py
# IMPORTANT: this assumes your main file is named app.py and module name is "app"
from app import login_required, admin_required, log_action, BASE_DIR

def _paths():
    data_dir = ensure_data_files(BASE_DIR)
    exercises_path = os.path.join(data_dir, "exercises.json")
    warmups_path = os.path.join(data_dir, "warmups.json")
    return exercises_path, warmups_path

def _get_logged_in_name():
    return session.get("name") or session.get("username") or "User"

@exercise_bp.route("/", methods=["GET", "POST"])
@login_required
def setup():
    username = session.get("username")
    log_action(username, "exercise_setup_view")

    if request.method == "POST":
        difficulty = request.form.get("difficulty", "easy").lower()
        focus = request.form.get("focus", "mixed").lower()

        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "easy"
        if focus not in ("legs", "upper", "mixed"):
            focus = "mixed"

        exercises_path, warmups_path = _paths()
        exercises = load_json(exercises_path, [])
        warmups = load_json(warmups_path, [])

        steps = generate_workout(exercises, difficulty, focus)

        warmup = random.choice(warmups)["name"] if warmups else "Light movement"

        session["exercise_state"] = {
            "user": _get_logged_in_name(),
            "difficulty": difficulty,
            "focus": focus,
            "warmup": warmup,
            "steps": steps,
            "index": 0,
            "skipped": [],
        }

        log_action(username, "exercise_setup_submit", {"difficulty": difficulty, "focus": focus})
        return redirect(url_for("exercise.warmup"))

    # GET
    return render_template("exercise/setup.html", user=_get_logged_in_name())

@exercise_bp.route("/warmup", methods=["GET", "POST"])
@login_required
def warmup():
    username = session.get("username")
    state = session.get("exercise_state")
    if not state:
        return redirect(url_for("exercise.setup"))

    if request.method == "POST":
        log_action(username, "exercise_warmup_next")
        return redirect(url_for("exercise.workout"))

    log_action(username, "exercise_warmup_shown", {"warmup": state.get("warmup")})
    return render_template("exercise/warmup.html", state=state)

@exercise_bp.route("/workout", methods=["GET", "POST"])
@login_required
def workout():
    username = session.get("username")
    state = session.get("exercise_state")
    if not state:
        return redirect(url_for("exercise.setup"))

    steps = state.get("steps", [])
    idx = int(state.get("index", 0))

    # finished?
    if idx >= len(steps):
        return redirect(url_for("exercise.complete"))

    if request.method == "POST":
        action = request.form.get("action")

        current_step = steps[idx] if idx < len(steps) else None

        if action == "skip":
            state.setdefault("skipped", []).append({"index": idx, "step": current_step})
            log_action(username, "exercise_step_skip", {"step": current_step})
        else:
            log_action(username, "exercise_step_continue", {"step": current_step})

        state["index"] = idx + 1
        session["exercise_state"] = state
        return redirect(url_for("exercise.workout"))

    current_step = steps[idx]
    return render_template(
        "exercise/workout.html",
        state=state,
        step=current_step,
        index=idx,
        total=len(steps),
    )

@exercise_bp.route("/complete", methods=["GET"])
@login_required
def complete():
    username = session.get("username")
    state = session.get("exercise_state")
    if not state:
        return redirect(url_for("exercise.setup"))

    log_action(username, "exercise_complete", {
        "difficulty": state.get("difficulty"),
        "focus": state.get("focus"),
    })

    return render_template("exercise/complete.html", state=state)

# ───────── Admin (re-uses your admin role system) ─────────

@exercise_bp.route("/admin", methods=["GET"])
@admin_required
def admin_home():
    username = session.get("username")
    log_action(username, "exercise_admin_view")
    return render_template("exercise/admin.html")

@exercise_bp.route("/admin/exercises", methods=["GET", "POST"])
@admin_required
def admin_exercises():
    username = session.get("username")
    exercises_path, _ = _paths()
    exercises = load_json(exercises_path, [])

    if request.method == "POST":
        # Add or delete
        if request.form.get("delete") == "1":
            name = request.form.get("name")
            exercises = [e for e in exercises if e.get("name") != name]
            save_json(exercises_path, exercises)
            log_action(username, "exercise_admin_exercise_deleted", {"name": name})
        else:
            name = (request.form.get("name") or "").strip()
            focus = (request.form.get("focus") or "mixed").strip().lower()
            allowed = request.form.getlist("difficulty_allowed")

            if name:
                exercises.append({
                    "name": name,
                    "focus": focus if focus in ("legs", "upper", "mixed") else "mixed",
                    "difficulty_allowed": [d for d in allowed if d in ("easy", "medium", "hard")] or ["easy", "medium", "hard"],
                })
                save_json(exercises_path, exercises)
                log_action(username, "exercise_admin_exercise_added", {"name": name})

        return redirect(url_for("exercise.admin_exercises"))

    return render_template("exercise/admin_exercises.html", exercises=exercises)

@exercise_bp.route("/admin/warmups", methods=["GET", "POST"])
@admin_required
def admin_warmups():
    username = session.get("username")
    _, warmups_path = _paths()
    warmups = load_json(warmups_path, [])

    if request.method == "POST":
        if request.form.get("delete") == "1":
            name = request.form.get("name")
            warmups = [w for w in warmups if w.get("name") != name]
            save_json(warmups_path, warmups)
            log_action(username, "exercise_admin_warmup_deleted", {"name": name})
        else:
            name = (request.form.get("name") or "").strip()
            if name:
                warmups.append({"name": name})
                save_json(warmups_path, warmups)
                log_action(username, "exercise_admin_warmup_added", {"name": name})

        return redirect(url_for("exercise.admin_warmups"))

    return render_template("exercise/admin_warmups.html", warmups=warmups)



