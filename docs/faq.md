# FAQ

???+ question "Does preview write anything?"

    It fetches and caches source records locally but performs zero destination writes. Mapping suggestions are candidates, never approvals.

??? question "Why are my timed holds or cardio missing?"

    The graph builder excludes duration/distance-only exercise types. A mixed workout imports its supported strength portion. Missing mappings for supported exercises hold the entire source object.

??? question "Can it write workouts back to Hevy?"

    No. It reads Hevy's official API and writes wger REST resources. Nutrition, measurements and automatic exercise creation are outside its scope.

??? question "Will mirror mode delete my native wger workouts?"

    It operates on tracked imported structures, not unrelated native objects. Cascade checks refuse deletion when other local records would be affected. Mirror also overwrites local changes to managed fields.

??? question "Why is bodyweight volume lower than effective body mass?"

    Additional load is retained without adding an invented body mass. Assisted reps do not become positive weight lifted. Exact source values remain in snapshots/notes.

??? question "Why does a routine show a 28-day period?"

    Saved templates use a placeholder reusable period. Completed history lives in separate monthly archives grouped by source routine, with UTC archive months.
