# Publishing and releases

## First publication

The local `origin` is prepared for
`https://github.com/willtheorangeguy/hevy-wger-connector.git`.
Create that empty GitHub repository without adding a README, license or gitignore,
then push this repository's existing history. With GitHub CLI:

```powershell
gh repo create willtheorangeguy/hevy-wger-connector --public --description "Docker connector importing Hevy strength workouts into wger"
git push -u origin main
```

These commands publish the repository; preparation does not run them. Choose
`--private` instead if that is the intended visibility. Enable GitHub Actions if
organization policy disables it. No registry password or personal access token
is required: the publishing job uses its scoped `GITHUB_TOKEN` with
`contents: read` and `packages: write`.

Wait for the **Connector tests** workflow to pass. For optional hosted integration
tests, publish the separate wger harness first, set the repository variable
`WGER_HARNESS_REPOSITORY` to its `OWNER/REPOSITORY`, and add a read-only
`WGER_HARNESS_TOKEN` secret if that repository is private. Run **Connector tests**
manually to exercise mock Hevy against the real Docker wger sandbox. Local
integration testing works without publishing the harness.

## Release a version

1. Update both `pyproject.toml` and `src/hevy_wger/__init__.py` to the same version.
   The initial release is already `0.1.0`. Update `CHANGELOG.md` and the default
   `CONNECTOR_VERSION` example in `compose.ghcr.yaml` and the README as appropriate.
2. Run `python test_harness.py` with the sibling harness present. Review
   `reports/junit.xml`, update `VALIDATION.md`, and commit the release changes.
3. Push `main`, wait for CI, then tag the reviewed commit and push the tag:

   ```powershell
   git tag -a v0.1.0 -m "Release 0.1.0"
   git push origin v0.1.0
   gh release create v0.1.0 --verify-tag --title "v0.1.0" --notes-file CHANGELOG.md
   ```

Publishing the release (including a prerelease) triggers **Publish release
container**. Merely pushing a tag or saving a draft release does not publish an
image. Tags must be `vMAJOR.MINOR.PATCH`, optionally with a suffix such as
`v0.2.0-rc.1`; suffix versions must be marked as prereleases on GitHub and both
version files must contain that same suffix. A mismatch fails before publishing.
For prereleases add `--prerelease` to `gh release create`.

The workflow rechecks unit tests and container startup, then builds Linux amd64
and arm64 images with OCI source/version/license labels, SBOMs and BuildKit
provenance. Actions are pinned to commit SHAs; Dependabot proposes weekly updates.
The release gate does not require the separately configured integration job;
run the full harness before tagging as described above.

Stable `v0.1.0` publishes `:0.1.0`, `:0.1` and `:latest`. A prerelease publishes
only its full version, such as `:0.2.0-rc.1`. Stable aliases follow the last stable
release published, including a republished older release. Deploy by exact version
or digest when you need a fixed artifact. Use new versions for corrections rather
than moving an existing release tag. The workflow summary records the image digest.

## After the first image publishes

In the GitHub package's settings, verify that it links to this repository and
select **public** visibility if anonymous image pulls are intended. GHCR packages
can initially be private even when their source repository is public. Private
pulls require a GitHub login with package read access.

```powershell
docker buildx imagetools inspect ghcr.io/willtheorangeguy/hevy-wger-connector:0.1.0
docker compose -f compose.ghcr.yaml pull
docker compose -f compose.ghcr.yaml run --rm connector --help
```

For a fork, update the project URLs and Compose image default. Publishing itself
uses the current GitHub repository's lowercase name automatically.

## Local workflow checks

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo rhysd/actionlint:1.7.12
docker compose -f compose.ghcr.yaml config --quiet
docker compose -f compose.test.yaml build test
docker compose -f compose.test.yaml run --rm --no-deps test -q -m "not integration"
```

GitHub event handling, package permissions and registry uploads require an actual
GitHub release; local checks build and validate without publishing.

References: [GitHub's publishing workflow guide](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
and [GHCR authentication and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
