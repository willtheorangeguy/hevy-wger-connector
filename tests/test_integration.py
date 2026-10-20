from dataclasses import replace
import json
import os
from pathlib import Path
import httpx
import pytest
from hevy_wger.api import Wger
from hevy_wger.config import Config
from hevy_wger.engine import Engine
from hevy_wger.state import State

pytestmark = pytest.mark.integration


@pytest.fixture
def account_data():
    file = os.getenv("TEST_CREDENTIALS_FILE")
    if not file or not Path(file).is_file():
        pytest.skip("Use python test_harness.py to prepare dedicated wger test accounts")
    return json.loads(Path(file).read_text())


def configuration(tmp_path, account_data, index):
    return Config(os.environ["HEVY_BASE_URL"], "mock-hevy-key", os.environ["WGER_BASE_URL"],
                  account_data["accounts"][index]["token"], tmp_path)


def scenario(config, name):
    response = httpx.post(config.hevy_url + "/__scenario", headers={"api-key": config.hevy_key}, json={"scenario": name})
    response.raise_for_status()


def approve(state, account_data):
    for index, name in enumerate(["H_BENCH", "H_ROW", "H_ASSISTED", "H_PUSHUP"]):
        state.map(name, account_data["exercise_ids"][index])


def counts(api):
    return {route: len(list(api.items(route))) for route in ["routine", "workoutsession", "workoutlog"]}


def test_live_import_review_edits_deletes_conflicts_and_stats(tmp_path, account_data):
    config = configuration(tmp_path, account_data, 0)
    scenario(config, "base")
    state = State(tmp_path)
    engine = Engine(config, state)
    try:
        before = counts(engine.wger)
        with state.lock():
            preview = engine.preview()
        assert counts(engine.wger) == before
        assert any(p.get("missing_mappings") for p in preview)
        report = engine.sync()
        assert report["counts"]["blocked"] == 5
        assert counts(engine.wger) == before
        approve(state, account_data)
        report = engine.sync()
        assert report["counts"] == {"imported": 5, "skipped": 1}
        assert counts(engine.wger) == {"routine": 5, "workoutsession": 3, "workoutlog": 27}
        engine.sync(full=True)
        assert counts(engine.wger)["workoutlog"] == 27
        roots = [r for r in state.resources() if r["route"] == "routine"]
        for record in roots:
            remote = engine.wger.detail("routine", record["remote_id"])
            assert len(remote["name"]) <= 25
            if record["owner"].startswith("archive:"):
                grouped = engine.wger.request("GET", f"/api/v2/routine/{record['remote_id']}/logs/")
                stats = engine.wger.request("GET", f"/api/v2/routine/{record['remote_id']}/stats/")
                assert grouped and stats
        logs = list(engine.wger.items("workoutlog"))
        assert all(log["session"] and log["slot_entry"] and log["routine"] for log in logs)
        assert {float(log["weight"]) for log in logs if log["weight"] is not None} >= {50, 52.5, 55}
        session_record = state.resource("workout:workout-0/session")
        session = engine.wger.detail("workoutsession", session_record["remote_id"])
        assert "Fixture: preserve notes" in session["notes"] and "bodyweight_assisted_reps" in session["notes"]

        scenario(config, "edit")
        report = engine.sync()
        assert not report["counts"].get("failed"), report
        assert counts(engine.wger)["workoutlog"] == 26
        updated_log = state.resource("workout:workout-0/exercise/0/set/0/log")
        assert float(engine.wger.detail("workoutlog", updated_log["remote_id"])["weight"]) == 72.5
        # A locally edited destination must remain untouched in preserve mode.
        engine.wger.request("PATCH", f"/api/v2/workoutlog/{updated_log['remote_id']}/", {"weight": 77})
        report = engine.sync(full=True)
        assert report["counts"].get("conflict") == 1, report
        assert float(engine.wger.detail("workoutlog", updated_log["remote_id"])["weight"]) == 77

        scenario(config, "delete")
        report = engine.sync()
        assert report["counts"]["retained_deleted"] == 2
        assert counts(engine.wger)["workoutsession"] == 3
        engine.close()
        engine = Engine(replace(config, policy="mirror"), state)
        report = engine.sync()
        assert not report["counts"].get("failed"), report
        assert report["counts"].get("deleted") == 2, report
        assert counts(engine.wger)["workoutsession"] == 2
        assert counts(engine.wger)["workoutlog"] == 17
        assert float(engine.wger.detail("workoutlog", updated_log["remote_id"])["weight"]) == 72.5

        # Local children attached to an imported template cannot be cascaded away.
        template = state.resource("routine:routine-a/root")
        local_day = engine.wger.request("POST", "/api/v2/day/", {"routine": int(template["remote_id"]),
            "order": 99, "name": "Local day", "description": "Not owned by connector", "is_rest": True})
        from hevy_wger.writer import Conflict
        with pytest.raises(Conflict):
            engine.writer.remove(state.resources("routine:routine-a"))
        assert engine.wger.detail("day", local_day["id"])
    finally:
        engine.close()
        state.close()


class LostResponse(httpx.BaseTransport):
    def __init__(self, route):
        self.inner, self.route, self.raised = httpx.HTTPTransport(), route, False

    def handle_request(self, request):
        response = self.inner.handle_request(request)
        if request.method == "POST" and request.url.path == f"/api/v2/{self.route}/" and not self.raised:
            self.raised = True
            response.read()
            response.close()
            raise httpx.ReadTimeout("Simulated response lost after commit", request=request)
        return response

    def close(self):
        self.inner.close()


@pytest.mark.parametrize("route,index", [("workoutlog", 1), ("day", 2)])
def test_live_restart_after_committed_write(tmp_path, account_data, route, index):
    config = configuration(tmp_path, account_data, index)
    scenario(config, "base")
    state = State(tmp_path)
    approve(state, account_data)
    engine = Engine(config, state, wger=Wger(config, transport=LostResponse(route)))
    try:
        report = engine.sync()
        assert report["counts"].get("uncertain"), report
    finally:
        engine.close()
        state.close()
    # Reopen SQLite and all API clients, as a restarted Docker container would.
    state = State(tmp_path)
    engine = Engine(config, state)
    try:
        report = engine.sync()
        assert report["counts"] == {"imported": 5, "skipped": 1}, report
        assert counts(engine.wger) == {"routine": 5, "workoutsession": 3, "workoutlog": 27}
        assert not state.report()["uncertain_writes"]
    finally:
        engine.close()
        state.close()
