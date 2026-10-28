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

    def test_two_versions_coexist_without_replacing_default_java(self):
        stage = self.root / 'image'
        (stage / 'bin').mkdir(parents=True)
        (stage / 'bin/java').write_text('project-owned default')
        for major in ('21', '25'):
            receipt = self.receipt(major)
            home = bundle.install(receipt, stage, major)
            self.assertEqual((home / 'lib/modules').read_bytes(), ('classes-' + major).encode())
            self.assertEqual((home / 'bin/java').read_bytes(), (stage / ('bin/java' + major)).read_bytes())
        self.assertEqual((stage / 'bin/java').read_text(), 'project-owned default')
        self.assertNotEqual((stage / 'bin/java21').read_bytes(), (stage / 'bin/java25').read_bytes())

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
            self.assertEqual(layer['kind'], 'script')
            self.assertEqual(layer['architectures'], ['aarch64'])
            self.assertTrue((manifest.parent / layer['source']).is_file())


if __name__ == '__main__':
    unittest.main()
