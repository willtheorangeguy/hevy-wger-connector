# Installation

## Requirements

The released image supports Linux amd64 and arm64 under Docker with Compose v2. Python development requires 3.12 or later. Hevy access requires a Pro key; the destination must expose wger's compatible writable session/log UUID and routine APIs. `check` verifies schema and units before imports.

## Install methods

=== "Released container"

    Download `docker-compose.yml` and `env.example` from [v0.1.0](https://github.com/willtheorangeguy/hevy-wger-connector/releases/tag/v0.1.0), rename the environment file to `.env`, and supply credentials:

    ```sh
    docker compose pull
    docker compose run --rm connector --help
    ```

=== "Source container"

    ```sh
    git clone https://github.com/willtheorangeguy/hevy-wger-connector.git
    cd hevy-wger-connector
    cp .env.example .env
    docker compose -f compose.build.yaml build
    docker compose -f compose.build.yaml run --rm connector --help
    ```

    Use the same `-f compose.build.yaml` for later commands. It shares the published deployment's project and state volume; stop one before switching.

=== "Python development"

    ```sh
    python -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.lock
    pip install --no-deps -e .
    hevy-wger --help
    ```

    Export environment variables yourself. The Python CLI does not load `.env`. Its `DATA_DIR` default is `./runtime`; containers and the tracked example select `/data`.

## Verify the installation

`--help` prints the commands. After credentials are configured, `docker compose run --rm connector check --json` validates bindings, destination schema and units. Follow [getting started](getting-started.md) before the first write.

## Upgrading

Back up state and wger, update `CONNECTOR_VERSION`, then run `docker compose pull` and `docker compose up -d`. Retain the state volume containing managed-object ownership records.

## Uninstalling

`docker compose down` stops/removes containers and the project network without deleting state. Preserve the state backup together with wger's database. Losing state can duplicate integer-ID structures on a new import.
