# Hevy → wger connector

A separate Docker service that imports Hevy strength workout history and saved
routines into wger. It reads Hevy's official API and writes wger's REST API;
it does not require a wger plugin installation or database access.

Features include exercise mapping review, initial historical import, 15-minute
polling, manual synchronization, configurable deletion behavior, and durable
recovery after interrupted imports. No web dashboard is included.

Licensed under [MIT](LICENSE). See [release instructions](RELEASING.md) for
publishing the repository and its GHCR container.

## Quick start: two files

After the first GitHub release publishes successfully, the image is available at
`ghcr.io/willtheorangeguy/hevy-wger-connector:0.1.0` for Linux amd64 and arm64.
This repository is currently prepared for its first publication; the image does
not exist until that release workflow completes.

You only need [docker-compose.yml](docker-compose.yml) and
[.env.example](.env.example), saved as `.env`, in an empty folder. No Python,
source checkout or local image build is required. Both files will also be attached
to each GitHub release. Fill in `HEVY_API_KEY`, `WGER_BASE_URL` and `WGER_TOKEN`
in `.env` (see credential instructions below), then:

```powershell
docker compose pull
docker compose run --rm connector check --json
docker compose run --rm connector preview --json
docker compose run --rm connector mappings suggest --json
```

Approve the exercise mappings you have reviewed, import, and start polling:

```powershell
docker compose run --rm connector mappings set HEVY_TEMPLATE_ID WGER_EXERCISE_ID
docker compose run --rm connector sync --json
docker compose up -d
```

Repeat `mappings set` for each exercise that needs a mapping. `up -d` alone starts
the service, but importing an exercise requires an approved mapping first.
Set `CONNECTOR_VERSION` in `.env` to select a
specific release; it defaults to `0.1.0`. `CONNECTOR_IMAGE` overrides the registry
and repository. Stable releases also publish `0.1` and `latest` aliases;
prereleases publish only their exact version. Use a fixed version for repeatable
deployments.

The published and source-build Compose files use the same project and state
volume. Choose one file for your deployment; stop the service before switching
and retain its volume. For an upgrade, back up state and wger, update
`CONNECTOR_VERSION`, then run `docker compose pull` and `docker compose up -d`.

## Add to an existing wger Compose stack

Use [examples/docker-compose.wger.yml](examples/docker-compose.wger.yml) to add a
`hevy-connector` service to your existing stack. Either copy its **service and
volume** sections into your wger Compose file, or save it beside that file as
`docker-compose.hevy.yml`. Append the entries from
[examples/wger.env.example](examples/wger.env.example) to your existing wger
`.env` and fill in the API key and token. Keep your existing wger settings.

`HEVY_WGER_BASE_URL=http://web:8000` connects directly to a wger service called
`web` on its internal port 8000. Change it to match your actual service and
container port. The connector must share a Docker network with that service;
the example joins the default Compose network. If your wger service uses a custom
network, add that same `networks:` entry to `hevy-connector`. The example passes
only connector settings into its container and publishes no ports.

If you copied the sections into your existing Compose file:

```powershell
docker compose pull hevy-connector
docker compose run --rm --no-deps hevy-connector check --json
docker compose run --rm --no-deps hevy-connector preview --json
docker compose run --rm --no-deps hevy-connector mappings suggest --json
docker compose run --rm --no-deps hevy-connector mappings set HEVY_TEMPLATE_ID WGER_EXERCISE_ID
docker compose run --rm --no-deps hevy-connector sync --json
docker compose up -d --no-deps hevy-connector
```

Start wger first. Repeat `mappings set` for all required exercises. If you kept the
connector as a separate file, add
`-f docker-compose.yml -f docker-compose.hevy.yml` after `docker compose` in
each command; replace the first filename with your wger Compose filename.
This uses Compose's [standard file merging](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/).

The integration example uses `HEVY_` prefixes for its wger token, URL and sync
options to avoid colliding with wger's settings. Its `hevy_connector_state` volume
must be retained across upgrades. If you already ran a standalone connector,
stop it before switching and reuse/migrate its state volume; a fresh volume loses
the existing import ownership records. Use one active connector per account pair.

## Connect your accounts

