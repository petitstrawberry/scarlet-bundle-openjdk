"""A consumer must receive the checked binary and only its versioned files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build
import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / 'runtime'
        self.home = self.stage / 'usr/lib/jvm/openjdk-25'
        self.output = self.root / 'release'
        self.output.mkdir()
        self.sources = {'producer': {'commit': 'a' * 40}}
        for name in ('LICENSE', 'ADDITIONAL_LICENSE_INFO', 'ASSEMBLY_EXCEPTION', 'lib/modules',
                     'legal/scarlet-runtime/NOTICE', 'legal/scarlet-runtime/sources.json'):
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.sources) if name.endswith('.json') else 'fixture')
        for path in (self.stage / 'bin/java25', self.home / 'bin/java'):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'checked-native-executable')
            path.chmod(0o755)

    def package(self):
        name = 'openjdk-25-aarch64-v0.1.0.tar.gz'
        artifact = self.output / name
        release.archive_runtime(self.stage, artifact, 1234)
        metadata = dict(jdk='25', version='v0.1.0', artifact=name,
                        producer_commit='a' * 40, java_sha256=build.sha256(self.stage / 'bin/java25'),
                        sha256=build.sha256(artifact))
        for filename, value in [('sources.json', self.sources), ('build.json', {}), ('release.json', metadata)]:
            (self.output / filename).write_bytes(build.json_bytes(value))
        (self.output / 'bundle.toml').write_text(release.bundle_manifest('v0.1.0', '25', metadata['sha256']))
        self.rehash()
        return artifact

    def rehash(self):
        (self.output / 'SHA256SUMS').write_text(''.join(build.sha256(p) + '  ' + p.name + '\n'
                                                    for p in sorted(self.output.iterdir()) if p.name != 'SHA256SUMS'))

    def test_archive_is_deterministic_and_manifest_matches(self):
        first = self.package()
        second = self.root / 'again.tar.gz'
        release.archive_runtime(self.stage, second, 1234)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(release.verify_release(self.output)['jdk'], '25')

    def test_corrupt_archive_is_rejected_before_installation(self):
        archive = self.package()
        archive.write_bytes(archive.read_bytes() + b'corrupt')
        with self.assertRaisesRegex(build.BuildError, 'checksum|SHA-256'):
            release.verify_release(self.output)

    def test_default_java_and_other_versions_cannot_be_overwritten(self):
        (self.stage / 'bin/java').write_bytes(b'wrong')
        self.package()
        with self.assertRaisesRegex(build.BuildError, 'versioned paths'):
            release.verify_release(self.output)

    def test_missing_notice_prevents_release(self):
        (self.home / 'LICENSE').unlink()
        self.package()
        with self.assertRaisesRegex(build.BuildError, 'Incomplete runtime'):
            release.verify_release(self.output)

    def test_manifest_cannot_select_another_archive(self):
        self.package()
        (self.output / 'bundle.toml').write_text(release.bundle_manifest('v0.1.1', '25', '0' * 64))
        self.rehash()
        with self.assertRaisesRegex(build.BuildError, 'Bundle does not match'):
            release.verify_release(self.output)

    def test_source_index_must_match_the_installed_runtime(self):
        self.package()
        source = dict(self.sources, unrelated='different sources')
        (self.output / 'sources.json').write_bytes(build.json_bytes(source))
        self.rehash()
        with self.assertRaisesRegex(build.BuildError, 'Installed source index'):
            release.verify_release(self.output)

    def test_symlink_payload_is_rejected(self):
        (self.home / 'external').symlink_to(self.root)
        with self.assertRaisesRegex(build.BuildError, 'Unsupported runtime'):
            self.package()
