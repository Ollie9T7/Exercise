import os
import random
import json
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, session, current_app

from . import exercise_bp
from .storage import (
    ensure_data_files,
    load_json,
    save_json,
    append_workout_log,
    load_difficulty_config,
    save_difficulty_config,
    load_settings,
    save_settings,
)
from .generate import generate_workout

# Import existing helpers from main app.py
# IMPORTANT: this assumes your main file is named app.py and module name is "app"
from basecamp_core import login_required, admin_required, log_action, BASE_DIR



WARMUP_CATEGORY_OPTIONS = ["cardio", "upper", "legs", "full-body", "mobility", "core", "stretch", "mixed"]


def _paths():
    data_dir = ensure_data_files(BASE_DIR)
    exercises_path = os.path.join(data_dir, "exercises.json")
    warmups_path = os.path.join(data_dir, "warmups.json")
    log_path = os.path.join(data_dir, "workout_logs.jsonl")
    config_path = os.path.join(data_dir, "settings.json")
    return exercises_path, warmups_path, log_path, config_path

def _get_logged_in_name():
    return session.get("name") or session.get("username") or "User"


def _normalize_warmup(warmup: dict):
    return {
        "name": warmup.get("name", "Warm-up"),
        "description": warmup.get("description", ""),
        "categories": warmup.get("categories") or ["full-body"],
        "duration_seconds": warmup.get("duration_seconds") or 60,
    }


def _select_warmups(warmups: list, focus: str):
    """
    Choose warmups ensuring at least one cardio and one mobility/stretch.
    """
    normalized = [_normalize_warmup(w) for w in warmups]
    cardio = [w for w in normalized if "cardio" in w["categories"]]
    stretch = [w for w in normalized if "mobility" in w["categories"] or "stretch" in w["categories"]]
    fallback = normalized or [_normalize_warmup({})]

    chosen = []
    if cardio:
        chosen.append(random.choice(cardio))
    if stretch:
        pick = random.choice(stretch)
        if pick not in chosen:
            chosen.append(pick)

    # if still empty, pick any two fallback
    if not chosen:
        chosen = random.sample(fallback, k=min(2, len(fallback)))

    return chosen


def _append_workout_log_entry(state: dict):
    """Persist a finished workout to the workout log file."""
    _, _, log_path, _ = _paths()
    entry = {
        "user": state.get("user"),
        "difficulty": state.get("difficulty"),
        "focus": state.get("focus"),
        "started_at": state.get("started_at"),
        "ended_at": state.get("ended_at"),
        "warmups": state.get("warmups", []),
        "steps": state.get("steps", []),
        "rating": state.get("rating"),
        "type": "guided",
    }
    append_workout_log(log_path, entry)
    return entry


def _format_timestamp(ts: str):
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d/%m/%y %H:%M")
    except Exception:
        return ts or "-"


