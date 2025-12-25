import os
import json
from .defaults import DEFAULT_EXERCISES, DEFAULT_WARMUPS, DEFAULT_DIFFICULTY_CONFIG

DEFAULT_SETTINGS = {
    "difficulty_config": DEFAULT_DIFFICULTY_CONFIG,
    "daily_target": 15,
}


def ensure_data_files(base_dir: str) -> str:
    data_dir = os.path.join(base_dir, "exercise_app", "data")
    os.makedirs(data_dir, exist_ok=True)

    exercises_path = os.path.join(data_dir, "exercises.json")
    warmups_path = os.path.join(data_dir, "warmups.json")
    workout_log_path = os.path.join(data_dir, "workout_logs.jsonl")
    config_path = os.path.join(data_dir, "settings.json")

    if not os.path.exists(exercises_path):
        with open(exercises_path, "w") as f:
            json.dump(DEFAULT_EXERCISES, f, indent=2)

    if not os.path.exists(warmups_path):
        with open(warmups_path, "w") as f:
            json.dump(DEFAULT_WARMUPS, f, indent=2)

    if not os.path.exists(workout_log_path):
        # JSON Lines file makes it easy to append
        with open(workout_log_path, "w") as f:
            f.write("")

    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2)

    return data_dir


def load_json(path: str, fallback):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return fallback


def save_json(path: str, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def append_workout_log(path: str, entry: dict):
    """
    Append a single workout log entry to the JSONL file.
    """
    try:
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        # Don't crash the flow if logging fails
        pass


def load_difficulty_config(path: str):
    data = load_json(path, DEFAULT_SETTINGS)
    cfg = data.get("difficulty_config") or DEFAULT_DIFFICULTY_CONFIG
    # Ensure keys for each difficulty
    for diff, defaults in DEFAULT_DIFFICULTY_CONFIG.items():
        if diff not in cfg:
            cfg[diff] = defaults
        else:
            for key, val in defaults.items():
                if key not in cfg[diff]:
                    cfg[diff][key] = val
    return cfg


def save_difficulty_config(path: str, config: dict):
    current = load_json(path, DEFAULT_SETTINGS)
    current["difficulty_config"] = config
    save_json(path, current)


def load_settings(path: str):
    data = load_json(path, DEFAULT_SETTINGS)
    data.setdefault("difficulty_config", DEFAULT_DIFFICULTY_CONFIG)
    data.setdefault("daily_target", 15)
    return data


def save_settings(path: str, settings: dict):
    save_json(path, settings)
