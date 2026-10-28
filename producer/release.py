#!/usr/bin/env python3
"""Package a built runtime as a checksum-pinned release archive.

Sources remain in their existing repositories. sources.json identifies the exact
revisions/downloads; notices from statically linked dependencies accompany Java.
Run in the matching producer Nix shell after build.py --target java.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.request

import build
import bundle

REPOSITORY = 'https://github.com/petitstrawberry/scarlet-bundle-openjdk'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=build.ROOT, text=True).strip()


def fetch(url, checksum=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'scarlet-openjdk-release'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if checksum and hashlib.sha256(data).hexdigest() != checksum:
        raise build.BuildError('Source checksum mismatch: ' + url)
    return data


def source_ref(repository, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise build.BuildError('Expected an immutable Git revision')
    return dict(repository=repository, commit=revision,
                url=repository + '/archive/' + revision + '.tar.gz')


def collect_notices(receipt, destination, flake_inputs, revision):
    destination.mkdir(parents=True)
    refs = {'producer': source_ref(REPOSITORY, revision),
            **receipt['inputs']['source_archives']}
    for name in ('LICENSE', 'NOTICE', 'ATTRIBUTION.md'):
        shutil.copy2(build.ROOT / name, destination / name)
    shutil.copytree(build.ROOT / 'LICENSES', destination / 'producer')
    sdk = Path(flake_inputs['inputs']['scarlet-sdk']['path'])
    llvm = Path(flake_inputs['inputs']['scarlet-sdk']['inputs']['llvm-src']['path'])
    abi = Path(flake_inputs['inputs']['scarlet-sdk']['inputs']['scarlet-abi-src']['path'])
    lock = json.loads((build.ROOT / 'flake.lock').read_text())
    refs['flake_inputs'] = {name: source_ref('https://github.com/' + node['locked']['owner']
                                           + '/' + node['locked']['repo'], node['locked']['rev'])
                           for name, node in lock['nodes'].items()
                           if node.get('locked', {}).get('type') == 'github'}
    notices = {'scarlet-sdk': sdk / 'LICENSE', 'scarlet-abi': abi / 'LICENSE',
               'libffi': Path(receipt['inputs']['sources']['libffi']) / 'LICENSE',
               'llvm': llvm / 'LICENSE.TXT', 'libcxx': llvm / 'libcxx/LICENSE.TXT',
               'libcxxabi': llvm / 'libcxxabi/LICENSE.TXT', 'llvm-libc': llvm / 'libc/LICENSE.TXT'}
    for name, path in notices.items():
        shutil.copy2(build.regular_file(path), destination / (name + '.txt'))
    rustc = receipt['inputs']['toolchain']['environment']['SCARLET_RUSTC']
    rust = Path(subprocess.check_output([rustc, '--print', 'sysroot'], text=True).strip())
    rust_manifest = tomllib.loads((rust / 'manifest.toml').read_text())
    for label, key in (('rust-compiler-crt', 'rust_commit'), ('rust-native-std', 'native_std_commit')):
        refs[label] = source_ref('https://github.com/petitstrawberry/rust', rust_manifest[key])
    # The pinned Nix recipe supplies the backtrace submodule omitted by GitHub tarballs.
    recipe = Path(flake_inputs['inputs']['scarlet-rust-toolchain']['path']) / 'flake.nix'
    backtrace, = re.findall(r'https://github.com/rust-lang/backtrace-rs/archive/([0-9a-f]{40})\.tar\.gz', recipe.read_text())
    refs['backtrace'] = source_ref('https://github.com/rust-lang/backtrace-rs', backtrace)
    for name in ('LICENSE-MIT', 'LICENSE-APACHE', 'COPYRIGHT'):
        url = 'https://raw.githubusercontent.com/petitstrawberry/rust/' + rust_manifest['native_std_commit'] + '/' + name
        (destination / ('rust-' + name)).write_bytes(fetch(url))
    library = rust / 'lib/rustlib/src/rust/library'
    for path in sorted(library.rglob('*')):
        if path.is_file() and re.match(r'(?i)(license|copying|copyright|notice)', path.name):
            target = destination / 'rust-library' / path.relative_to(library)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    packages = {}
    runtime_crates = {path.name[3:].rsplit('-', 1)[0]
                      for path in (rust / 'lib/rustlib/aarch64-unknown-scarlet/lib').glob('lib*.rlib')}
    for name, path in (('scarlet-libc', sdk / 'scarlet-libc/Cargo.lock'),
                       ('rust-library', library / 'Cargo.lock')):
        shutil.copy2(path, destination / (name + '.lock'))
        for item in tomllib.loads(path.read_text())['package']:
            if (item.get('source', '').startswith('registry+')
                    and (name == 'scarlet-libc' or item['name'].replace('-', '_') in runtime_crates)):
                packages[(item['name'], item['version'])] = item
    def crate(item):
        name, version = item['name'], item['version']
        url = f'https://static.crates.io/crates/{name}/{name}-{version}.crate'
        data = fetch(url, item['checksum'])
        count = 0
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if not member.isfile() or not re.match(r'(?i)(license|copying|copyright|notice)', path.name):
                    continue
                if path.is_absolute() or '..' in path.parts or path.parts[0] != name + '-' + version:
                    raise build.BuildError('Invalid crate notice path')
                target = destination / 'crates' / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                count += 1
        if not count:
            raise build.BuildError('No license notice in ' + url)
        return dict(name=name, version=version, url=url, sha256=item['checksum'])
    with ThreadPoolExecutor(max_workers=6) as pool:
        refs['rust_dependencies'] = list(pool.map(crate, packages.values()))
    (destination / 'sources.json').write_bytes(build.json_bytes(refs))
    return refs


def archive_runtime(stage, output, epoch):
    # Stable metadata and ordering; retain executable modes without host owners.
    with output.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for path in [stage, *sorted(stage.rglob('*'))]:
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise build.BuildError('Unsupported runtime entry: ' + str(path))
                name = 'rootfs' if path == stage else 'rootfs/' + path.relative_to(stage).as_posix()
                info = archive.gettarinfo(str(path), arcname=name)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = epoch
                info.pax_headers = {}
                if path.is_file():
                    with path.open('rb') as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)


def bundle_manifest(version, major, checksum):
    name = f'openjdk-{major}-aarch64-{version}.tar.gz'
    return ('# Generated from the verified CI release archive.\n[[layers]]\nkind = "archive"\n'
            f'url = "{REPOSITORY}/releases/download/{version}/{name}"\n'
            f'sha256 = "sha256:{checksum}"\nformat = "tar-gz"\nstrip_components = 1\nto = "/"\n')


def verify_release(output):
    metadata = json.loads((output / 'release.json').read_text())
    major, version = metadata['jdk'], metadata['version']
    if major not in ('21', '25') or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', version):
        raise build.BuildError('Invalid release identity')
    name = f'openjdk-{major}-aarch64-{version}.tar.gz'
    expected = {name, 'sources.json', 'build.json', 'bundle.toml', 'release.json'}
    hashes = {}
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        checksum, filename = line.split('  ')
        if filename not in expected or filename in hashes or not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise build.BuildError('Invalid checksum inventory')
        build.verify_archive(output / filename, checksum)
        hashes[filename] = checksum
    if set(hashes) != expected or {p.name for p in output.iterdir()} != expected | {'SHA256SUMS'}:
        raise build.BuildError('Incomplete release assets')
    if metadata['artifact'] != name or metadata['sha256'] != hashes[name]:
        raise build.BuildError('Archive does not match release metadata')
    if (output / 'bundle.toml').read_text() != bundle_manifest(version, major, hashes[name]):
        raise build.BuildError('Bundle does not match archive')
    sources = json.loads((output / 'sources.json').read_text())
    if sources['producer']['commit'] != metadata['producer_commit']:
        raise build.BuildError('Producer source revision mismatch')
    home = f'usr/lib/jvm/openjdk-{major}'
    required = {'bin/java', home + '/bin/java', home + '/lib/modules',
                home + '/LICENSE', home + '/ADDITIONAL_LICENSE_INFO', home + '/ASSEMBLY_EXCEPTION',
                home + '/legal/scarlet-runtime/sources.json', home + '/legal/scarlet-runtime/NOTICE'}
    found = set()
    with tarfile.open(output / name, 'r:gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'rootfs'
                    or not (member.isfile() or member.isdir()) or member.name in found):
                raise build.BuildError('Unsafe or duplicate archive entry: ' + member.name)
            found.add(member.name)
            relative = '/'.join(path.parts[1:])
            if (relative and relative not in ('bin', 'usr', 'usr/lib', 'usr/lib/jvm', 'bin/java')
                    and relative != home and not relative.startswith(home + '/')):
                raise build.BuildError('Runtime writes outside its supported paths: ' + relative)
            if relative in ('bin/java', home + '/bin/java'):
                data = archive.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != metadata['java_sha256'] or member.mode & 0o111 != 0o111:
                    raise build.BuildError('Installed executable mismatch')
            if relative == home + '/legal/scarlet-runtime/sources.json':
                if json.loads(archive.extractfile(member).read()) != sources:
                    raise build.BuildError('Installed source index mismatch')
        if not {'rootfs/' + p for p in required}.issubset(found):
            raise build.BuildError('Incomplete runtime archive')
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jdk', choices=('21', '25'), required=True)
    p.add_argument('--version', required=True)
    p.add_argument('--build-receipt', type=Path, required=True)
    p.add_argument('--flake-inputs', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', a.version):
        p.error('Version must look like v0.1.0')
    if git('status', '--porcelain', '--untracked-files=normal'):
        p.error('Commit the producer inputs before packaging a release')
    revision = git('rev-parse', 'HEAD')
    receipt = json.loads(a.build_receipt.read_text())
    for name, checksum in receipt['inputs']['local_sources'].items():
        if build.sha256(build.HERE / name) != checksum:
            p.error('Build receipt uses different producer inputs: ' + name)
    output = a.output.absolute()
    if output.exists():
        p.error('Release output must be a new directory')
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='openjdk-release-') as temporary:
        stage = Path(temporary) / 'runtime'
        home = bundle.install(receipt, stage, a.jdk)
        refs = collect_notices(receipt, home / 'legal/scarlet-runtime',
                               json.loads(a.flake_inputs.read_text()), revision)
        artifact = output / f'openjdk-{a.jdk}-aarch64-{a.version}.tar.gz'
        archive_runtime(stage, artifact, int(git('show', '-s', '--format=%ct', 'HEAD')))
    (output / 'sources.json').write_bytes(build.json_bytes(refs))
    (output / 'build.json').write_bytes(build.json_bytes(receipt))
    (output / 'bundle.toml').write_text(bundle_manifest(a.version, a.jdk, build.sha256(artifact)))
    provenance = dict(version=a.version, jdk=a.jdk, producer_commit=revision,
                      java_sha256=receipt['artifact_sha256'], jvm_variant=receipt['inputs']['jvm_variant'],
                      artifact=artifact.name, sha256=build.sha256(artifact),
                      scope='CI compilation, native ELF audit and archive checks; guest execution is recorded separately')
    (output / 'release.json').write_bytes(build.json_bytes(provenance))
    (output / 'SHA256SUMS').write_text(''.join(build.sha256(path) + '  ' + path.name + '\n'
                                             for path in sorted(output.iterdir())))
    verify_release(output)
    print('Packaged ' + str(artifact))


if __name__ == '__main__':
    main()