def _calc_duration_minutes(start_iso: str, end_iso: str):
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        if end < start:
            return 0
        return int((end - start).total_seconds() // 60)
    except Exception:
        return 0

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

        exercises_path, warmups_path, _, config_path = _paths()
        exercises = load_json(exercises_path, [])
        warmups = [_normalize_warmup(w) for w in load_json(warmups_path, [])]
        settings = load_settings(config_path)
        difficulty_config = settings.get("difficulty_config", load_difficulty_config(config_path))

        # Build lookup for descriptions in case existing data is missing them
        exercise_lookup = {e.get("name"): e for e in exercises}
        steps = generate_workout(exercises, difficulty, focus, difficulty_config)
        for step in steps:
            if step.get("type") == "exercise" and not step.get("description"):
                data = exercise_lookup.get(step.get("name"), {})
                step["description"] = data.get("description", "")

        warmup_choices = _select_warmups(warmups, focus)

        session["exercise_state"] = {
            "user": _get_logged_in_name(),
            "difficulty": difficulty,
            "focus": focus,
            "warmups": warmup_choices,
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


@exercise_bp.route("/home", methods=["GET"])
@login_required
def home():
    username = session.get("username")
    log_action(username, "exercise_home_view")
    return render_template("exercise/home.html")

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

    warmups = state.get("warmups") or []
    log_action(username, "exercise_warmup_shown", {"warmups": [w.get("name") for w in warmups]})
    return render_template("exercise/warmup.html", state=state, warmups=warmups)

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
        rating = request.form.get("rating")
        try:
            rating_int = int(rating) if rating else None
            if rating_int and 1 <= rating_int <= 5:
                state["rating"] = rating_int
        except ValueError:
            pass

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
    return render_template(
        "exercise/complete.html",
        state=state,
        started_display=_format_timestamp(state.get("started_at")),
        ended_display=_format_timestamp(state.get("ended_at")),
        duration_minutes=_calc_duration_minutes(state.get("started_at"), state.get("ended_at")),
    )


@exercise_bp.route("/logs", methods=["GET"])
@login_required
def workout_logs():
    username = session.get("username")
    _, _, log_path, _ = _paths()
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        entry["started_display"] = _format_timestamp(entry.get("started_at"))
                        entry["ended_display"] = _format_timestamp(entry.get("ended_at"))
                        entry["duration_minutes"] = _calc_duration_minutes(entry.get("started_at"), entry.get("ended_at"))
                        entry["type"] = entry.get("type") or "guided"
                        entry["name"] = entry.get("name")
                        entry["notes"] = entry.get("notes")
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    logs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    log_action(username, "exercise_logs_view")
    return render_template("exercise/logs.html", logs=logs)


@exercise_bp.route("/progress", methods=["GET"])
@login_required
def progress():
    username = session.get("username")
    _, _, log_path, config_path = _paths()
    now = datetime.now()
    settings = load_settings(config_path)
    daily_target = settings.get("daily_target", 15)

    counters = {
        "all": {"minutes": 0, "count": 0},
        "week": {"minutes": 0, "count": 0},
        "month": {"minutes": 0, "count": 0},
        "year": {"minutes": 0, "count": 0},
    }

    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        start_iso = entry.get("started_at")
                        end_iso = entry.get("ended_at")
                        duration = _calc_duration_minutes(start_iso, end_iso)
                        if duration <= 0:
                            continue
                        start_dt = datetime.fromisoformat(start_iso)
                        counters["all"]["minutes"] += duration
                        counters["all"]["count"] += 1
                        if start_dt.isocalendar()[1] == now.isocalendar()[1] and start_dt.year == now.year:
                            counters["week"]["minutes"] += duration
                            counters["week"]["count"] += 1
                        if start_dt.month == now.month and start_dt.year == now.year:
                            counters["month"]["minutes"] += duration
                            counters["month"]["count"] += 1
                        if start_dt.year == now.year:
                            counters["year"]["minutes"] += duration
                            counters["year"]["count"] += 1
                    except Exception:
                        continue
        except OSError:
            pass

    log_action(username, "exercise_progress_view")
    # Build a 7-day streak/goal view
    past_days = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_key = day.strftime("%Y-%m-%d")
        minutes = 0
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        start_iso = entry.get("started_at")
                        end_iso = entry.get("ended_at")
                        if not start_iso or not end_iso:
                            continue
                        entry_day = start_iso.split("T")[0]
                        if entry_day == day_key:
                            minutes += _calc_duration_minutes(start_iso, end_iso)
            except Exception:
                pass
        past_days.append({
            "label": day.strftime("%a"),
            "minutes": minutes,
            "target": daily_target,
            "over": minutes - daily_target,
            "date_label": day.strftime("%d/%m"),
        })

    return render_template("exercise/progress.html", counters=counters, past_days=past_days, daily_target=daily_target)


@exercise_bp.route("/manual-log", methods=["GET", "POST"])
@login_required
def manual_log():
    username = session.get("username")
    exercises_path, warmups_path, log_path, config_path = _paths()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        started = request.form.get("started_at")
        ended = request.form.get("ended_at")
        notes = (request.form.get("notes") or "").strip()

        try:
            start_dt = datetime.fromisoformat(started)
            end_dt = datetime.fromisoformat(ended)
            if end_dt < start_dt:
                end_dt = start_dt
        except Exception:
            start_dt = datetime.now()
            end_dt = start_dt

        entry = {
            "user": session.get("name") or session.get("username"),
            "name": name or "Manual activity",
            "type": "manual",
            "started_at": start_dt.isoformat(),
            "ended_at": end_dt.isoformat(),
            "warmups": [],
            "steps": [],
            "rating": None,
            "notes": notes,
        }
        append_workout_log(log_path, entry)
        log_action(username, "exercise_manual_logged", {"name": name})
        return redirect(url_for("exercise.workout_logs"))

    return render_template("exercise/manual_log.html")

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
    exercises_path, _, _, config_path = _paths()
    exercises = load_json(exercises_path, [])
    settings = load_settings(config_path)
    difficulty_config = settings.get("difficulty_config") or load_difficulty_config(config_path)
    daily_target = settings.get("daily_target", 15)

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

    return render_template("exercise/admin_exercises.html", exercises=exercises, difficulty_config=difficulty_config, daily_target=daily_target)

@exercise_bp.route("/admin/warmups", methods=["GET", "POST"])
@admin_required
def admin_warmups():
    username = session.get("username")
    _, warmups_path, _, _ = _paths()
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
            duration = int(request.form.get("duration_seconds") or "60")

            for w in warmups:
                if w.get("name") == original_name:
                    w["name"] = name or original_name
                    w["description"] = description
                    w["categories"] = categories
                    w["duration_seconds"] = duration
                    break
            save_json(warmups_path, warmups)
            log_action(username, "exercise_admin_warmup_updated", {"name": name})
        else:
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip()
            categories = request.form.getlist("categories") or ["full-body"]
            duration = int(request.form.get("duration_seconds") or "60")
            if name:
                warmups.append({"name": name, "description": description, "categories": categories, "duration_seconds": duration})
                save_json(warmups_path, warmups)
                log_action(username, "exercise_admin_warmup_added", {"name": name})

        return redirect(url_for("exercise.admin_warmups"))

    return render_template("exercise/admin_warmups.html", warmups=warmups, warmup_categories=WARMUP_CATEGORY_OPTIONS)


@exercise_bp.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    username = session.get("username")
    _, _, _, config_path = _paths()
    settings = load_settings(config_path)
    config = settings.get("difficulty_config") or load_difficulty_config(config_path)

    for diff in ["easy", "medium", "hard"]:
        count = int(request.form.get(f"{diff}_count") or config[diff]["count"])
        rep_min = int(request.form.get(f"{diff}_rep_min") or config[diff]["rep_min"])
        rep_max = int(request.form.get(f"{diff}_rep_max") or config[diff]["rep_max"])
        if rep_max < rep_min:
            rep_max = rep_min
        config[diff] = {"count": count, "rep_min": rep_min, "rep_max": rep_max}

    daily_target = int(request.form.get("daily_target") or settings.get("daily_target", 15))
    settings["difficulty_config"] = config
    settings["daily_target"] = daily_target

    save_settings(config_path, settings)
    log_action(username, "exercise_admin_settings_updated", {"config": config, "daily_target": daily_target})
    return redirect(url_for("exercise.admin_exercises"))
