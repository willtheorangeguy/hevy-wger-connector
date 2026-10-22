# CI/CD

`test.yml` runs unit/release tests, Compose validation and a non-root container startup check on pushes and pull requests. Manual dispatch also runs integration when `WGER_HARNESS_REPOSITORY` identifies an accessible harness. A private harness needs read-only `WGER_HARNESS_TOKEN` access.

```sh
gh workflow run test.yml
```

`publish.yml` validates the published release version, invokes test gates and publishes GHCR images for Linux amd64/arm64. Stable releases receive exact, minor and latest tags; prereleases receive exact versions only. See [release instructions](https://github.com/willtheorangeguy/hevy-wger-connector/blob/HEAD/RELEASING.md).

`docs-lint.yml` calls shared Markdown, strict-build and link checks on docs PRs. `docs.yml` builds/deploys Pages on main/master docs pushes or manual dispatch, using the inherited Material theme. Pages must use Actions as its build source.
