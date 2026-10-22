# Troubleshooting

## Set HEVY_API_KEY and WGER_TOKEN

Use a Hevy Pro API key and wger legacy Token API key, not a JWT refresh token. Set base URLs without API path suffixes. From a container, localhost is the connector itself; use the host gateway or a shared Compose service name.

```sh
docker compose run --rm connector check --json
docker compose run --rm connector status --json
```

## Schema or session validation fails

The tested target is wger `2.8.0-dev.1`. It needs writable session/log UUID APIs and compatible units. Sessions above the destination's configured maximum (five hours in the tested image) fail rather than being split or shortened. Review intentional long sessions with the destination administrator.

## Sync exits 2

Read `status` and sync counts for mappings, conflicts, failed sources or uncertain writes. Review suggestions, approve actual existing target IDs and sync again. Unsupported-only records are skipped without exit 2.

## Local-edit conflict

With the default policy, restore imported managed fields to their last expected values. Select `mirror` only when Hevy should overwrite managed changes and delete its managed structures on source deletion. Full reconciliation checks unchanged destinations too.

## Write outcome is unknown

Do not delete state or automatically repeat the POST. Run read-back reconciliation. If an integer-ID result is absent, verify the earlier request cannot still commit before approving the exact retry key. See [recovery](recovery.md).

## State binding changed or manual command is locked

Restore the original account/URL/username or use a separate project and volume for another pair. Retry maintenance after the active writer finishes, or stop the watcher before running it. A fresh journal loses ownership information.
