# Roadmap

The current importer has explicit boundaries. These are verified limitations, not a release schedule.

- No web dashboard, writes back to Hevy, nutrition/measurement imports or automatic exercise creation.
- Duration/distance exercise types are excluded. Supported strength data in mixed workouts remains eligible.
- Failure labels, RPE, notes and assistance metadata do not all have equivalent native fields and are retained in notes/snapshots.
- Hevy does not provide actual per-set completion times. Logs use workout start and retain order through slots/metadata.
- Imports span multiple API requests. The journal supports recovery but does not make the destination transaction atomic.
- Uncertain integer-ID creates can require explicit operator confirmation before retry.
- Empty monthly archives can remain after the final managed workout is deleted.
- Automated source tests use mock Hevy; live source behavior still needs validation with the operator's own key.

Review actual outcomes with `docker compose run --rm connector status --json`. See [usage](usage.md) for data fidelity and [recovery](recovery.md) for held writes.
