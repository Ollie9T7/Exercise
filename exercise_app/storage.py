import os
import json
from .defaults import DEFAULT_EXERCISES, DEFAULT_WARMUPS


def ensure_data_files(base_dir: str) -> str:
    data_dir = os.path.join(base_dir, "exercise_app", "data")
    os.makedirs(data_dir, exist_ok=True)

    exercises_path = os.path.join(data_dir, "exercises.json")
    warmups_path = os.path.join(data_dir, "warmups.json")
    workout_log_path = os.path.join(data_dir, "workout_logs.jsonl")

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


