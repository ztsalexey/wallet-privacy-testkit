#!/usr/bin/env python3
"""Fail when release metadata or source contents violate the package boundary."""

import argparse
import json
import py_compile
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
sys.path.insert(0, str(SOURCE))

from wallet_privacy_testkit import __version__

IGNORED_DIRECTORIES = frozenset(
    (".git", ".venv", "__pycache__", "build", "dist", ".pytest_cache")
)
FORBIDDEN_DIRECTORIES = frozenset(("state", "target", "vendor", "runs"))
FORBIDDEN_SUFFIXES = frozenset((".dat", ".key", ".pem", ".seed", ".wallet"))
FORBIDDEN_TEXT = (
    ("private key marker", re.compile(r"BEGIN (?:RSA |EC )?PRIVATE KEY")),
    ("absolute developer path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("regtest unified address", re.compile(r"uregtest1[0-9a-z]{40,}")),
    ("mainnet unified address", re.compile(r"u1[0-9a-z]{40,}")),
)
REQUIRED_FILES = (
    ".github/workflows/ci.yml",
    ".github/workflows/publish.yml",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "LICENSE-APACHE",
    "LICENSE-MIT",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    "docs/COMPETITIVE_LANDSCAPE.md",
    "docs/METHODOLOGY.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_NOTES.md",
    "docs/THREAT_MODEL.md",
)
TEXT_SUFFIXES = frozenset((".cff", ".json", ".jsonl", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"))
MAX_RELEASE_FILE_BYTES = 1_000_000


def release_files():
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not IGNORED_DIRECTORIES.intersection(path.relative_to(ROOT).parts)
    ]


def local_markdown_links(path, source):
    for target in re.findall(r"\]\(([^)]+)\)", source):
        if "://" in target or target.startswith("#") or target.startswith("mailto:"):
            continue
        yield target.split("#", 1)[0]


def artifact_errors(version):
    errors = []
    artifacts = sorted((ROOT / "dist").glob("*"))
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
    unexpected = [path for path in artifacts if path not in wheels + sdists]
    if len(wheels) != 1 or len(sdists) != 1 or unexpected:
        return [
            "dist must contain exactly one wheel and one .tar.gz source archive"
        ]
    expected_wheel = f"wallet_privacy_testkit-{version}-py3-none-any.whl"
    expected_sdist = f"wallet_privacy_testkit-{version}.tar.gz"
    if wheels[0].name != expected_wheel:
        errors.append(f"unexpected wheel name: {wheels[0].name}")
    if sdists[0].name != expected_sdist:
        errors.append(f"unexpected sdist name: {sdists[0].name}")

    members = []
    with zipfile.ZipFile(wheels[0]) as archive:
        members.extend((wheels[0].name, item.filename, item.file_size, archive.read(item)) for item in archive.infolist() if not item.is_dir())
    with tarfile.open(sdists[0], "r:gz") as archive:
        for item in archive.getmembers():
            if item.isfile():
                source = archive.extractfile(item)
                members.append((sdists[0].name, item.name, item.size, source.read()))

    for artifact, name, size, payload in members:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe archive path in {artifact}: {name}")
        if "zcash_privacy_testkit" in relative.parts:
            errors.append(f"obsolete package path in {artifact}: {name}")
        if FORBIDDEN_DIRECTORIES.intersection(relative.parts):
            errors.append(f"forbidden directory in {artifact}: {name}")
        if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden file type in {artifact}: {name}")
        if size > MAX_RELEASE_FILE_BYTES:
            errors.append(f"archive member exceeds 1 MB in {artifact}: {name}")
        if relative.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            source = payload.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"expected UTF-8 archive member in {artifact}: {name}")
            continue
        for label, pattern in FORBIDDEN_TEXT:
            if pattern.search(source):
                errors.append(f"{label} in {artifact}: {name}")
    return errors


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument(
        "--artifacts", action="store_true", help="also inspect the built wheel and sdist"
    )
    options = arguments.parse_args()
    errors = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    declared_version = metadata["project"]["version"]
    if declared_version != __version__:
        errors.append(
            f"version mismatch: pyproject {declared_version}, package {__version__}"
        )
    changelog = (ROOT / "CHANGELOG.md").read_text()
    release_notes = (ROOT / "docs/RELEASE_NOTES.md").read_text()
    for name, source in (("changelog", changelog), ("release notes", release_notes)):
        if declared_version not in source:
            errors.append(f"{name} does not contain version {declared_version}")
    files = release_files()
    for path in files:
        relative = path.relative_to(ROOT)
        if FORBIDDEN_DIRECTORIES.intersection(relative.parts):
            errors.append(f"forbidden release directory: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden release file type: {relative}")
        if path.stat().st_size > MAX_RELEASE_FILE_BYTES:
            errors.append(f"release file exceeds 1 MB: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            source = path.read_text()
        except UnicodeDecodeError:
            errors.append(f"expected text file is not UTF-8: {relative}")
            continue
        for label, pattern in FORBIDDEN_TEXT:
            if pattern.search(source):
                errors.append(f"{label} in {relative}")
        if path.suffix.lower() == ".md":
            for link in local_markdown_links(path, source):
                if link and not (path.parent / link).exists():
                    errors.append(f"broken local link in {relative}: {link}")
        if path.suffix.lower() == ".json":
            try:
                json.loads(source)
            except json.JSONDecodeError as error:
                errors.append(f"invalid JSON in {relative}: {error}")
        if path.suffix.lower() == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as error:
                errors.append(f"Python compile failure in {relative}: {error}")
    if options.artifacts:
        errors.extend(artifact_errors(declared_version))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    print(
        json.dumps(
            {
                "version": declared_version,
                "release_files_checked": len(files),
                "required_files": len(REQUIRED_FILES),
                "private_key_markers": 0,
                "forbidden_artifacts": 0,
                "broken_local_links": 0,
                "artifacts_checked": options.artifacts,
                "status": "pass",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
