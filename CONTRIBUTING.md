# Contributing

Use Python 3.12 or the supplied Docker test runner. For a local Python environment:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python -m pytest -q -m "not integration"
```

Run `python test_harness.py` for integration tests with the sibling
`wger-addon-harness` checkout and Docker running. These tests use a mock Hevy API
and isolated wger users. Never use real Hevy credentials or a production wger
destination in automated tests. See the README for fixtures and cleanup behavior.

Keep changes focused, include regression coverage when changing synchronization
behavior, and state the tests run in pull requests. Keep `.env`, tokens, workout
snapshots, runtime data and reports out of commits. Submit synthetic fixtures
when reporting import problems. Release instructions are in `RELEASING.md`.
