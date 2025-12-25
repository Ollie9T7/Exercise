import os
import random
from datetime import datetime
from flask import render_template, request, redirect, url_for, session, current_app

from . import exercise_bp
from .storage import ensure_data_files, load_json, save_json, append_workout_log
from .generate import generate_workout

# Import existing helpers from main app.py
# IMPORTANT: this assumes your main file is named app.py and module name is "app"
from basecamp_core import login_required, admin_required, log_action, BASE_DIR



WARMUP_CATEGORY_OPTIONS = ["cardio", "upper", "legs", "full-body", "mobility", "core", "mixed"]


def _paths():
    data_dir = ensure_data_files(BASE_DIR)
    exercises_path = os.path.join(data_dir, "exercises.json")
    warmups_path = os.path.join(data_dir, "warmups.json")
    log_path = os.path.join(data_dir, "workout_logs.jsonl")
    return exercises_path, warmups_path, log_path

def _get_logged_in_name():
    return session.get("name") or session.get("username") or "User"


def _normalize_warmup(warmup: dict):
    return {
        "name": warmup.get("name", "Warm-up"),
        "description": warmup.get("description", ""),
        "categories": warmup.get("categories") or ["full-body"],
    }


def _pick_warmup(warmups: list, focus: str):
    """Choose a warmup that best fits the focus, with sensible fallbacks."""
    normalized = [_normalize_warmup(w) for w in warmups]
    preferred = {focus, "full-body", "cardio", "mobility", "mixed"}
    matches = [w for w in normalized if preferred.intersection(set(w["categories"]))]
    if not matches:
        matches = normalized
    return random.choice(matches) if matches else _normalize_warmup({})


def _append_workout_log_entry(state: dict):
    """Persist a finished workout to the workout log file."""
    _, _, log_path = _paths()
    entry = {
        "user": state.get("user"),
        "difficulty": state.get("difficulty"),
        "focus": state.get("focus"),
        "started_at": state.get("started_at"),
        "ended_at": state.get("ended_at"),
        "warmup": {
            "name": state.get("warmup"),
            "description": state.get("warmup_description", ""),
            "categories": state.get("warmup_categories", []),
        },
        "steps": state.get("steps", []),
    }
    append_workout_log(log_path, entry)
    return entry

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

        exercises_path, warmups_path, _ = _paths()
        exercises = load_json(exercises_path, [])
        warmups = [_normalize_warmup(w) for w in load_json(warmups_path, [])]

        # Build lookup for descriptions in case existing data is missing them
        exercise_lookup = {e.get("name"): e for e in exercises}
        steps = generate_workout(exercises, difficulty, focus)
        for step in steps:
            if step.get("type") == "exercise" and not step.get("description"):
                data = exercise_lookup.get(step.get("name"), {})
                step["description"] = data.get("description", "")

        warmup_choice = _pick_warmup(warmups, focus)
        warmup_name = warmup_choice.get("name") or "Light movement"

        session["exercise_state"] = {
            "user": _get_logged_in_name(),
            "difficulty": difficulty,
            "focus": focus,
            "warmup": warmup_name,
            "warmup_description": warmup_choice.get("description", ""),
            "warmup_categories": warmup_choice.get("categories", []),
            "steps": steps,
            "index": 0,
            "skipped": [],
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "logged": False,
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
            status = "skipped"
        else:
            log_action(username, "exercise_step_continue", {"step": current_step})
            status = "completed"

        if current_step is not None:
            current_step["status"] = status
            current_step["acted_at"] = datetime.now().isoformat()

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

@exercise_bp.route("/complete", methods=["GET", "POST"])
@login_required
def complete():
    username = session.get("username")
    state = session.get("exercise_state")
    if not state:
        return redirect(url_for("exercise.setup"))

    if not state.get("ended_at"):
        state["ended_at"] = datetime.now().isoformat()

    if request.method == "POST":
        if not state.get("logged"):
            _append_workout_log_entry(state)
            state["logged"] = True
            log_action(username, "exercise_workout_logged", {
                "difficulty": state.get("difficulty"),
                "focus": state.get("focus"),
            })
        session["exercise_state"] = state
        return redirect(url_for("exercise.complete"))

    log_action(username, "exercise_complete", {
        "difficulty": state.get("difficulty"),
        "focus": state.get("focus"),
    })

    session["exercise_state"] = state
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
    exercises_path, _, _ = _paths()
    exercises = load_json(exercises_path, [])

    if request.method == "POST":
        # Add, update or delete
        if request.form.get("delete") == "1":
            name = request.form.get("name")
            exercises = [e for e in exercises if e.get("name") != name]
            save_json(exercises_path, exercises)
            log_action(username, "exercise_admin_exercise_deleted", {"name": name})
        elif request.form.get("update") == "1":
            original_name = request.form.get("original_name")
            name = (request.form.get("name") or "").strip()
            focus = (request.form.get("focus") or "mixed").strip().lower()
            allowed = request.form.getlist("difficulty_allowed")
            description = (request.form.get("description") or "").strip()

            for ex in exercises:
                if ex.get("name") == original_name:
                    ex["name"] = name or original_name
                    ex["focus"] = focus if focus in ("legs", "upper", "mixed") else "mixed"
                    ex["difficulty_allowed"] = [d for d in allowed if d in ("easy", "medium", "hard")] or ["easy", "medium", "hard"]
                    ex["description"] = description
                    break
            save_json(exercises_path, exercises)
            log_action(username, "exercise_admin_exercise_updated", {"name": name})
        else:
            name = (request.form.get("name") or "").strip()
            focus = (request.form.get("focus") or "mixed").strip().lower()
            allowed = request.form.getlist("difficulty_allowed")
            description = (request.form.get("description") or "").strip()

            if name:
                exercises.append({
                    "name": name,
                    "focus": focus if focus in ("legs", "upper", "mixed") else "mixed",
                    "difficulty_allowed": [d for d in allowed if d in ("easy", "medium", "hard")] or ["easy", "medium", "hard"],
                    "description": description,
                })
                save_json(exercises_path, exercises)
                log_action(username, "exercise_admin_exercise_added", {"name": name})

        return redirect(url_for("exercise.admin_exercises"))

    return render_template("exercise/admin_exercises.html", exercises=exercises)

@exercise_bp.route("/admin/warmups", methods=["GET", "POST"])
@admin_required
def admin_warmups():
    username = session.get("username")
    _, warmups_path, _ = _paths()
    warmups = [_normalize_warmup(w) for w in load_json(warmups_path, [])]

    if request.method == "POST":
        if request.form.get("delete") == "1":
            name = request.form.get("name")
            warmups = [w for w in warmups if w.get("name") != name]
            save_json(warmups_path, warmups)
            log_action(username, "exercise_admin_warmup_deleted", {"name": name})
        elif request.form.get("update") == "1":
            original_name = request.form.get("original_name")
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip()
            categories = request.form.getlist("categories") or ["full-body"]

            for w in warmups:
                if w.get("name") == original_name:
                    w["name"] = name or original_name
                    w["description"] = description
                    w["categories"] = categories
                    break
            save_json(warmups_path, warmups)
            log_action(username, "exercise_admin_warmup_updated", {"name": name})
        else:
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip()
            categories = request.form.getlist("categories") or ["full-body"]
            if name:
                warmups.append({"name": name, "description": description, "categories": categories})
                save_json(warmups_path, warmups)
                log_action(username, "exercise_admin_warmup_added", {"name": name})

        return redirect(url_for("exercise.admin_warmups"))

    return render_template("exercise/admin_warmups.html", warmups=warmups, warmup_categories=WARMUP_CATEGORY_OPTIONS)

