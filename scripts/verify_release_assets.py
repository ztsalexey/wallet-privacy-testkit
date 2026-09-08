#!/usr/bin/env python3
"""Verify that publishing uses exactly the two reviewed artifacts for this tag."""

import argparse
import hashlib
import re
import sys
import tomllib
from pathlib import Path


def verify_release_assets(root, tag):
    root = Path(root)
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if not isinstance(version, str) or tag != f'v{version}':
        raise ValueError('release tag does not match the project version')
    expected = {
        f'dist/wallet_privacy_testkit-{version}-py3-none-any.whl',
        f'dist/wallet_privacy_testkit-{version}.tar.gz',
    }
    checksums = {}
    for line in (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (dist/[^/\\]+)', line)
        if match is None:
            raise ValueError('malformed release checksum entry')
        digest, filename = match.groups()
        if filename in checksums:
            raise ValueError('duplicate release checksum entry')
        checksums[filename] = digest
    if set(checksums) != expected:
        raise ValueError('checksums must list exactly the wheel and source archive for this version')
    dist = root / 'dist'
    if dist.is_symlink() or not dist.is_dir():
        raise ValueError('dist must be a regular directory')
    files = list(dist.iterdir())
    if {f'dist/{path.name}' for path in files} != expected:
        raise ValueError('downloaded release files differ from the reviewed checksum file set')
    for filename, expected_digest in checksums.items():
        path = root / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'release artifact must be a regular file: {filename}')
        with path.open('rb') as source:
            actual_digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual_digest != expected_digest:
            raise ValueError(f'release checksum mismatch: {filename}')
    return sorted(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True, help='release tag, for example v0.3.0')
    args = parser.parse_args()
    try:
        files = verify_release_assets(Path(__file__).resolve().parents[1], args.tag)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'release verification failed: {error}', file=sys.stderr)
        return 1
    print(f'Verified exactly {len(files)} reviewed release artifacts for {args.tag}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
