# Deployment

Use [examples/docker-compose.wger.yml](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/examples/docker-compose.wger.yml) to add a
`hevy-connector` service to your existing stack. Either copy its **service and
volume** sections into your wger Compose file, or save it beside that file as
`docker-compose.hevy.yml`. Append the entries from
[examples/wger.env.example](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/examples/wger.env.example) to your existing wger
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

## Continuous operation

The default container command is `watch`. It syncs immediately and waits the configured interval plus 1–30 seconds of jitter. SIGINT/SIGTERM request graceful shutdown. Mapping holds and conflicts remain in `status` even when the scheduler/network health check succeeds.

```sh
docker compose logs -f connector
docker compose run --rm connector status --json
```

Commands share the writer lock. Retry maintenance once an active sync finishes, or stop the watcher first. Preserve the standalone or overlay state volume when changing deployments. See [recovery](recovery.md) for consistent backups and uncertain writes.
