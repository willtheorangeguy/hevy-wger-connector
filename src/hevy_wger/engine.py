from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import json
import time
from .api import Hevy, Wger, APIError, UnknownWrite
from .graph import build, digest, iso, stamp
from .state import encode
from .writer import Writer, Conflict


class Engine:
    def __init__(self, config, state, hevy=None, wger=None):
        self.config, self.state = config, state
        self.hevy, self.wger = hevy or Hevy(config), wger or Wger(config)

    def close(self):
        self.hevy.close()
        self.wger.close()

    def check(self):
        self.config.require_connections()
        info = self.hevy.request("GET", "/v1/user/info")
        info = info.get("data", info)
        if not info.get("id"):
            raise ValueError("Hevy did not return an account ID")
        profile = self.wger.request("GET", "/api/v2/userprofile/")
        if not profile.get("username"):
            raise ValueError("wger did not return an authenticated profile")
        identity = {"hevy_url": self.config.hevy_url, "hevy_user": str(info["id"]),
                    "wger_url": self.config.wger_url, "wger_user": profile["username"]}
        self.state.bind(identity)
        if not self.state.get("capabilities_checked"):
            schema = self.wger.request("GET", "/api/v2/schema?format=json")
            schemas = schema["components"]["schemas"]
            for name in ["WorkoutLog", "WorkoutSession"]:
                id_field = schemas[name]["properties"]["id"]
                if id_field.get("readOnly") or id_field.get("format") != "uuid":
                    raise ValueError("wger must support client-supplied session/log UUIDs")
            for field in ["datetime_start", "datetime_end", "day"]:
                if field not in schemas["WorkoutSession"]["properties"]:
                    raise ValueError("wger's workout session API is incompatible")
            self.state.set("capabilities_checked", True)
        self.units = self.wger.units()
        self.identity = digest(encode(identity))
        self.writer = Writer(self.state, self.wger, self.identity, self.config.policy)
        return {"identity": identity, "policy": self.config.policy, "units": self.units}

    def discover(self, full=False):
        started = datetime.now(timezone.utc)
        checkpoint = self.state.get("checkpoint")
        last_full = self.state.get("last_full")
        full = full or not checkpoint or not last_full or started-stamp(last_full) >= timedelta(days=1)
        templates = {str(item["id"]): item for item in self.hevy.pages("exercise_templates")}
        self.state.set("exercise_templates", templates)
        routine_ids = set()
        for item in self.hevy.pages("routines"):
            routine_ids.add(str(item["id"]))
            self.state.ingest("routine", item)
        # Absence is only authoritative after a complete, successful listing and
        # a confirming point read (pagination may move during a source edit).
        for source in self.state.sources():
            if source["kind"] == "routine" and not source["deleted"] and source["id"] not in routine_ids:
                current = self.hevy.request("GET", "/v1/routines/"+source["id"], allow_missing=True)
                if current is None:
                    self.state.deleted("routine", source["id"])
                else:
                    self.state.ingest("routine", unwrap(current, "routine"))
        if full:
            seen = set()
            for item in self.hevy.pages("workouts"):
                seen.add(str(item["id"]))
                self.state.ingest("workout", item)
            for source in self.state.sources():
                if source["kind"] == "workout" and not source["deleted"] and source["id"] not in seen:
                    current = self.hevy.request("GET", "/v1/workouts/"+source["id"], allow_missing=True)
                    if current is None:
                        self.state.deleted("workout", source["id"])
                    else:
                        self.state.ingest("workout", unwrap(current, "workout"))
        since = iso(stamp(checkpoint)-timedelta(minutes=5)) if checkpoint else iso(started)
        events = list(self.hevy.pages("workouts/events", since=since))
        changed = set()
        for event in events:
            source_id = str(event["id"] if event.get("type") == "deleted" else event["workout"]["id"])
            if source_id in changed:
                continue
            # Read the current version once, avoiding out-of-order overlap events
            # and edit/delete/recreate races during pagination.
            current = self.hevy.request("GET", "/v1/workouts/"+source_id, allow_missing=True)
            if current is None:
                self.state.deleted("workout", source_id)
            else:
                self.state.ingest("workout", unwrap(current, "workout"))
            changed.add(source_id)
        # Fetch templates omitted from the public list, including custom ones.
        for source in self.state.sources():
            if source["deleted"]:
                continue
            for exercise in json.loads(source["payload"]).get("exercises", []):
                key = str(exercise["exercise_template_id"])
                if key not in templates:
                    template = self.hevy.request("GET", "/v1/exercise_templates/"+key, allow_missing=True)
                    if template:
                        templates[key] = unwrap(template, "exercise_template")
        self.state.set("exercise_templates", templates)
        # Only advance after every fetched event and source snapshot is durable.
        self.state.set("checkpoint", iso(started))
        if full:
            self.state.set("last_full", iso(started))
        return full

    def mappings(self):
        return {row["hevy_id"]: row["wger_id"] for row in self.state.db.execute("SELECT * FROM mappings")}

    def preview(self):
        self.check()
        self.discover()
        return self.plans()

    def plans(self):
        output = []
        for source in self.state.sources():
            if source["deleted"]:
                output.append({"kind": source["kind"], "id": source["id"],
                               "action": "delete" if self.config.policy == "mirror" else "retain_deleted"})
                continue
            try:
                plan = build(source["kind"], json.loads(source["payload"]), self.state.get("exercise_templates", {}),
                             self.mappings(), self.units)
                output.append({"kind": source["kind"], "id": source["id"], "sets": plan.set_count,
                               "missing_mappings": plan.missing, "skipped_exercises": plan.skipped,
                               "action": "blocked" if plan.missing else "import" if plan.nodes else "skip"})
            except (ValueError, KeyError, TypeError) as error:
                output.append({"kind": source["kind"], "id": source["id"], "action": "invalid", "error": str(error)})
        return output

    def sync(self, full=False):
        with self.state.lock():
            self.state.set("last_attempt", iso(datetime.now(timezone.utc)))
            try:
                self.check()
                self.writer.reconcile()
                full = self.discover(full)
                mapping_hash = digest(encode(self.mappings()))
                catalog_hash = digest(encode(self.state.get("exercise_templates", {})))
                recheck = (full or mapping_hash != self.state.get("mapping_hash")
                           or catalog_hash != self.state.get("catalog_hash") or self.config.policy != self.state.get("last_policy"))
                validated = set()
                for source in self.state.sources():
                    kind, source_id = source["kind"], source["id"]
                    owner = kind+":"+source_id
                    if source["status"] in {"imported", "skipped"} and not recheck and not source["deleted"]:
                        continue
                    try:
                        if source["deleted"]:
                            if self.config.policy == "mirror":
                                self.writer.remove(self.state.resources(owner))
                                self.state.status(kind, source_id, "deleted")
                            else:
                                self.state.status(kind, source_id, "retained_deleted", "Deleted in Hevy; retained by policy")
                            continue
                        plan = build(kind, json.loads(source["payload"]), self.state.get("exercise_templates", {}), self.mappings(), self.units)
                        if plan.missing:
                            self.state.status(kind, source_id, "blocked", "Review exercise IDs: " + ", ".join(plan.missing))
                            continue
                        if not plan.nodes:
                            # A revision that no longer has any strength content
                            # must remove its old managed strength representation.
                            self.writer.remove(self.state.resources(owner))
                            self.state.status(kind, source_id, "skipped", "No supported strength sets")
                            continue
                        for exercise_id in {n.data["exercise"] for n in plan.nodes if n.route == "slot-entry"}:
                            if exercise_id not in validated:
                                if self.wger.detail("exercise", exercise_id) is None:
                                    raise ValueError("An approved wger exercise no longer exists")
                                validated.add(exercise_id)
                        self.writer.preflight({n.owner for n in plan.nodes})
                        ids = {}
                        for node in plan.nodes:
                            self.writer.upsert(node, ids)
                        desired = {node.key for node in plan.nodes}
                        self.writer.remove([r for r in self.state.resources(owner) if r["key"] not in desired])
                        message = "Skipped unsupported exercises: " + encode(plan.skipped) if plan.skipped else None
                        self.state.status(kind, source_id, "imported", message)
                    except (APIError, Conflict, ValueError, KeyError, TypeError) as error:
                        if isinstance(error, APIError) and error.status in {401, 403}:
                            raise
                        status = "conflict" if isinstance(error, Conflict) else "uncertain" if isinstance(error, UnknownWrite) else "failed"
                        self.state.status(kind, source_id, status, str(error))
                self.state.set("mapping_hash", mapping_hash)
                self.state.set("catalog_hash", catalog_hash)
                self.state.set("last_policy", self.config.policy)
                self.state.set("last_success", iso(datetime.now(timezone.utc)))
                self.state.set("last_error", None)
            except Exception as error:
                self.state.set("last_error", str(error))
                raise
            return self.state.report()

    def suggest(self):
        templates = self.state.get("exercise_templates", {})
        languages = list(self.wger.items("language"))
        english = next((language["id"] for language in languages if language.get("short_name") == "en"), None)
        exercises = list(self.wger.items("exerciseinfo", **({"language": english} if english else {})))
        output = []
        for key, template in templates.items():
            if template.get("type") not in {"weight_reps", "reps_only", "bodyweight_reps", "bodyweight_assisted_reps"}:
                continue
            if self.state.mapping(key):
                continue
            candidates = []
            name = normalize(template["title"])
            for exercise in exercises:
                translations = exercise.get("translations", [])
                names = [t["name"] for t in translations if t.get("language") == english] or [t["name"] for t in translations]
                if not names and exercise.get("name"):
                    names = [exercise["name"]]
                score = max((SequenceMatcher(None, name, normalize(n)).ratio() for n in names), default=0)
                equipment = normalize(template.get("equipment", ""))
                if equipment and any(equipment in normalize(item.get("name", "")) for item in exercise.get("equipment", [])):
                    score = min(1, score + .05)
                candidates.append({"id": exercise["id"], "name": names[0] if names else "", "score": round(score, 3)})
            output.append({"hevy_id": key, "title": template["title"],
                           "candidates": sorted(candidates, key=lambda c: (-c["score"], c["id"]))[:5]})
        return output


def normalize(value):
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in value).split())


def unwrap(value, key):
    if key in value:
        result = value[key]
        return result[0] if isinstance(result, list) else result
    return value
