# Hevy → wger connector

Import Hevy strength history and saved routines into wger through a separate Docker service. Review exercise mappings before writes, then run continuous synchronization with tracked ownership and interrupted-write recovery. The connector uses REST APIs without a wger plugin or database access.

## Key features

- Import saved templates and completed strength history as separate wger structures.
- Review mappings before initial and incremental imports.
- Choose preserved source deletions or managed mirror behavior.
- Reconcile local edits, unknown writes and historical changes through SQLite state.

## Quick start

Download the release Compose/environment pair and configure your Hevy Pro key and wger legacy token:

```sh
docker compose pull
docker compose run --rm connector check --json
docker compose run --rm connector preview --json
docker compose run --rm connector mappings suggest --json
```

Follow [getting started](getting-started.md) to approve actual exercise IDs before importing.

## Where to next

<div class="grid cards" markdown>

- [Installation](installation.md): released and source deployments.
- [Configuration](configuration.md): credentials, polling and policy defaults.
- [Usage](usage.md): fidelity, templates, history and deletion policy.
- [Recovery](recovery.md): backups, write intent and safe reconciliation.
- [Architecture](architecture.md): source snapshots, graph and writer.
- [Testing](testing.md): real-wger fixtures and mock Hevy isolation.

</div>

## Support

Open an [issue](https://github.com/willtheorangeguy/hevy-wger-connector/issues/new/choose).
