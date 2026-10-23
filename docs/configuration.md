# Configuration

## Precedence

Explicit environment variables override code defaults. Commands provide behavior flags, not environment-setting overrides. The CLI does not load a config file or `.env`. Standalone Compose passes `.env`; the existing-stack overlay translates `HEVY_`-prefixed variables to avoid collisions with wger settings.

## Process environment

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `HEVY_API_KEY` | string | empty | Hevy Pro API key; example `your-hevy-key`. |
| `HEVY_BASE_URL` | HTTP(S) URL | `https://api.hevyapp.com` | Source origin; a test example is `http://mock-hevy:8080`. |
| `WGER_BASE_URL` | HTTP(S) URL | empty | Destination origin without `/api/v2`; example `http://host.docker.internal:8101`. |
| `WGER_TOKEN` | string | empty | Legacy token alone; example `your-wger-token`. JWT refresh tokens are not accepted. |
| `DATA_DIR` | path | `./runtime` | Host CLI state directory; example `/data` in the container. |
| `SYNC_POLICY` | enum | `update_preserve_deleted` | `update_preserve_deleted` or `mirror`; example `update_preserve_deleted`. |
| `SYNC_INTERVAL_SECONDS` | integer | `900` | At least 30 seconds; example `900`. Watch adds 1–30 seconds jitter. |

Invalid policy or interval values fail configuration loading. Connection commands require both keys and HTTP(S) URLs without credentials, queries or fragments. `status` can inspect local state without API credentials.

## Compose interpolation

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `CONNECTOR_IMAGE` | image repository | `ghcr.io/willtheorangeguy/hevy-wger-connector` | No tag; example `ghcr.io/your-account/hevy-wger-connector`. |
| `CONNECTOR_VERSION` | string | `0.1.0` | Release without `v`; example `0.1.0`. |

The existing-stack overlay accepts `HEVY_CONNECTOR_IMAGE`, `HEVY_CONNECTOR_VERSION`, `HEVY_WGER_BASE_URL`, `HEVY_WGER_TOKEN`, `HEVY_SYNC_POLICY`, and `HEVY_SYNC_INTERVAL_SECONDS`. They map to the corresponding settings above. The destination URL defaults to `http://web:8000`; `HEVY_API_KEY` keeps its original name. Both examples mount state at `/data`. See [deployment](deployment.md).

## Examples

Copy the [tracked example](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/.env.example) and fill in your own keys:

```dotenv title=".env"
HEVY_API_KEY=
# Use your wger HTTPS URL, or this address for the local Docker harness.
WGER_BASE_URL=http://host.docker.internal:8101
WGER_TOKEN=
CONNECTOR_VERSION=0.1.0
SYNC_POLICY=update_preserve_deleted
SYNC_INTERVAL_SECONDS=900
DATA_DIR=/data
# Hevy API access requires Hevy Pro. Keep the public API URL unless testing.
HEVY_BASE_URL=https://api.hevyapp.com

```

Run `docker compose up -d` after editing `.env` to apply changes. Use one source/destination pair per state volume. A wger username change needs explicit state migration rather than a silent rebind.
