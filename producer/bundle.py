#!/usr/bin/env python3
"""Build a selected version and install its runtime into an explicit image stage."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import build


def install(receipt, destination, major):
    java = build.regular_file(Path(receipt['artifact']))
    home = Path(receipt['java_home'])
    if home.name != 'openjdk-' + major or build.sha256(java) != receipt['artifact_sha256']:
        raise build.BuildError('Build receipt version or executable checksum mismatch')
    if home.is_symlink() or not home.is_dir():
        raise build.BuildError('Expected a regular runtime home')
    if any(p.is_symlink() for p in home.rglob('*')):
        raise build.BuildError('Runtime payload must not contain symlinks')
    destination = destination.absolute()
    if destination.is_symlink():
        raise build.BuildError('Image destination must not be a symlink')
    destination = destination.resolve()
    target = destination / 'usr/lib/jvm' / home.name
    # The image stage is explicit; do not follow existing links out of it.
    for path in [target, *target.parents, destination / 'bin', target / 'bin']:
        if path.is_symlink():
            raise build.BuildError('Refusing symlink in installation path: ' + str(path))
    if target.exists() and any(p.is_symlink() for p in target.rglob('*')):
        raise build.BuildError('Existing Java home contains symlinks')
    shutil.copytree(home, target, dirs_exist_ok=True)
    for executable in (destination / 'bin' / ('java' + major), target / 'bin/java'):
        if executable.is_symlink():
            raise build.BuildError('Refusing symlink executable: ' + str(executable))
        executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(java, executable)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jdk', choices=('21', '25'), required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--boot-jdk', type=Path)
    parser.add_argument('--output', type=Path, help='Producer-owned build cache')
    parser.add_argument('--jobs', type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()
    boot = args.boot_jdk or os.environ.get('OPENJDK_BOOT_JDK_' + args.jdk) or os.environ.get('JAVA_HOME')
    if not boot:
        parser.error('Set JAVA_HOME or OPENJDK_BOOT_JDK_' + args.jdk + ' to a matching host JDK')
    output = (args.output or build.ROOT / 'producer/.build' / ('jdk-' + args.jdk)).absolute()
    subprocess.run([sys.executable, str(build.HERE / 'build.py'), '--jdk', args.jdk,
                    '--target', 'java', '--boot-jdk', str(boot), '--output', str(output),
                    '--jobs', str(args.jobs)], check=True)
    receipt = json.loads((output / 'java.json').read_text())
    home = install(receipt, args.destination, args.jdk)
    print('Installed ' + str(home))


if __name__ == '__main__':
    main()
