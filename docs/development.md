# Development

Use Python 3.12+ or the supplied Docker runner. Install the exact lock file before the editable package:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
pytest -q -m 'not integration'
```

The repository's [contributing notes](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/CONTRIBUTING.md) also show the Windows virtual-environment path. Source images use `compose.build.yaml`; test images use `compose.test.yaml`. See [testing](testing.md) for the real-wger runner and cleanup.

Use synthetic fixtures and isolated accounts when changing synchronization. Preserve unknown-write, conflict and deletion-safety coverage. Keep `.env`, workout snapshots, tokens, reports and runtime data out of commits. Include the checks run in each PR.

## Documentation

With the shared MkDocs checkout beside this repository:

```sh
../mkdocs/scripts/docs-serve.sh --build
../mkdocs/scripts/docs-serve.sh
```

Shared dependencies, plugins, assets and writing rules belong to [willtheorangeguy/mkdocs](https://github.com/willtheorangeguy/mkdocs). Project configuration declares identity and navigation without replacing inherited plugin/extension lists.
