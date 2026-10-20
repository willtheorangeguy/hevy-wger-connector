# Validation — 2026-10-20

Environment: Windows host, Docker Desktop 4.72.0, Compose 5.1.3, Python 3.12.13
Linux containers, and the existing wger harness's pinned 2.8.0-dev.1 image.

## Automated checks

- 29 unit tests passed in the final unit run (`reports/unit.xml`).
- All three destination integration cases passed against a real wger instance and a deterministic
  mock of Hevy's documented public API. They cover the complete review/import/
  edit/delete lifecycle and simulated lost responses after committed UUID-log
  and integer-ID-day creates.
- The lifecycle imports two private templates, three monthly history archives,
  three sessions and 27 strength sets. Reconciliation keeps those counts stable.
  A source edit removes one set and updates a load; preserve mode retains two
  deleted source records, while mirror removes the appropriate template/session
  and leaves two sessions/17 sets.
- Checks include routine statistics/log endpoints, explicit session/slot linkage,
  local-edit conflicts, protection of local children, mapping holds, supersets,
  rep ranges, fractional kilogram precision, signed assistance metadata, moving
  pagination, failed-page checkpoints, rate limiting, account binding and locks.

The complete local runner (`python test_harness.py`) writes `reports/junit.xml`.
The latest local run passed **all 32 tests together** (29 unit tests and three
wger integration cases) in **223.62 seconds**, with zero failures, errors or
skipped tests. It used `http://mock-hevy:8080` with a dummy API key and the local
Docker wger harness at `http://host.docker.internal:8101`; the production `.env`
was not loaded. The separate unit-only report is `reports/unit.xml`.

## CLI and container checks

- Exercised `check`, `preview`, `mappings suggest`, `mappings set`, `mappings list`
  and `status` against mock Hevy and the real wger schema/catalog.
- Verified preview makes no destination writes.
- Built the production image with locked dependencies, validated Compose config,
  ran the packaged CLI entrypoint, and successfully created/read its state volume
  as the non-root production user.
- The wger harness repository has no tracked modifications. Test accounts are
  created separately and removed after the integration runner; the demo user is
  preserved. Production `.env` contains no test account credentials.

## Limits of validation

No live Hevy account was accessed: no real Hevy API key was supplied. Live account
validation and continuous polling against Hevy remain deployment checks after
the user configures keys. The background scheduling loop and Docker health command
are included; the reported integration cases invoke the same sync engine directly.
Other wger releases have not been tested. Check required API compatibility before
using a different release.
