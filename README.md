<!-- Logo -->
<h1 align="center">Hevy → wger connector</h1>
<!-- Tagline -->
<h4 align="center">Import Hevy strength history and saved routines into wger with reviewed mappings and durable recovery.</h4>
<!-- Badges -->
<div align="center">
<img alt="Issues" src="https://img.shields.io/github/issues/willtheorangeguy/hevy-wger-connector">
<img alt="Pull requests" src="https://img.shields.io/github/issues-pr/willtheorangeguy/hevy-wger-connector">
<img alt="License" src="https://img.shields.io/github/license/willtheorangeguy/hevy-wger-connector">
<img alt="docs-lint workflow" src="https://github.com/willtheorangeguy/hevy-wger-connector/actions/workflows/docs-lint.yml/badge.svg">
<img alt="docs workflow" src="https://github.com/willtheorangeguy/hevy-wger-connector/actions/workflows/docs.yml/badge.svg">
<img alt="publish workflow" src="https://github.com/willtheorangeguy/hevy-wger-connector/actions/workflows/publish.yml/badge.svg">
<img alt="test workflow" src="https://github.com/willtheorangeguy/hevy-wger-connector/actions/workflows/test.yml/badge.svg">
</div>
<!-- Nav -->
<p align="center"><a href="#key-features">Key Features</a> • <a href="#installation">Installation</a> • <a href="#usage">Usage</a> • <a href="#documentation">Documentation</a> • <a href="#support">Support</a> • <a href="#license">License</a></p>

## Key Features

- Import historical workouts and saved routine templates through REST APIs.
- Require approved exercise mappings before writing supported exercises.
- Run manual or periodic synchronization with full reconciliation.
- Choose preservation or managed mirror behavior for source deletions and edits.
- Resume interrupted imports through durable ownership and write-intent records.

## Installation

Download `docker-compose.yml` and `env.example` from [v0.1.0](https://github.com/willtheorangeguy/hevy-wger-connector/releases/tag/v0.1.0). Rename `env.example` to `.env`; set a Hevy Pro API key, wger URL and legacy token.

```sh
docker compose pull
docker compose run --rm connector check --json
docker compose run --rm connector preview --json
```

Requires Docker Compose v2 and the writable session APIs tested with wger `2.8.0-dev.1`. See [getting started](docs/getting-started.md).

## Usage

```sh
docker compose run --rm connector mappings suggest --json
docker compose run --rm connector mappings set HEVY_TEMPLATE_ID 123
docker compose run --rm connector sync --json
docker compose up -d
```

Replace the mapping arguments with reviewed source/target exercise IDs. Retain the state volume and back it up with wger. The default policy holds local edits and preserves source deletions. Mirror behavior and unknown-write recovery are described in the guides.

## Documentation

Read the [documentation site](https://williamvdg.me/hevy-wger-connector/) or browse [`docs/`](docs/index.md):
[Getting started](docs/getting-started.md) · [Installation](docs/installation.md) · [Usage](docs/usage.md) · [Configuration](docs/configuration.md) · [Troubleshooting](docs/troubleshooting.md).


## Support

Open an [issue](https://github.com/willtheorangeguy/hevy-wger-connector/issues/new/choose).

## Contributing

Contributions welcome. See the org-wide [Contributing Guide](https://github.com/willtheorangeguy/.github/blob/main/CONTRIBUTING.md) and [Code of Conduct](https://github.com/willtheorangeguy/.github/blob/main/CODE_OF_CONDUCT.md).

## License

MIT — see [`LICENSE`](LICENSE).
