# Usage

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

## Review a full reconciliation

```sh
docker compose run --rm connector sync --full --json
docker compose run --rm connector status --json
```

The default policy holds local edits as conflicts. `mirror` restores managed fields to Hevy values and deletes managed structures for deleted source objects, subject to cascade safety. Review [recovery](recovery.md) and retain backups before changing policy.
