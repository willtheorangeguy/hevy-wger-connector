"""Prevent publishing mismatched versions or moving stable tags for prereleases."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_metadata", Path(__file__).resolve().parents[1] / "scripts/release_metadata.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_stable_release_metadata():
    result = release.release_metadata("v0.1.0", False, "0.1.0", "0.1.0", "Example/Connector")
    assert result == {"version": "0.1.0", "minor": "0.1", "stable": "true", "image": "ghcr.io/example/connector"}


def test_prerelease_does_not_get_stable_aliases():
    result = release.release_metadata("v0.2.0-rc.1", True, "0.2.0-rc.1", "0.2.0-rc.1", "owner/repo")
    assert result["stable"] == "false"
    assert result["version"] == "0.2.0-rc.1"


@pytest.mark.parametrize("tag,prerelease,version,source_version", [
    ("0.1.0", False, "0.1.0", "0.1.0"),
    ("v00.1.0", False, "00.1.0", "00.1.0"),
    ("v0.1.0", False, "0.2.0", "0.2.0"),
    ("v0.1.0", False, "0.1.0", "0.2.0"),
    ("v0.1.0", True, "0.1.0", "0.1.0"),
    ("v0.2.0-rc.1", False, "0.2.0-rc.1", "0.2.0-rc.1"),
    ("v0.2.0-rc.01", True, "0.2.0-rc.01", "0.2.0-rc.01"),
    ("v0.1.0\nlatest", False, "0.1.0", "0.1.0"),
])
def test_reject_invalid_release(tag, prerelease, version, source_version):
    with pytest.raises(ValueError):
        release.release_metadata(tag, prerelease, version, source_version, "owner/repo")
