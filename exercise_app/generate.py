import random


def generate_workout(exercises: list, difficulty: str, focus: str, rules: dict):
    rules = rules[difficulty]

    # Filter by focus and allowed difficulty

    if focus == "mixed":
        pool = exercises[:]
    else:
        pool = [e for e in exercises if e.get("focus") in (focus, "mixed")]

    pool = [e for e in pool if difficulty in (e.get("difficulty_allowed") or [])]

    # If not enough, fall back to any difficulty match
    if len(pool) < rules["count"]:
        pool = [e for e in exercises if difficulty in (e.get("difficulty_allowed") or [])]

    random.shuffle(pool)
    chosen = pool[:rules["count"]]

    steps = []
    exercise_steps = []

    for idx, ex in enumerate(chosen, start=1):
        reps = random.randint(rules["rep_min"], rules["rep_max"])
        sets = random.randint(rules.get("set_min", 1), rules.get("set_max", 1))
        step = {
            "type": "exercise",
            "name": ex["name"],
            "reps": reps,
            "sets": sets,
            "description": ex.get("description", ""),
            "status": None,
            "timer_seconds": ex.get("timer_seconds"),
        }
        exercise_steps.append(step)

    # Insert breaks after every 2 exercises
    for i, step in enumerate(exercise_steps, start=1):
        steps.append(step)
        if i % 2 == 0 and i != len(exercise_steps):
            steps.append({"type": "break", "name": "Break", "detail": "60 seconds"})

    return steps
