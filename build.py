#!/usr/bin/env python3
"""Build (and optionally push) the reusable Python/dbt CI image.

Stdlib-only helper so local and CI builds share one command:

    python3 build.py
    python3 build.py --push --registry ghcr.io/predictive-paul/python_dbt_image
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
    return text.splitlines()[0].strip()


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
) -> None:
    tags = image_refs(name, version, registries, extra_tags, latest)
    build_cmd = ["build", "-f", str(dockerfile), "-t", tags[0]]
    for tag in tags[1:]:
        build_cmd.extend(["-t", tag])
    build_cmd.append(str(REPO_ROOT))
    run_docker(build_cmd, dry_run=dry_run)

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
        version = args.version or read_version()
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
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            return exc.returncode or 1
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
