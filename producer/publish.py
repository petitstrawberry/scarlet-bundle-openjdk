#!/usr/bin/env python3
"""Publish verified CI archives together and update the consumer bundle pins."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import build
import release


def run(*args, **kwargs):
    return subprocess.check_output(list(args), cwd=build.ROOT, text=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--branch', default='main', help='Branch whose bundle pins receive the verified release')
    a = p.parse_args()
    if release.git('rev-parse', 'HEAD') != a.revision or release.git('status', '--porcelain'):
        p.error('Checkout must be clean and match the CI build revision')
    metadata = [release.verify_release(a.artifacts / ('openjdk-' + jdk)) for jdk in ('21', '25')]
    version, = {m['version'] for m in metadata}
    if any(m['producer_commit'] != a.revision for m in metadata):
        p.error('CI archives were built from another producer revision')
    # Refuse existing tags as well as releases; never replace published bytes.
    if release.git('ls-remote', '--tags', 'origin', 'refs/tags/' + version):
        p.error('Version tag already exists; choose a new version')
    probe = subprocess.run(['gh', 'release', 'view', version, '--repo', release.REPOSITORY],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if probe.returncode == 0:
        p.error('Release already exists; choose a new version')
    if 'release not found' not in probe.stderr.lower():
        p.error('Could not determine release state: ' + probe.stderr)
    with tempfile.TemporaryDirectory(prefix='openjdk-publish-') as temporary:
        upload = Path(temporary)
        assets = []
        for jdk in ('21', '25'):
            group = []
            for source in sorted((a.artifacts / ('openjdk-' + jdk)).iterdir()):
                if source.name == 'SHA256SUMS':
                    continue
                name = source.name if source.name.endswith('.tar.gz') else 'openjdk-' + jdk + '-' + source.name
                target = upload / name
                shutil.copy2(source, target)
                assets.append(target)
                group.append(target)
            sums = upload / ('openjdk-' + jdk + '-SHA256SUMS')
            sums.write_text(''.join(build.sha256(path) + '  ' + path.name + '\n' for path in group))
            assets.append(sums)
        notes = upload / 'notes.md'
        notes.write_text('Native Scarlet AArch64 OpenJDK 21 (C1) and 25 (C1+C2).\n\n'
                         'Built by CI from [' + a.revision + '](' + release.REPOSITORY + '/tree/' + a.revision + '). '
                         'Each runtime includes its licenses and a source index linking the exact existing forks and dependencies. '
                         'The producer sources are available from this release tag.\n\n'
                         'This release passed compilation, native ELF and archive checks. '
                         'See producer/VALIDATION.md for the separately recorded guest execution scope.\n')
        run('gh', 'release', 'create', version, '--repo', release.REPOSITORY, '--draft', '--prerelease',
            '--target', a.revision, '--title', 'Native OpenJDK ' + version, '--notes-file', str(notes),
            *map(str, assets))
        uploaded = json.loads(run('gh', 'release', 'view', version, '--repo', release.REPOSITORY, '--json', 'assets'))['assets']
        expected = {path.name: path.stat().st_size for path in assets}
        if {item['name']: item['size'] for item in uploaded} != expected:
            raise build.BuildError('Incomplete release upload; draft retained')
        downloaded = upload / 'verify'
        run('gh', 'release', 'download', version, '--repo', release.REPOSITORY, '--dir', str(downloaded))
        if any(build.sha256(downloaded / path.name) != build.sha256(path) for path in assets):
            raise build.BuildError('Uploaded asset checksum mismatch; draft retained')
    run('gh', 'release', 'edit', version, '--repo', release.REPOSITORY, '--draft=false')
    for jdk in ('21', '25'):
        shutil.copyfile(a.artifacts / ('openjdk-' + jdk) / 'bundle.toml',
                        build.ROOT / 'bundles' / ('openjdk-' + jdk) / 'bundle.toml')
    run('git', 'add', 'bundles/openjdk-21/bundle.toml', 'bundles/openjdk-25/bundle.toml')
    run('git', 'commit', '-m', 'Pin OpenJDK CI archives ' + version)
    run('git', 'push', 'origin', 'HEAD:' + a.branch)
    print('Published ' + version)


if __name__ == '__main__':
    main()
