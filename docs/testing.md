# Testing

No real Hevy account/key is needed for automated tests:

**Mock Hevy HTTP API → connector → local Docker wger harness → PostgreSQL.**
The destination is the actual wger application running as a sandbox, so integration
tests verify real API writes and stored workout data. `compose.test.yaml` supplies
a dummy Hevy key, points to the local mock server and harness, and does not load
the production `.env`.

```powershell
python test_harness.py
```

The runner starts the sibling `../wger-addon-harness`, creates three isolated
test users, runs a mock Hevy service and the containerized suite, then removes
only those users and the mock test stack. It leaves wger running and preserves
the demo account. Test setup uses Django to provision accounts; the connector
itself never accesses Django or PostgreSQL. Use `--keep-users` to inspect a test
run (its tokens are in ignored `runtime/test-credentials.json`), or
`--wger-harness PATH` when the harness checkout is elsewhere.

Reports are written to `reports/junit.xml`. Run just the unit suite with:

```powershell
docker compose -f compose.test.yaml build test
docker compose -f compose.test.yaml run --rm --no-deps test -q -m "not integration"
```

Fixtures cover pagination, progressive strength sets, varying prescriptions,
supersets, assisted reps, cardio exclusions, review holds, edits, deletions,
local conflicts, UTC month boundaries, and lost responses after real wger writes.
The production service stays unconfigured until you provide your account keys;
test credentials are never copied to `.env`.

GitHub Actions runs unit tests and a container startup check on pushes and pull
requests, and repeats them before release publishing. The optional manual
integration job requires a repository variable `WGER_HARNESS_REPOSITORY` naming
the accessible harness repository (and a read-only `WGER_HARNESS_TOKEN` secret if private). It runs
the same local integration runner. This repository does not assume the separate
local harness has already been published.
