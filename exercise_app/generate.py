import random

DIFF_RULES = {
    "easy":   {"count": 4, "rep_min": 6,  "rep_max": 10},
    "medium": {"count": 6, "rep_min": 8,  "rep_max": 14},
    "hard":   {"count": 8, "rep_min": 10, "rep_max": 20},
}


def generate_workout(exercises: list, difficulty: str, focus: str):
    rules = DIFF_RULES[difficulty]

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
        step = {
            "type": "exercise",
            "name": ex["name"],
            "reps": reps,
            "description": ex.get("description", ""),
            "status": None,
        }
        exercise_steps.append(step)

    # Insert breaks after every 2 exercises
    for i, step in enumerate(exercise_steps, start=1):
        steps.append(step)
        if i % 2 == 0 and i != len(exercise_steps):
            steps.append({"type": "break", "name": "Break", "detail": "60 seconds"})

    return steps
