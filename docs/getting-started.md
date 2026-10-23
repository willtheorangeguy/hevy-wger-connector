# Getting started

## Prerequisites

Use Docker Desktop or Docker Engine with Linux containers and Compose v2. You need a Hevy Pro API key, a wger legacy Token API key, and a destination with the writable UUID/session APIs of wger `2.8.0-dev.1`. Check Docker with `docker compose version`.

## Install

The release container is published at
`ghcr.io/willtheorangeguy/hevy-wger-connector:0.1.0` for Linux amd64 and arm64.

You only need [docker-compose.yml](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/docker-compose.yml) and
[.env.example](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/.env.example), saved as `.env`, in an empty folder. No Python,
source checkout or local image build is required. Download both files from the
[v0.1.0 release](https://github.com/willtheorangeguy/hevy-wger-connector/releases/tag/v0.1.0).
The release download is named `env.example`; rename it to `.env`.
Fill in `HEVY_API_KEY`, `WGER_BASE_URL` and `WGER_TOKEN`
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

## First run

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
login is **`demo`** / **`HarnessDemo123!`** at `http://localhost:8101`.
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

## What just happened

The connector reviewed source history and mappings, bound both accounts, and imported supported strength data. `preview` cached source records with zero wger writes. The watcher now discovers new/changed records and reconciles managed destination data.

## Next steps

- Read [usage and policies](usage.md) before selecting mirror mode.
- Use [deployment](deployment.md) for an existing wger stack and backups.
- Follow [recovery](recovery.md) when a write outcome is unknown.
