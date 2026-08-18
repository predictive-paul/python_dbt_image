#!/usr/bin/env python3
"""Build, version, and optionally push the reusable Python/dbt CI image.

    python3 build.py
    python3 build.py --push --registry ghcr.io/predictive-paul/python_dbt_image
    python3 build.py --bump patch   # 0.1.0 → 0.1.1, commit, tag v0.1.1
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_NAME = "dbt"
DEFAULT_DOCKERFILE = REPO_ROOT / "Dockerfile"
DEFAULT_VERSION_FILE = REPO_ROOT / "VERSION"


def read_version(path: Path = DEFAULT_VERSION_FILE) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"version file is empty: {path}")
    return text.splitlines()[0].strip().lstrip("v")


def write_version(version: str, path: Path = DEFAULT_VERSION_FILE) -> None:
    path.write_text(f"{version}\n", encoding="utf-8")


def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.lstrip("v").split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"VERSION must be X.Y.Z (got {version!r})")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(version: str, part: str) -> str:
    major, minor, patch = parse_semver(version)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown bump part: {part}")


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def git_tag_name(version: str) -> str:
    return f"v{version}"


def bump_and_tag(part: str) -> str:
    current = read_version()
    new = bump_version(current, part)
    write_version(new)
    run(["git", "add", str(DEFAULT_VERSION_FILE.relative_to(REPO_ROOT))])
    run(["git", "commit", "-m", f"Bump version to {new}"])
    tag = git_tag_name(new)
    run(["git", "tag", "-a", tag, "-m", tag])
    print(
        f"Bumped {current} → {new} and created {tag}.\n"
        "Publish the image by pushing the tag:\n"
        "  git push origin HEAD\n"
        f"  git push origin {tag}"
    )
    return new


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Python/dbt image used by pi_dbt CI.",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"image name (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="image version (default: contents of VERSION)",
    )
    parser.add_argument(
        "--dockerfile",
        type=Path,
        default=DEFAULT_DOCKERFILE,
        help="path to the Dockerfile",
    )
    parser.add_argument(
        "--registry",
        action="append",
        dest="registries",
        default=[],
        metavar="PREFIX",
        help=(
            "registry prefix to also tag, e.g. "
            "ghcr.io/predictive-paul/python_dbt_image (repeatable)"
        ),
    )
    parser.add_argument(
        "--tag",
        action="append",
        dest="extra_tags",
        default=[],
        help="additional fully-qualified image tag (repeatable)",
    )
    parser.add_argument(
        "--latest",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also tag :latest (default: yes)",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="push registry-qualified tags after a successful build",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print docker commands without running them",
    )
    parser.add_argument(
        "--skip-smoke-test",
        action="store_true",
        help="Skip running dbt --version inside the built image",
    )
    parser.add_argument(
        "--bump",
        choices=("major", "minor", "patch"),
        help="Increment VERSION, commit, and create annotated git tag vX.Y.Z",
    )
    return parser.parse_args(argv)


def resolve_dockerfile(path: Path) -> Path:
    dockerfile = path if path.is_absolute() else REPO_ROOT / path
    if not dockerfile.is_file():
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")
    return dockerfile


def image_refs(
    name: str,
    version: str,
    registries: list[str],
    extra_tags: list[str],
    latest: bool,
) -> list[str]:
    refs = [f"{name}:{version}"]
    if latest:
        refs.append(f"{name}:latest")
    for registry in registries:
        prefix = registry.rstrip("/")
        refs.append(f"{prefix}/{name}:{version}")
        if latest:
            refs.append(f"{prefix}/{name}:latest")
    refs.extend(extra_tags)

    unique: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        unique.append(ref)
    return unique


def run_docker(args: list[str], *, dry_run: bool) -> None:
    cmd = ["docker", *args]
    print("+", " ".join(cmd), flush=True)
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def build_and_maybe_push(
    *,
    name: str,
    version: str,
    dockerfile: Path,
    registries: list[str],
    extra_tags: list[str],
    latest: bool,
    push: bool,
    dry_run: bool,
    skip_smoke_test: bool,
) -> None:
    tags = image_refs(name, version, registries, extra_tags, latest)
    build_cmd = ["build", "-f", str(dockerfile), "-t", tags[0]]
    for tag in tags[1:]:
        build_cmd.extend(["-t", tag])
    build_cmd.append(str(REPO_ROOT))
    run_docker(build_cmd, dry_run=dry_run)

    if not skip_smoke_test:
        run_docker(["run", "--rm", tags[0], "dbt", "--version"], dry_run=dry_run)

    if not push:
        return

    for tag in tags:
        if "/" not in tag:
            print(f"skipping push of local tag {tag}", flush=True)
            continue
        run_docker(["push", tag], dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.bump:
            bump_and_tag(args.bump)
            return 0
        version = (args.version or read_version()).lstrip("v")
        dockerfile = resolve_dockerfile(args.dockerfile)
        build_and_maybe_push(
            name=args.name,
            version=version,
            dockerfile=dockerfile,
            registries=args.registries,
            extra_tags=args.extra_tags,
            latest=args.latest,
            push=args.push,
            dry_run=args.dry_run,
            skip_smoke_test=args.skip_smoke_test,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            return exc.returncode or 1
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
