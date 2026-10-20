"""Validate release identity before allowing a container to be published."""

import ast
import os
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def release_metadata(tag, prerelease, version, source_version, repository):
    match = re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", tag)
    if not match:
        raise ValueError("Release tag must be vMAJOR.MINOR.PATCH with an optional prerelease suffix")
    if match[4] and any(part.isdigit() and len(part) > 1 and part[0] == "0" for part in match[4][1:].split(".")):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeroes")
    if tag[1:] != version or version != source_version:
        raise ValueError("Release tag, pyproject.toml and hevy_wger.__version__ must match")
    if bool(match[4]) != prerelease:
        raise ValueError("GitHub prerelease status must match the version suffix")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be OWNER/REPOSITORY")
    return {
        "version": version,
        "minor": f"{match[1]}.{match[2]}",
        "stable": str(not prerelease).lower(),
        "image": f"ghcr.io/{repository.lower()}",
    }


def main():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    tree = ast.parse((ROOT / "src/hevy_wger/__init__.py").read_text(encoding="utf-8"))
    source_version = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    )
    prerelease = os.environ.get("RELEASE_PRERELEASE", "false")
    if prerelease not in {"true", "false"}:
        raise ValueError("RELEASE_PRERELEASE must be true or false")
    metadata = release_metadata(
        os.environ["RELEASE_TAG"], prerelease == "true", project["version"],
        source_version, os.environ["GITHUB_REPOSITORY"],
    )
    output = "".join(f"{key}={value}\n" for key, value in metadata.items())
    print(output, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write(output)


if __name__ == "__main__":
    main()
