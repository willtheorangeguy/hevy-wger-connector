# Recovery

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
