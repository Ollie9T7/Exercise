DEFAULT_EXERCISES = [
    {
        "name": "Bodyweight Squats",
        "focus": "legs",
        "difficulty_allowed": ["easy", "medium", "hard"],
        "description": "Stand tall with feet shoulder-width apart. Push hips back as if sitting into a chair, keep chest lifted, knees tracking over toes, descend until thighs are parallel or comfortable depth, then drive through heels to stand.",
    },
    {
        "name": "Lunges",
        "focus": "legs",
        "difficulty_allowed": ["medium", "hard"],
        "description": "Step one foot forward, lower the back knee toward the floor while keeping torso upright, front knee over mid-foot. Light tap the ground, then press through the front heel to return.",
    },
    {
        "name": "Glute Bridges",
        "focus": "legs",
        "difficulty_allowed": ["easy", "medium", "hard"],
        "description": "Lie on your back, knees bent, heels close to glutes. Brace core, drive hips up by squeezing glutes, pause at the top without arching the back, then lower slowly.",
    },
    {
        "name": "Press-ups",
        "focus": "upper",
        "difficulty_allowed": ["easy", "medium", "hard"],
        "description": "Hands under shoulders, feet hip-width, body in a straight line. Lower chest toward the floor by bending elbows at 45°, lightly touch, then press back to plank without hips sagging.",
    },
    {
        "name": "Incline Press-ups",
        "focus": "upper",
        "difficulty_allowed": ["easy", "medium"],
        "description": "Hands on a sturdy bench/table, feet back to a straight line. Lower chest to the edge while bracing core, then press away, keeping elbows at ~45°.",
    },
    {
        "name": "Tricep Dips (Chair)",
        "focus": "upper",
        "difficulty_allowed": ["medium", "hard"],
        "description": "Hands on chair behind hips, fingers forward, legs extended or bent. Lower by bending elbows straight back, shoulders away from ears, then press up without locking elbows.",
    },
    {
        "name": "Mountain Climbers",
        "focus": "mixed",
        "difficulty_allowed": ["easy", "medium", "hard"],
        "description": "High plank with shoulders over wrists. Drive one knee toward chest, switch quickly like running in place while keeping hips level and core braced.",
    },
    {
        "name": "Burpees",
        "focus": "mixed",
        "difficulty_allowed": ["hard"],
        "description": "Squat to place hands on floor, jump feet back to plank, optional push-up, snap feet back under hips, then jump explosively with hands overhead.",
    },
    {
        "name": "Plank Shoulder Taps",
        "focus": "mixed",
        "difficulty_allowed": ["medium", "hard"],
        "description": "High plank, feet a bit wider than hips. Tap opposite shoulder with one hand while keeping hips square and glutes/core engaged. Alternate sides smoothly.",
    },
]

DEFAULT_WARMUPS = [
    {
        "name": "March on the spot",
        "description": "Stand tall and march, lifting knees to hip height, swinging arms naturally. Keep posture upright and breathe steadily.",
        "categories": ["cardio", "full-body"],
        "duration_seconds": 60,
    },
    {
        "name": "Arm circles",
        "description": "Extend arms to the sides at shoulder height. Make small circles forward for 20s, then reverse direction, gradually increasing circle size without shrugging shoulders.",
        "categories": ["upper", "mobility"],
        "duration_seconds": 40,
    },
    {
        "name": "Hip circles",
        "description": "Hands on hips, draw slow circles with the hips keeping feet planted. Move clockwise for 20s, then counterclockwise, keeping knees soft.",
        "categories": ["legs", "mobility"],
        "duration_seconds": 40,
    },
    {
        "name": "Dynamic hamstring reaches",
        "description": "Step one foot forward, hinge at hips with a flat back to reach toward toes, switch legs each rep, keeping a gentle stretch without bouncing.",
        "categories": ["legs", "mobility"],
        "duration_seconds": 40,
    },
    {
        "name": "Jumping jacks",
        "description": "Start tall with feet together. Jump feet wide while sweeping arms overhead, then return to start. Keep a steady rhythm and soft knees.",
        "categories": ["cardio", "full-body"],
        "duration_seconds": 45,
    },
    {
        "name": "Band pull-aparts",
        "description": "Hold a light band at shoulder height, arms straight. Pull the band apart by squeezing shoulder blades together, pause, then return with control.",
        "categories": ["upper", "mobility"],
        "duration_seconds": 45,
    },
]

DEFAULT_DIFFICULTY_CONFIG = {
    "easy": {"count": 4, "rep_min": 6, "rep_max": 10},
    "medium": {"count": 6, "rep_min": 8, "rep_max": 14},
    "hard": {"count": 8, "rep_min": 10, "rep_max": 20},
}

