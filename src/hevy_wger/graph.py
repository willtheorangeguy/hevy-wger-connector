"""Pure source-to-destination planning; no network calls or writes."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import uuid

STRENGTH_TYPES = {"weight_reps", "reps_only", "bodyweight_reps", "bodyweight_assisted_reps"}
NAMESPACE = uuid.UUID("a5d1ed20-23af-4e2d-ad05-b1099fc5dcad")


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def stamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def number(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Source numeric field is invalid") from error
    if not result.is_finite() or result < 0 or result > 3000:
        raise ValueError("Strength values must be finite, nonnegative and at most 3000")
    return float(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def lifted_load(item, exercise_type):
    # Assistance is a separate source metric, never positive lifted load. Retain
    # its exact sign/value in notes and snapshots without sending it to wger.
    return None if exercise_type in {"reps_only", "bodyweight_assisted_reps"} else number(item.get("weight_kg"))


def ref(key):
    return {"$ref": key}


@dataclass
class Node:
    key: str
    owner: str
    route: str
    data: dict
    marker_field: str | None = None
    match_fields: tuple = ()
    uuid_id: bool = False

    def payload(self, identity, ids):
        def resolve(value):
            if isinstance(value, dict) and set(value) == {"$ref"}:
                return ids[value["$ref"]]
            return value
        data = {name: resolve(value) for name, value in self.data.items()}
        marker = "[HW:" + digest(identity + ":" + self.key)[:24] + "]"
        if self.marker_field:
            limit = {"description": 1000, "comment": 100}.get(self.marker_field)
            content = str(data.get(self.marker_field) or "")
            data[self.marker_field] = marker + "\n" + (content[:limit-len(marker)-1] if limit else content)
        if self.uuid_id:
            data["id"] = str(uuid.uuid5(NAMESPACE, identity + ":" + self.key))
        return data, marker


@dataclass
class Plan:
    nodes: list[Node] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    set_count: int = 0


def build(kind, source, templates, mappings, units):
    owner = f"{kind}:{source['id']}"
    result, supported = Plan(), []
    exercises = sorted(source.get("exercises", []), key=lambda e: e["index"])
    if len({exercise["index"] for exercise in exercises}) != len(exercises):
        raise ValueError("Duplicate source exercise index")
    for position, exercise in enumerate(exercises):
        template_id = str(exercise["exercise_template_id"])
        template = templates.get(template_id)
        if not template:
            result.missing.append(template_id)
            continue
        exercise_type = template.get("type")
        if exercise_type not in STRENGTH_TYPES:
            result.skipped.append({"exercise": exercise.get("title", template_id), "type": exercise_type})
            continue
        if template_id not in mappings:
            result.missing.append(template_id)
        sets = sorted(exercise.get("sets", []), key=lambda s: s["index"])
        seen = set()
        for item in sets:
            if item["index"] in seen:
                raise ValueError("Duplicate source set index")
            seen.add(item["index"])
            reps = number(item.get("reps"))
            load = lifted_load(item, exercise_type)
            if kind == "workout" and reps is None and load is None:
                raise ValueError("A strength set has neither reps nor a representable load")
            rep_range = item.get("rep_range") or {}
            low, high = number(rep_range.get("start")), number(rep_range.get("end"))
            if low is not None and high is not None and low > high:
                raise ValueError("Invalid prescribed repetition range")
        supported.append((position, exercise, exercise_type, sets))
    result.missing = sorted(set(result.missing))
    if result.missing or not any(item[3] for item in supported):
        return result

    def add(suffix, route, data, marker_field=None, match_fields=(), uuid_id=False, node_owner=owner):
        key = node_owner + "/" + suffix
        result.nodes.append(Node(key, node_owner, route, data, marker_field, match_fields, uuid_id))
        return key

    if kind == "routine":
        start = stamp(source.get("created_at") or "2000-01-01T00:00:00Z").date()
        root = add("root", "routine", {
            "name": ("Hevy " + source.get("title", "Routine"))[:17] + " " + digest(source["id"])[:7],
            "description": f"Hevy routine {source['id']}: {source.get('title', '')}",
            "start": str(start), "end": str(start+timedelta(days=28)),
            "is_template": True, "is_public": False, "fit_in_week": False}, "description")
        template_notes = [{"title": ex.get("title"), "notes": ex.get("notes"),
                           "rest_seconds": ex.get("rest_seconds"), "type": typ}
                          for _, ex, typ, _ in supported]
        day = add("day", "day", {"routine": ref(root), "order": 1, "name": "Hevy routine",
            "description": "Imported prescription; complete source retained in connector state.\n" + json.dumps(template_notes, ensure_ascii=False), "is_rest": False,
            "need_logs_to_advance": False, "type": "custom"}, "description")
        session = None
    else:
        start_time, end_time = stamp(source["start_time"]), stamp(source["end_time"])
        if end_time < start_time:
            raise ValueError("Workout end precedes its start")
        first = start_time.date().replace(day=1)
        last = (first.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
        group = str(source.get("routine_id") or "adhoc")
        archive_owner = f"archive:{group}:{first:%Y-%m}"
        root = add("root", "routine", {"name": f"Hevy {first:%Y-%m} {digest(group)[:8]}",
            "description": f"Hevy history, UTC month {first:%Y-%m}; source routine {group}. Historical archive, not a future schedule.",
            "start": str(first), "end": str(last), "is_template": False,
            "is_public": False, "fit_in_week": False}, "description", node_owner=archive_owner)
        order = start_time.day*100000 + start_time.hour*3600 + start_time.minute*60 + start_time.second
        day = add("day", "day", {"routine": ref(root), "order": order,
            "name": (f"{start_time:%m-%d} " + source.get("title", "Workout"))[:20],
            "description": f"Hevy workout {source['id']}: {source.get('title', '')}",
            "is_rest": False, "need_logs_to_advance": False, "type": "custom"}, "description")
        metadata = [{"index": pos, "title": ex.get("title"), "type": typ,
                     "notes": ex.get("notes"), "superset_id": ex.get("superset_id"), "sets": sets}
                    for pos, ex, typ, sets in supported]
        notes = (f"Hevy workout: {source.get('title', '')}\nSource ID: {source['id']}\n"
                 f"Source routine: {source.get('routine_id') or 'none'}\n{source.get('description') or ''}\n"
                 "Original strength sets (order, set type, RPE and assistance):\n" + json.dumps(metadata, ensure_ascii=False))
        session = add("session", "workoutsession", {"routine": ref(root), "day": ref(day),
            "datetime_start": iso(start_time), "datetime_end": iso(end_time), "notes": notes,
            "impression": "2"}, "notes", uuid_id=True)

    # One slot per set/round avoids averaging unequal prescriptions. Superset
    # members at the same set index share a slot and remain interleaved in wger.
    slots, members = {}, {}
    for position, exercise, exercise_type, sets in supported:
        for item in sets:
            set_index = item["index"]
            superset = exercise.get("superset_id")
            group = f"superset:{superset}:{set_index}" if superset is not None else f"exercise:{position}:{set_index}"
            if group not in slots:
                slots[group] = add("slot/"+group, "slot", {"day": ref(day), "order": len(slots)+1,
                    "comment": "Hevy set/round " + group}, "comment")
                members[group] = 0
            members[group] += 1
            prefix = f"exercise/{position}/set/{set_index}"
            load = lifted_load(item, exercise_type)
            reps = number(item.get("reps"))
            rep_range = item.get("rep_range") or {}
            target_reps = number(rep_range.get("start")) if rep_range.get("start") is not None else reps
            target_max = number(rep_range.get("end"))
            entry = add(prefix+"/entry", "slot-entry", {"slot": ref(slots[group]),
                "exercise": mappings[str(exercise["exercise_template_id"])], "order": members[group],
                "comment": f"Hevy {exercise.get('title', '')}, set {set_index}, type {item.get('type', 'normal')}",
                "type": {"warmup": "warmup", "dropset": "dropset"}.get(item.get("type"), "normal"),
                "repetition_unit": units["reps"], "weight_unit": units["kg"]}, "comment")
            values = [("sets-config", 1), ("repetitions-config", target_reps),
                      ("max-repetitions-config", target_max), ("weight-config", load),
                      ("rest-config", number(exercise.get("rest_seconds")))]
            for route, value in values:
                if value is not None:
                    add(prefix+"/"+route, route, {"slot_entry": ref(entry), "iteration": 1,
                        "value": value, "operation": "r", "step": "abs", "repeat": False},
                        match_fields=("slot_entry", "iteration"))
            if session:
                add(prefix+"/log", "workoutlog", {"date": iso(start_time), "session": ref(session),
                    "routine": ref(root), "slot_entry": ref(entry), "iteration": 1,
                    "exercise": mappings[str(exercise["exercise_template_id"])],
                    "repetitions_unit": units["reps"], "weight_unit": units["kg"],
                    "repetitions": reps, "weight": load}, uuid_id=True)
            result.set_count += 1
    return result
