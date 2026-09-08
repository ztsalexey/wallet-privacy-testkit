import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    'verify_release_assets', Path(__file__).resolve().parents[1] / 'scripts' / 'verify_release_assets.py'
)
release_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_assets)


class ReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'pyproject.toml').write_text('[project]\nversion = "0.3.0"\n')
        (self.root / 'dist').mkdir()
        self.names = ('wallet_privacy_testkit-0.3.0-py3-none-any.whl',
                      'wallet_privacy_testkit-0.3.0.tar.gz')
        self.lines = []
        for name in self.names:
            data = f'reviewed artifact {name}'.encode()
            (self.root / 'dist' / name).write_bytes(data)
            self.lines.append(f'{hashlib.sha256(data).hexdigest()}  dist/{name}\n')
        (self.root / 'SHA256SUMS').write_text(''.join(self.lines))

    def test_only_reviewed_artifacts_are_accepted(self):
        self.assertEqual(release_assets.verify_release_assets(self.root, 'v0.3.0'),
                         sorted(f'dist/{name}' for name in self.names))
        extra = self.root / 'dist' / 'unreviewed-1.0-py3-none-any.whl'
        extra.write_bytes(b'extra upload')
        with self.assertRaisesRegex(ValueError, 'file set'):
            release_assets.verify_release_assets(self.root, 'v0.3.0')

    def test_tag_and_checksum_entries_must_describe_same_version(self):
        with self.assertRaisesRegex(ValueError, 'tag'):
            release_assets.verify_release_assets(self.root, 'v0.2.0')
        (self.root / 'SHA256SUMS').write_text(''.join(self.lines).replace('0.3.0', '0.2.0'))
        with self.assertRaisesRegex(ValueError, 'this version'):
            release_assets.verify_release_assets(self.root, 'v0.3.0')

    def test_changed_missing_or_symlinked_artifacts_fail(self):
        path = self.root / 'dist' / self.names[0]
        original = path.read_bytes()
        path.write_bytes(b'changed after review')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            release_assets.verify_release_assets(self.root, 'v0.3.0')
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'file set'):
            release_assets.verify_release_assets(self.root, 'v0.3.0')
        outside = self.root / 'outside.whl'
        outside.write_bytes(original)
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            release_assets.verify_release_assets(self.root, 'v0.3.0')

    def test_ambiguous_or_unsafe_checksum_entries_fail(self):
        for manifest, message in [
            (''.join(self.lines) + self.lines[0], 'duplicate'),
            (self.lines[0], 'exactly'),
            (''.join(self.lines).replace('  dist/', '  ../dist/', 1), 'malformed'),
            (''.join(self.lines).replace('  dist/', '  dist/nested/', 1), 'malformed'),
        ]:
            with self.subTest(manifest=manifest):
                (self.root / 'SHA256SUMS').write_text(manifest)
                with self.assertRaisesRegex(ValueError, message):
                    release_assets.verify_release_assets(self.root, 'v0.3.0')
