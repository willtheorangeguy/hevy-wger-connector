from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import httpx
import pytest
from hevy_wger.api import API, APIError, Hevy, UnknownWrite, Wger
from hevy_wger.config import Config
from hevy_wger.graph import build, Node, iso, stamp
from hevy_wger.state import State, encode
from hevy_wger.writer import Writer, Conflict
from fixtures import dataset


@pytest.fixture
def state(tmp_path):
    value = State(tmp_path)
    yield value
    value.close()


def config(tmp_path):
    return Config("https://hevy.test", "secret-hevy", "https://wger.test", "secret-wger", tmp_path)


def plan(kind="workout", index=0):
    data = dataset()
    return build(kind, data["workouts" if kind == "workout" else "routines"][index],
                 {x["id"]: x for x in data["templates"]},
                 {"H_BENCH": 1, "H_ROW": 2, "H_ASSISTED": 3}, {"kg": 1, "reps": 1})


def test_strength_mapping_keeps_sets_supersets_and_no_invented_assistance_load():
    result = plan()
    assert result.set_count == 9 and not result.missing
    assert [x["type"] for x in result.skipped] == ["distance_duration"]
    entries = [n for n in result.nodes if n.route == "slot-entry"]
    assert len(entries) == 9
    assert len([n for n in result.nodes if n.route == "slot"]) == 6
    logs = [n for n in result.nodes if n.route == "workoutlog"]
    assert [n.data["weight"] for n in logs[:3]] == [50, 52.5, 55]
    assert all(n.data["weight"] is None for n in logs[-3:])
    assert all(n.data["session"] and n.data["slot_entry"] for n in logs)
    assert "bodyweight_assisted_reps" in next(n for n in result.nodes if n.route == "workoutsession").data["notes"]


def test_template_ranges_and_long_names():
    result = plan("routine")
    root = result.nodes[0]
    assert root.data["is_template"] and not root.data["is_public"]
    assert len(root.data["name"]) <= 25
    assert len([n for n in result.nodes if n.route == "max-repetitions-config"]) == 2
    assert all(n.data["value"] == 90 for n in result.nodes if n.route == "rest-config")


def test_missing_mapping_blocks_whole_object_and_cardio_only_skips():
    data = dataset()
    result = build("workout", data["workouts"][0], {x["id"]: x for x in data["templates"]}, {}, {"kg": 1, "reps": 1})
    assert set(result.missing) == {"H_BENCH", "H_ROW", "H_ASSISTED"}
    assert result.nodes == []
    assert plan(index=3).nodes == []


def test_utc_month_boundary():
    result = plan(index=1)
    root = result.nodes[0]
    assert root.data["start"] == "2026-10-01" and root.data["end"] == "2026-10-31"
    session = next(n for n in result.nodes if n.route == "workoutsession")
    assert session.data["datetime_start"] == "2026-10-01T03:30:00Z"


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), 3001])
def test_bad_numeric_values_do_not_produce_a_partial_plan(bad):
    data = dataset()
    data["workouts"][0]["exercises"][0]["sets"][0]["weight_kg"] = bad
    with pytest.raises(ValueError):
        build("workout", data["workouts"][0], {x["id"]: x for x in data["templates"]}, {}, {"kg": 1, "reps": 1})


def test_read_retries_respect_retry_after_without_leaking_keys():
    calls, delays = [], []
    def handle(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3"}) if len(calls) == 1 else httpx.Response(200, json={"ok": True})
    api = API("https://example.test", {"api-key": "private"}, transport=httpx.MockTransport(handle), sleep=delays.append)
    assert api.request("GET", "/v1/workouts") == {"ok": True}
    assert delays == [3]
    with pytest.raises(ValueError):
        api.request("GET", "https://other.test/data")
    api.close()


def test_ambiguous_post_is_not_retried():
    calls = []
    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("private response", request=request)
    api = API("https://example.test", {"api-key": "private"}, transport=httpx.MockTransport(handle))
    with pytest.raises(UnknownWrite) as error:
        api.request("POST", "/things", {"secret": "private"})
    assert len(calls) == 1 and "private" not in str(error.value)
    api.close()


def test_hevy_paginates_events_and_uses_documented_page_limits(tmp_path):
    calls = []
    def handle(request):
        calls.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(200, json={"page": page, "page_count": 2, "events": [{"id": str(page)}]})
    api = Hevy(config(tmp_path), transport=httpx.MockTransport(handle))
    assert len(list(api.pages("workouts/events", since="2026-10-20T00:00:00Z"))) == 2
    assert all(c.url.params["pageSize"] == "10" for c in calls)
    assert calls[0].url.params["since"] == "2026-10-20T00:00:00Z"
    api.close()


def test_long_retry_after_does_not_retry_early():
    api = API("https://example.test", {}, transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"Retry-After": "600"})),
              sleep=lambda _: pytest.fail("Must return to scheduler instead of retrying early"))
    with pytest.raises(APIError):
        api.request("GET", "/test")
    api.close()


