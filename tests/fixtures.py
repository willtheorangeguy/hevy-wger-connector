"""Synthetic Hevy Public API shapes; no personal account data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone


def dataset(scenario="base"):
    templates = [
        {"id": "H_BENCH", "title": "Bench Press (Barbell)", "type": "weight_reps", "equipment": "barbell"},
        {"id": "H_ROW", "title": "Bent Over Row (Barbell)", "type": "weight_reps", "equipment": "barbell"},
        {"id": "H_ASSISTED", "title": "Assisted Pull Up", "type": "bodyweight_assisted_reps", "equipment": "machine"},
        {"id": "H_PUSHUP", "title": "Push Up", "type": "reps_only", "equipment": "none"},
        {"id": "H_CYCLE", "title": "Cycling", "type": "distance_duration", "equipment": "machine"},
        {"id": "H_PLANK", "title": "Plank", "type": "duration", "equipment": "none"},
    ]
    workouts = []
    for index, start in enumerate(["2026-09-30T22:30:00Z", "2026-09-30T23:30:00-04:00", "2026-10-20T17:00:00Z"]):
        exercises = []
        for order, template_id, weight in [(0, "H_BENCH", 50), (1, "H_ROW", 35), (2, "H_ASSISTED", 20)]:
            sets = [{"index": i, "type": "warmup" if i == 0 else "normal",
                     "weight_kg": weight+index*2.5+i*2.5, "reps": 8+i,
                     "rpe": 7+i*.5, "distance_meters": None, "duration_seconds": None}
                    for i in range(3)]
            exercises.append({"index": order, "title": templates[order]["title"], "notes": "Synthetic strength fixture",
                "exercise_template_id": template_id, "superset_id": 0 if order < 2 else None, "sets": sets})
        exercises.append({"index": 3, "title": "Cycling", "exercise_template_id": "H_CYCLE", "superset_id": None,
            "notes": "Must be reported, never imported as strength", "sets": [{"index": 0, "type": "normal",
            "weight_kg": None, "reps": None, "distance_meters": 3000, "duration_seconds": 600}]})
        begin = datetime.fromisoformat(start.replace("Z", "+00:00"))
        workouts.append({"id": f"workout-{index}", "title": f"Strength session {index+1}",
            "routine_id": "routine-a" if index < 2 else None,
            "description": "Fixture: preserve notes & Unicode \u2014 strength history",
            "start_time": start, "end_time": (begin+timedelta(minutes=50)).isoformat(),
            "created_at": start, "updated_at": start, "exercises": exercises})
    workouts.append({"id": "workout-cardio", "title": "Timed only", "routine_id": None,
        "description": None, "start_time": "2026-10-19T18:00:00Z", "end_time": "2026-10-19T18:05:00Z",
        "created_at": "2026-10-19T18:00:00Z", "updated_at": "2026-10-19T18:00:00Z",
        "exercises": [{"index": 0, "title": "Plank", "exercise_template_id": "H_PLANK", "superset_id": None,
                       "sets": [{"index": 0, "type": "normal", "duration_seconds": 60, "reps": None, "weight_kg": None}]}]})
    routines = []
    for index in range(2):
        exercises = deepcopy(workouts[0]["exercises"][:2])
        for exercise in exercises:
            exercise["rest_seconds"] = 90
            exercise["sets"][1]["rep_range"] = {"start": 8, "end": 12}
        routines.append({"id": f"routine-{'a' if index == 0 else 'b'}",
            "title": "Upper body \u2014 long original title retained in import metadata " + str(index),
            "folder_id": 1, "created_at": "2026-09-01T08:00:00Z", "updated_at": "2026-09-01T08:00:00Z",
            "exercises": exercises})
    if scenario in {"edit", "delete"}:
        workouts[0]["exercises"][0]["sets"] = workouts[0]["exercises"][0]["sets"][:2]
        workouts[0]["exercises"][0]["sets"][0]["weight_kg"] = 72.5
        workouts[0]["description"] = "Edited in Hevy"
        workouts[0]["updated_at"] = "2026-10-20T18:00:00Z"
        routines[0]["title"] = "Updated Hevy routine"
        routines[0]["updated_at"] = "2026-10-20T18:00:00Z"
    if scenario == "delete":
        workouts = [w for w in workouts if w["id"] != "workout-1"]
        routines = routines[:1]
    return {"templates": templates, "workouts": workouts, "routines": routines}
