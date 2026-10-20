# Validation — 2026-10-20

Environment: Windows host, Docker Desktop 4.72.0, Compose 5.1.3, Python 3.12.13
Linux containers, and the existing wger harness's pinned 2.8.0-dev.1 image.

## Automated checks

- 29 connector unit tests passed in the full harness run. Release preparation
  added ten version/tag checks; the subsequent unit-only run passed all **39**
  tests in **1.18 seconds** (`reports/unit.xml`), with three integration cases
  deselected.
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
The full local harness run passed **all 32 tests together** (29 unit tests and three
wger integration cases) in **223.62 seconds**, with zero failures, errors or
skipped tests. It used `http://mock-hevy:8080` with a dummy API key and the local
Docker wger harness at `http://host.docker.internal:8101`; the production `.env`
was not loaded. The separate unit-only report is `reports/unit.xml`.
The three integration cases were not repeated for the release workflow and
documentation changes; synchronization code did not change.

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
- Release preparation passed `actionlint 1.7.12` for both GitHub workflows and
  validated the published-image Compose file (now `docker-compose.yml`). The
  release metadata command accepted `v0.1.0`
  and generated the expected lowercase GHCR image path. The rebuilt packaged CLI
  starts successfully and runs with UID 10001.
- A local multi-platform Buildx build completed for **linux/amd64** and
  **linux/arm64**, including SBOM generation and maximum-mode provenance for
  both platforms. Its OCI archive is ignored at `reports/release-image.oci.tar`.
  Runtime CLI startup was checked on amd64; arm64 was built under emulation.
- The build backend minimum is setuptools 77, which supports the SPDX license
  expression added for MIT. The package wheel was rebuilt after that adjustment.

## Simplified deployment checks

- The default `docker-compose.yml` uses the published image and does not build.
  In an isolated folder containing only that file and `.env`, Compose resolved
  successfully and the packaged CLI started. The check used the locally built
  image in place of the not-yet-published GHCR image.
- The wger add-on file merged with the existing harness Compose file while
  retaining its project name. Its connector reached the real wger version API
  at `http://web:8000` over the shared Docker network (HTTP 200), running as UID
  10001. Only synthetic credential values were passed; this connectivity check
  made no workout writes or Hevy requests.
- Both standalone/source-build configurations and the add-on example passed
  Compose validation, and both workflows passed actionlint after adding release
  setup-file uploads. Temporary test containers and their newly created volumes
  were removed; the wger harness stayed running.

## Limits of validation

No live Hevy account was accessed: no real Hevy API key was supplied. Live account
validation and continuous polling against Hevy remain deployment checks after
the user configures keys. The background scheduling loop and Docker health command
are included; the reported integration cases invoke the same sync engine directly.
Other wger releases have not been tested. Check required API compatibility before
using a different release.

## GitHub publication checks (2026-10-20)

All three repositories are public on GitHub. Both harness integration workflows
passed. The connector's [hosted validation run](https://github.com/willtheorangeguy/hevy-wger-connector/actions/runs/39512185931)
passed unit tests, Compose validation, container startup and the complete mock
Hevy-to-wger suite. The integration runner joins the harness's Docker network
directly so it works with the loopback-only frontend on Linux as well as Docker
Desktop. Pytest was updated to 9.0.3 to resolve the reported temporary-directory
vulnerability; GitHub marks the alert fixed.

The [v0.1.0 release workflow](https://github.com/willtheorangeguy/hevy-wger-connector/actions/runs/39512905197)
passed, published amd64/arm64 images with attestations, and attached all four
setup files. An anonymous GHCR manifest request returned HTTP 200. The release
index digest is `sha256:b41aee536c13e1a410a1d0cec70aa4b38c24427481cb3661796619178003ef9b`.
