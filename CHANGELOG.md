# Changelog

## 0.1.0 — prepared for first release

- Import Hevy strength history and saved routines into wger through its API.
- Review exercise mappings before import; preserve individual sets, supersets,
  workout timestamps and source notes.
- Resume interrupted imports with a durable SQLite journal and configurable
  handling of Hevy deletions and edits to imported wger records.
- Run with Docker Compose, manually or on a 15-minute schedule.
- Test against a mock Hevy HTTP API and an isolated Docker wger harness.
- Publish tested amd64/arm64 containers to GHCR when a GitHub release is published.
