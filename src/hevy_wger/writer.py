"""Journal remote writes and protect local edits and unmanaged descendants."""
import json
from decimal import Decimal, InvalidOperation
from .api import APIError, UnknownWrite
from .state import encode


class Conflict(RuntimeError):
    pass


def project(remote, fields):
    return {name: remote.get(name) for name in fields}


def equivalent(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if left == right:
        return True
    if left is None or right is None or isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except InvalidOperation:
        return False


class Writer:
    def __init__(self, state, api, identity, policy):
        self.state, self.api, self.identity, self.policy = state, api, identity, policy

    def inspect(self, record):
        if record["remote_id"]:
            return self.api.detail(record["route"], record["remote_id"])
        desired, match = json.loads(record["desired"]), json.loads(record["match_fields"])
        if "id" in desired:
            return self.api.detail(record["route"], desired["id"])
        matches = []
        for remote in self.api.items(record["route"], **match):
            if match and all(equivalent(remote.get(k), v) for k, v in match.items()):
                matches.append(remote)
            elif record["marker_field"] and record["marker"] in str(remote.get(record["marker_field"], "")):
                matches.append(remote)
        if len(matches) > 1:
            raise Conflict("Multiple destination objects match write intent " + record["key"])
        return matches[0] if matches else None

    def verify(self, record, remote):
        if remote is None:
            if self.policy == "mirror":
                return
            raise Conflict("A managed destination object was removed: " + record["key"])
        if record["expected"] and self.policy != "mirror":
            expected = json.loads(record["expected"])
            if not equivalent(project(remote, expected), expected):
                raise Conflict("Destination has local edits: " + record["key"])

    def preflight(self, owners):
        for owner in owners:
            for record in self.state.resources(owner):
                if record["remote_id"] and record["expected"]:
                    self.verify(record, self.api.detail(record["route"], record["remote_id"]))

    def upsert(self, node, ids):
        desired, marker = node.payload(self.identity, ids)
        match = {name: desired[name] for name in node.match_fields}
        record = self.state.resource(node.key)
        remote = self.inspect(record) if record else None
        if record and record["remote_id"]:
            self.verify(record, remote)
            if remote is None and self.policy == "mirror":
                self.state.save_resource(node.key, remote_id=None, expected=None, status="rejected")
                record = self.state.resource(node.key)
        if record and not record["remote_id"] and remote is None and record["status"] in {"intent", "unknown"} and not node.uuid_id:
            raise UnknownWrite("POST", "/api/v2/"+node.route+"/ (unresolved intent; use reconcile)")
        if remote and record and not record["remote_id"]:
            # A create committed before its response/state save. Verify ownership
            # and reconcile that exact intent before any later source revision.
            previous = json.loads(record["desired"])
            if not equivalent(project(remote, previous), previous):
                raise Conflict("Recovered object differs from its write intent: " + node.key)
        self.state.save_resource(node.key, owner=node.owner, route=node.route,
            desired=encode(desired), marker_field=node.marker_field, marker=marker,
            match_fields=encode(match), status="intent")
        if remote:
            old_fields = project(remote, desired)
            if not equivalent(old_fields, desired):
                # Persist both the old expectation and intended replacement.
                self.state.save_resource(node.key, remote_id=str(remote["id"]), expected=encode(old_fields))
                try:
                    remote = self.api.request("PATCH", f"/api/v2/{node.route}/{remote['id']}/", desired)
                except UnknownWrite:
                    self.state.save_resource(node.key, status="unknown")
                    raise
        else:
            try:
                remote = self.api.request("POST", f"/api/v2/{node.route}/", desired)
            except UnknownWrite:
                self.state.save_resource(node.key, status="unknown")
                raise
            except APIError as error:
                # A deterministic UUID create may have committed on an earlier
                # attempt; a duplicate-key response is reconciled by primary key.
                remote = self.api.detail(node.route, desired["id"]) if node.uuid_id and error.status == 400 else None
                if remote is None:
                    self.state.save_resource(node.key, status="rejected")
                    raise
                if not equivalent(project(remote, desired), desired):
                    raise Conflict("Existing deterministic UUID differs from this intent; restore connector state: " + node.key)
            if node.uuid_id and str(remote["id"]) != desired["id"]:
                raise Conflict("Destination ignored deterministic IDs; incompatible wger API")
        self.state.save_resource(node.key, remote_id=str(remote["id"]), expected=encode(project(remote, desired)), status="applied")
        ids[node.key] = remote["id"]

    def reconcile(self, retry_key=None):
        outcomes = []
        for record in self.state.resources():
            if record["status"] not in {"unknown", "intent"}:
                continue
            remote = self.inspect(record)
            desired = json.loads(record["desired"])
            if remote and equivalent(project(remote, desired), desired):
                self.state.save_resource(record["key"], remote_id=str(remote["id"]),
                    expected=encode(project(remote, desired)), status="applied")
                outcomes.append({"key": record["key"], "status": "recovered"})
            elif remote and record["expected"] and equivalent(project(remote, json.loads(record["expected"])), json.loads(record["expected"])):
                self.state.save_resource(record["key"], status="applied")
                outcomes.append({"key": record["key"], "status": "retry_update"})
            elif not remote and retry_key == record["key"]:
                self.state.save_resource(record["key"], status="rejected")
                outcomes.append({"key": record["key"], "status": "retry_authorized"})
            else:
                outcomes.append({"key": record["key"], "status": "unresolved"})
        return outcomes

    def protect_children(self, record, deleting):
        route, remote_id = record["route"], record["remote_id"]
        dependencies = {
            "routine": [("day", "routine"), ("workoutsession", "routine"), ("workoutlog", "routine")],
            "day": [("slot", "day"), ("workoutsession", "day")],
            "slot": [("slot-entry", "slot")],
            "slot-entry": [("workoutlog", "slot_entry"), *[(r, "slot_entry") for r in [
                "sets-config", "max-sets-config", "repetitions-config", "max-repetitions-config",
                "weight-config", "max-weight-config", "rest-config", "max-rest-config", "rir-config", "max-rir-config"]]],
            "workoutsession": [("workoutlog", "session")],
            "workoutlog": [("workoutlog", "next_log")],
        }
        for child_route, field in dependencies.get(route, []):
            for child in self.api.items(child_route, **{field: remote_id}):
                # Some endpoints ignore unknown filters: check the actual field.
                if str(child.get(field)) == str(remote_id) and (child_route, str(child["id"])) not in deleting:
                    raise Conflict("Destination data outside this deletion references " + record["key"])

    def remove(self, records):
        # Reverse dependency order: logs/configs before entries/slots/days/root.
        priority = {"workoutlog": 0, "workoutsession": 1, "slot-entry": 3, "slot": 4, "day": 5, "routine": 6}
        records = sorted(records, key=lambda r: priority.get(r["route"], 2))
        deleting = {(r["route"], r["remote_id"]) for r in records if r["remote_id"]}
        for record in records:
            if not record["remote_id"]:
                if record["status"] in {"intent", "unknown"}:
                    raise Conflict("Resolve uncertain writes before deleting " + record["key"])
                continue
            remote = self.api.detail(record["route"], record["remote_id"])
            if remote:
                self.verify(record, remote)
                self.protect_children(record, deleting)
        for record in records:
            if record["remote_id"]:
                try:
                    self.api.request("DELETE", f"/api/v2/{record['route']}/{record['remote_id']}/")
                except APIError as error:
                    if error.status != 404:
                        raise
            self.state.forget(record["key"])