Requires Docker Desktop/Linux containers, Docker Compose v2+, a Hevy Pro API key,
and a wger API token. The tested destination is the sibling harness's pinned
**wger 2.8.0-dev.1** image. Other servers must expose the same writable UUID and
session APIs; `check` validates the required schema before the first import.

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
HEVY_API_KEY=your-hevy-key
WGER_BASE_URL=http://host.docker.internal:8101
WGER_TOKEN=your-wger-token
SYNC_POLICY=update_preserve_deleted
SYNC_INTERVAL_SECONDS=900
```

Get the Hevy key from [Hevy Settings → Developer](https://hevy.com/settings?developer).
For wger, use its user settings/API key page to obtain a **legacy Token API key**.
`WGER_TOKEN` takes the token alone; the connector adds `Authorization: Token`.
JWT refresh tokens are a different credential and are not accepted by this version.

To use the local harness, start it with `python harness.py up` in its own folder,
then copy the `token` value from its ignored `runtime/credentials.json`. Its demo
login is **`demo`** / **`HarnessDemo123!`** at http://localhost:8101.
For a remote wger deployment, set its actual HTTPS base URL instead. Do not include
`/api/v2` in the base URL. `host.docker.internal` reaches the host from Docker;
inside a container `localhost` refers to that container.

```powershell
docker compose pull
docker compose run --rm connector check --json
docker compose run --rm connector preview --json
docker compose run --rm connector mappings suggest --json
```

`preview` fetches and caches source records, but performs **zero destination writes**.
Its output lists missing mappings and skipped exercise types. Suggestions are
candidates, never automatic approvals. Review the exercise names and equipment,
then approve each relevant Hevy exercise-template ID:

```powershell
docker compose run --rm connector mappings set HEVY_TEMPLATE_ID WGER_EXERCISE_ID
docker compose run --rm connector mappings list --json
docker compose run --rm connector sync --json
docker compose up -d
```

If no suitable wger exercise exists, create it in wger yourself first, then approve
its ID. Changing an approved mapping also updates that exercise in managed history.

The daemon syncs immediately, then approximately every 15 minutes with a small
random delay to avoid synchronized requests to Hevy. New unmatched exercises hold
the affected source routine/workout while the rest continue. Approve a mapping
and trigger `sync`, or wait for the next scheduled run.

## Commands and policies

| Command after `docker compose run --rm connector` | Behavior |
| --- | --- |
| `check` | Validate credentials, account binding, required schema and units |
| `preview --json` | Discover sources and describe imports without writing wger |
| `sync --json` | Run one sync and retry pending items |
| `sync --full --json` | Reconcile all history and verify managed destination fields |
| `watch` | Run continuously, with graceful SIGTERM shutdown |
| `status --json` | Show progress, conflicts, pending mappings and uncertain writes |
| `mappings list` | Show approved Hevy → wger exercise IDs |
| `mappings suggest` | Fetch the catalogs and rank possible matches |
| `mappings set HEVY_ID WGER_ID` | Approve or change a mapping after checking the target ID |
| `reconcile --json` | Read back uncertain writes and adopt confirmed results |

`docker compose logs -f connector` follows structured logs. `docker compose down`
stops the connector and retains state. Manual commands share its state volume and
acquire the same writer lock; if a sync is already running, retry after it finishes.

Set `SYNC_POLICY` in `.env`, then run `docker compose up -d` to apply a change:

| Policy | Hevy edits | Hevy deletions | Local changes to imported objects |
| --- | --- | --- | --- |
| `update_preserve_deleted` (default) | Update existing imports | Retain and report | Hold the source object as a conflict |
| `mirror` | Update existing imports | Delete its managed template/session/sets | Restore Hevy's managed field values |

Neither policy modifies native, unrelated wger objects. Deletion is refused when
it would cascade to records outside that deletion, including a local day or log
attached to an imported object. Deleting a Hevy routine removes its saved template
in mirror mode, while existing completed workouts remain independent history.
Empty monthly archives may remain after their final workout is deleted.

Normal incremental sync checks changed/pending records. A daily full reconciliation
also checks unchanged destination fields. `sync --full` performs that check now.
To resolve a local-edit conflict, restore the destination to its last imported
values, or choose `mirror` if you want Hevy to overwrite managed values.

Exit codes: **0** completed, **1** configuration/network/command error, **2** sync
finished discovering data but some sources need mappings, conflict review or retry.
Unsupported-only records are reported as skipped and do not cause exit code 2.
Docker health reflects scheduler/network progress; mapping and conflict counts
remain visible through `status`, even when the container is healthy.

## What appears in wger

- Each saved Hevy routine becomes a private reusable template. Wger display names
  are shortened to fit its limits and include stable suffixes; original titles
  and IDs remain in descriptions and source snapshots.
- Completed workouts become explicit sessions with their real start/end times,
  and individual logs linked to routine/day/slot entries. Monthly archive routines
  are grouped by source routine, with a separate group for ad-hoc workouts. This
  respects wger's 120-day routine limit and exposes history to its statistics API.
- Archive months use **UTC**, while wger displays timestamps in the user's zone.
  Archive day ordering is historical, not a calendar schedule for future training.
  Saved templates use a placeholder 28-day period, which can be copied into a
  future program; their structure is separate from historical prescriptions.
- Unequal sets retain their own reps and loads rather than averages. Superset
  members share slots by round. Warm-up/drop-set types map where wger supports
  them. Failure labels, RPE, exercise notes and original assistance values remain
  in structured session notes and complete local source snapshots.
- Loads are explicitly kilograms, rounded half-up to wger's two decimal places
  (including kilogram values Hevy converted from pounds); exact source values
  remain in notes/snapshots. Reps-only and assisted-rep exercises use no
  lifted load; assistance is **not** treated as positive weight lifted. Bodyweight
  movements retain additional load only, without inventing the user's body mass.
  Consequently wger volume for these movements is not total effective-body-mass
  volume. Actual set completion timestamps are not provided by Hevy, so logs use
  workout start time and preserve order through slot entries and source metadata.
- Cardio, timed holds and other duration/distance exercises are excluded and
  reported. A mixed workout imports its strength portion. A missing mapping for
  a supported exercise holds the whole source object before new writes begin.
  An unknown template is also held until its type can be determined.

Wger enforces its configured maximum session length (five hours in the tested
image). Longer Hevy sessions are reported as failed rather than shortened or
split silently; adjust the destination's setting if those sessions are intentional.

No nutrition, body measurements, automatic exercise creation, or writes back to
Hevy are included. The importer never creates a substitute exercise silently.

## State and recovery

SQLite is stored in Docker's `state` volume at `/data/state.sqlite3`. It includes
source snapshots, approved mappings, destination IDs, expected field values,
checkpoints, and write intentions. It is bound to the Hevy account ID, wger URL
and authenticated wger username. Changing an account or destination requires a
separate Compose project/state volume. A username change also requires explicit
state migration rather than silently rebinding another account.

Retain and back up the entire state volume, together with wger's database. Stop
the connector while backing up SQLite, or use SQLite's online backup mechanism;
copying only its main file while WAL writes are active is insufficient. Do not
delete the volume to resolve an error: losing it loses ownership information for
integer-ID objects and can cause duplicate structures on a new import.

The connector persists source records before advancing its event checkpoint,
uses an overlapping event window, and resumes pending imports independently of
that checkpoint. API writes span multiple requests, so partially imported
structures can be visible during an import or after a failure; the journal lets
the next run finish them. There is no cross-request wger transaction.

Sessions and logs have deterministic UUIDs. Other creates carry ownership markers
or parent/iteration keys. A timeout or 5xx on a write is treated as an unknown
outcome, not a failed transaction. Read-back reconciliation adopts a matching
committed object without another POST. If no matching integer-ID object can be
found, that write stays held. After verifying the original request cannot still
be running, explicitly authorize one unresolved key:

```powershell
docker compose run --rm connector reconcile --retry-uncommitted "KEY_FROM_STATUS" --json
docker compose run --rm connector sync --json
```

Do not authorize that retry while an earlier server request might still commit.
Changed recovered data or multiple matching objects require investigation rather
than automatic adoption. Neither API bodies nor authorization headers are logged.
State and session notes intentionally contain the user's workout data.

## Test with the existing wger harness

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

## API references

- [Hevy Public API](https://api.hevyapp.com/docs/): `api-key`, workout event feed,
  workouts/routines pages of at most 10, exercise-template pages of at most 100.
- [wger routines and workout history](https://wger.readthedocs.io/en/stable/api/routines.html)
- Local wger interactive schema: http://localhost:8101/api/v2/schema/redoc/

Live Hevy behavior still requires validation with your own key. The automated
Hevy service is a deterministic emulator of the documented API, paired with a
real wger instance for destination integration tests.