def test_account_binding_and_os_writer_lock(state, tmp_path):
    state.bind({"user": "a"})
    with pytest.raises(ValueError):
        state.bind({"user": "b"})
    other = State(tmp_path)
    with state.lock(), pytest.raises(RuntimeError):
        with other.lock():
            pass
    other.close()


class MemoryWger:
    def __init__(self):
        self.data, self.calls, self.fault = {}, [], None

    def detail(self, route, remote_id):
        return deepcopy(self.data.get((route, str(remote_id))))

    def items(self, route, **filters):
        return [deepcopy(value) for (r, _), value in self.data.items() if r == route]

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        parts = path.strip("/").split("/")
        route = parts[2]
        if method == "POST":
            remote_id = str(payload.get("id", len(self.data)+1))
            self.data[(route, remote_id)] = {**deepcopy(payload), "id": payload.get("id", int(remote_id) if remote_id.isdigit() else remote_id)}
            if self.fault == "after":
                self.fault = None
                raise UnknownWrite(method, path)
            return self.detail(route, remote_id)
        remote_id = parts[3]
        if method == "PATCH":
            self.data[(route, remote_id)].update(payload)
            if self.fault == "after":
                self.fault = None
                raise UnknownWrite(method, path)
            return self.detail(route, remote_id)
        if method == "DELETE":
            self.data.pop((route, remote_id), None)


def test_committed_create_recovers_after_response_loss(state):
    api = MemoryWger()
    writer = Writer(state, api, "identity", "update_preserve_deleted")
    node = Node("routine:1/root", "routine:1", "routine", {"name": "Example", "description": "Test"}, "description")
    api.fault = "after"
    with pytest.raises(UnknownWrite):
        writer.upsert(node, {})
    assert len(api.data) == 1
    assert writer.reconcile()[0]["status"] == "recovered"
    writer.upsert(node, {})
    assert len([c for c in api.calls if c[0] == "POST"]) == 1


def test_uncertain_uncommitted_create_requires_explicit_reconciliation(state):
    api = MemoryWger()
    writer = Writer(state, api, "identity", "mirror")
    node = Node("routine:1/root", "routine:1", "routine", {"name": "Example", "description": "Test"}, "description")
    desired, marker = node.payload("identity", {})
    state.save_resource(node.key, owner=node.owner, route=node.route, desired=encode(desired), status="unknown",
                        marker_field=node.marker_field, marker=marker)
    with pytest.raises(UnknownWrite):
        writer.upsert(node, {})
    assert api.calls == []
    writer.reconcile(retry_key=node.key)
    writer.upsert(node, {})
    assert len(api.data) == 1


def test_local_edit_conflicts_and_mirror_can_override(state):
    api = MemoryWger()
    node = Node("routine:1/root", "routine:1", "routine", {"name": "Hevy", "description": "Test"}, "description")
    writer = Writer(state, api, "identity", "update_preserve_deleted")
    writer.upsert(node, {})
    record = state.resource(node.key)
    api.data[("routine", record["remote_id"])]["name"] = "Local edit"
    with pytest.raises(Conflict):
        writer.upsert(node, {})
    Writer(state, api, "identity", "mirror").upsert(node, {})
    assert api.data[("routine", record["remote_id"])]["name"] == "Hevy"


def test_committed_update_recovers_after_response_loss(state):
    api = MemoryWger()
    writer = Writer(state, api, "identity", "update_preserve_deleted")
    node = Node("routine:1/root", "routine:1", "routine", {"name": "First", "description": "Test"}, "description")
    writer.upsert(node, {})
    node.data["name"] = "Second"
    api.fault = "after"
    with pytest.raises(UnknownWrite):
        writer.upsert(node, {})
    assert writer.reconcile()[0]["status"] == "recovered"
    writer.upsert(node, {})
    assert len([c for c in api.calls if c[0] == "PATCH"]) == 1


def test_delete_protects_unmanaged_children_even_in_mirror(state):
    api = MemoryWger()
    writer = Writer(state, api, "identity", "mirror")
    node = Node("routine:1/root", "routine:1", "routine", {"name": "Hevy", "description": "Test"}, "description")
    writer.upsert(node, {})
    record = state.resource(node.key)
    api.data[("day", "999")] = {"id": 999, "routine": int(record["remote_id"])}
    with pytest.raises(Conflict):
        writer.remove([record])
    assert api.detail("routine", record["remote_id"])


