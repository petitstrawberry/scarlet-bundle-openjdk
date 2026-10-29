"""Version isolation and image composition must work without a Scarlet checkout."""
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def receipt(self, major):
        home = self.root / ('openjdk-' + major)
        (home / 'lib').mkdir(parents=True)
        (home / 'lib/modules').write_bytes(('classes-' + major).encode())
        java = self.root / ('native-java-' + major)
        java.write_bytes(('executable-' + major).encode())
        java.chmod(0o755)
        return dict(artifact=str(java), artifact_sha256=bundle.build.sha256(java), java_home=str(home))

    def test_each_version_provides_java(self):
        for major in ('21', '25'):
            stage = self.root / ('image-' + major)
            receipt = self.receipt(major)
            home = bundle.install(receipt, stage, major)
            self.assertEqual((home / 'lib/modules').read_bytes(), ('classes-' + major).encode())
            self.assertEqual((home / 'bin/java').read_bytes(), (stage / 'bin/java').read_bytes())
            self.assertEqual([p.name for p in (stage / 'bin').iterdir()], ['java'])

    def test_versions_are_mutually_exclusive(self):
        stage = self.root / 'image'
        bundle.install(self.receipt('21'), stage, '21')
        with self.assertRaisesRegex(bundle.build.BuildError, 'mutually exclusive'):
            bundle.install(self.receipt('25'), stage, '25')
        self.assertEqual((stage / 'bin/java').read_bytes(), b'executable-21')
        self.assertFalse((stage / 'usr/lib/jvm/openjdk-25').exists())

    def test_receipt_version_and_checksum_must_match(self):
        receipt = self.receipt('25')
        for major, digest in (('21', receipt['artifact_sha256']), ('25', '0' * 64)):
            with self.assertRaises(bundle.build.BuildError):
                bundle.install(dict(receipt, artifact_sha256=digest), self.root / 'image', major)
        self.assertFalse((self.root / 'image').exists())

    def test_image_links_cannot_redirect_installation(self):
        receipt = self.receipt('25')
        stage, outside = self.root / 'image', self.root / 'outside'
        stage.mkdir(); outside.mkdir()
        (stage / 'usr').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(bundle.build.BuildError):
            bundle.install(receipt, stage, '25')
        self.assertEqual(list(outside.iterdir()), [])

    def test_version_recipes_are_self_contained_and_pinned(self):
        for major in ('21', '25'):
            root = bundle.build.ROOT
            source = bundle.build.load_sources(root / 'versions' / major / 'sources.json')['openjdk']
            self.assertTrue(source['version'].startswith('jdk-' + major + '.'))
            self.assertIn(source['commit'], source['url'])
            manifest = root / 'bundles' / ('openjdk-' + major) / 'bundle.toml'
            layer, = tomllib.loads(manifest.read_text())['layers']
            self.assertEqual(layer['kind'], 'archive')
            self.assertEqual(layer['format'], 'tar-gz')
            self.assertEqual(layer['strip_components'], 1)
            self.assertEqual(layer['to'], '/')
            self.assertRegex(layer['sha256'], r'^sha256:[0-9a-f]{64}$')
            self.assertTrue(layer['url'].startswith(
                'https://github.com/petitstrawberry/scarlet-bundle-openjdk/releases/download/'))
            self.assertIn('/openjdk-' + major + '-aarch64-', layer['url'])


if __name__ == '__main__':
    unittest.main()
