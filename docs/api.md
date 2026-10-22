# API

The public interface is `hevy-wger`, also the container entry point. No web dashboard or HTTP server is exposed. Start with `hevy-wger --help`. Commands emit JSON; `--json` selects indented output. Exit 0 means completed, 1 means configuration/network/command failure, and 2 means a sync finished discovery with blocked, failed, conflicting or uncertain sources. Unsupported-only records are skipped without exit 2.

## `check`

Validate credentials, bindings, writable UUID/session schema and units.

```sh
docker compose run --rm connector check --json
```

## `preview`

Fetch/cache source records and return a plan with `destination_writes: 0`.

```sh
docker compose run --rm connector preview --json
```

## `sync`

Run a synchronization; optionally recheck all source history and managed fields.

| Flag or argument | Type | Default | Description |
| --- | --- | --- | --- |
| `--full` | flag | off | Reconcile all history and managed objects. |

```sh
docker compose run --rm connector sync --full --json
```

## `watch`

Run repeated syncs with graceful signal handling.

```sh
docker compose run --rm connector watch
```

## `status`

Read the local progress, conflicts, mappings and uncertain writes.

| Flag or argument | Type | Default | Description |
| --- | --- | --- | --- |
| `--health` | flag | off | Exit according to recent scheduler attempt and last error without printing the report. |

```sh
docker compose run --rm connector status --json
```

## `reconcile`

Read back uncertain writes and adopt a matching committed object.

| Flag or argument | Type | Default | Description |
| --- | --- | --- | --- |
| `--retry-uncommitted` | key | unset | Explicitly permit a held integer-ID write only after the original request cannot still execute. |

```sh
docker compose run --rm connector reconcile --json
```

## `mappings list`

List approved source-template to destination-exercise IDs.

```sh
docker compose run --rm connector mappings list --json
```

## `mappings suggest`

Discover catalogs and rank candidate matches without approving them.

```sh
docker compose run --rm connector mappings suggest --json
```

## `mappings set`

Approve/change a reviewed source mapping after checking the destination ID.

| Flag or argument | Type | Default | Description |
| --- | --- | --- | --- |
| `hevy_id` | string | required | Known Hevy template ID from preview. |
| `wger_id` | integer | required | Existing destination exercise ID; example 123. |

```sh
docker compose run --rm connector mappings set HEVY_TEMPLATE_ID 123
```

All command examples require configured credentials except local `status`. Replace `HEVY_TEMPLATE_ID` and `123` with reviewed IDs from your catalogs. For a recovery key, use the exact value from status; see [recovery](recovery.md) for `--retry-uncommitted`.

## External APIs

- [Hevy Public API](https://api.hevyapp.com/docs/): `api-key`, workout event feed,
  workouts/routines pages of at most 10, exercise-template pages of at most 100.
- [wger routines and workout history](https://wger.readthedocs.io/en/stable/api/routines.html)
- Local wger interactive schema: `http://localhost:8101/api/v2/schema/redoc/`

Live Hevy behavior still requires validation with your own key. The automated
Hevy service is a deterministic emulator of the documented API, paired with a
real wger instance for destination integration tests.

Hevy requests use `api-key`: `/v1/user/info`, workouts/events, paginated workouts/routines and exercise templates. wger uses `Authorization: Token` for profile/schema/units and GET/POST/PATCH/DELETE of managed routine graphs, sessions and logs. The connector never writes Hevy.

The `check` result identifies both accounts and validated units. `preview` wraps a plan and zero destination-write count; `sync` includes per-source results and summary counts. For fields and redaction behavior, see [the engine](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/src/hevy_wger/engine.py) and [CLI](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/src/hevy_wger/cli.py).