def test_mirror_restores_a_locally_deleted_managed_object(state):
    api = MemoryWger()
    writer = Writer(state, api, "identity", "mirror")
    node = Node("routine:1/root", "routine:1", "routine", {"name": "Hevy", "description": "Test"}, "description")
    writer.upsert(node, {})
    api.data.clear()
    writer.preflight({node.owner})
    writer.upsert(node, {})
    assert len(api.data) == 1


@pytest.mark.parametrize("status", [401, 403, 500, 502])
def test_write_error_does_not_repeat_post(status):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"private": "must not appear"})
    api = API("https://example.test", {}, transport=httpx.MockTransport(handle))
    with pytest.raises(APIError) as error:
        api.request("POST", "/resource", {"secret": "not logged"})
    assert len(calls) == 1
    assert "private" not in str(error.value) and "secret" not in str(error.value)
    api.close()


def test_reversed_session_times_are_rejected_before_planning_writes():
    data = dataset()
    source = data["workouts"][0]
    source["end_time"] = "2000-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="end precedes"):
        build("workout", source, {x["id"]: x for x in data["templates"]},
              {"H_BENCH": 1, "H_ROW": 2, "H_ASSISTED": 3}, {"kg": 1, "reps": 1})


def test_pounds_converted_load_precision_and_signed_assistance():
    data = dataset()
    source = data["workouts"][0]
    source["exercises"][0]["sets"][0]["weight_kg"] = 22.6796185
    source["exercises"][2]["sets"][0]["weight_kg"] = -20
    result = build("workout", source, {x["id"]: x for x in data["templates"]},
                   {"H_BENCH": 1, "H_ROW": 2, "H_ASSISTED": 3}, {"kg": 1, "reps": 1})
    logs = [n for n in result.nodes if n.route == "workoutlog"]
    assert logs[0].data["weight"] == 22.68
    assert logs[6].data["weight"] is None
    notes = next(n.data["notes"] for n in result.nodes if n.route == "workoutsession")
    assert "22.6796185" in notes and "-20" in notes


def test_config_repr_never_includes_api_keys(tmp_path):
    rendered = repr(config(tmp_path))
    assert "secret-hevy" not in rendered and "secret-wger" not in rendered


def test_source_index_not_response_array_order_controls_set_order():
    data = dataset()
    source = data["workouts"][0]
    source["exercises"].reverse()
    result = build("workout", source, {x["id"]: x for x in data["templates"]},
                   {"H_BENCH": 1, "H_ROW": 2, "H_ASSISTED": 3}, {"kg": 1, "reps": 1})
    assert next(n for n in result.nodes if n.route == "workoutlog").data["weight"] == 50


class MovingHevy:
    def __init__(self, fail_routines=False):
        self.data = dataset()
        self.fail_routines = fail_routines

    def pages(self, name, since=None):
        if name == "exercise_templates":
            yield from self.data["templates"]
        elif name == "routines":
            yield self.data["routines"][0]
            if self.fail_routines:
                raise APIError("GET", "/v1/routines", 503)
            yield self.data["routines"][1]
        elif name == "workouts":
            # Offset pagination moved while the list was fetched; one workout
            # is absent from the listing but present in the overlapping feed.
            yield self.data["workouts"][0]
            yield self.data["workouts"][2]
        elif name == "workouts/events":
            yield {"type": "updated", "workout": self.data["workouts"][1]}

    def request(self, method, path, **kwargs):
        return next((w for w in self.data["workouts"] if path.endswith(w["id"])), None)


def test_backfill_event_overlap_recovers_a_workout_missing_from_moving_pages(state, tmp_path):
    from hevy_wger.engine import Engine
    engine = Engine(config(tmp_path), state, hevy=MovingHevy(), wger=MemoryWger())
    engine.discover(full=True)
    assert {s["id"] for s in state.sources() if s["kind"] == "workout"} == {"workout-0", "workout-1", "workout-2"}
    assert state.get("checkpoint")


def test_failed_page_does_not_advance_checkpoint_or_infer_deletions(state, tmp_path):
    from hevy_wger.engine import Engine
    original = "2026-09-01T00:00:00Z"
    state.set("checkpoint", original)
    state.ingest("routine", dataset()["routines"][1])
    engine = Engine(config(tmp_path), state, hevy=MovingHevy(fail_routines=True), wger=MemoryWger())
    with pytest.raises(APIError):
        engine.discover(full=True)
    assert state.get("checkpoint") == original
    assert not next(s for s in state.sources() if s["id"] == "routine-b")["deleted"]
