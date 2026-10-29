#!/usr/bin/env python3
"""Build native JNI test DSOs in the producer Nix shell."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Pinned OpenJDK source tree')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cc = os.environ['SCARLET_NATIVE_CC']
    resource = subprocess.check_output([cc, '-print-resource-dir'], text=True).strip()
    runtime = Path(os.environ['SCARLET_NATIVE_RUNTIME'])
    flags = ['--target=aarch64-unknown-none-elf', '-fPIC', '-O2', '-nostdlib', '-nostdinc',
             '-isystem', resource + '/include', '-isystem', str(runtime / 'include'),
             '-I', str(args.source / 'src/java.base/share/native/include'),
             '-I', str(args.source / 'src/java.base/scarlet/native/include'),
             '-fuse-ld=lld', '-Wl,-shared', '-Wl,-Bdynamic', '-Wl,-z,max-page-size=4096',
             '-Wl,--hash-style=both']
    here = Path(__file__).parent
    for name, source, dependencies in [
        ('libjni_dependency.so', 'jni-dependency.c', []),
        ('libjni_probe.so', 'jni-probe.c', [str(args.output / 'libjni_dependency.so')]),
    ]:
        target = args.output / name
        subprocess.run([cc, *flags, '-Wl,-soname,' + name, str(here / source),
                        *dependencies, '-o', str(target)], check=True)
        with target.open('r+b') as file:
            if file.read(4) != b'\x7fELF':
                raise ValueError('Expected ELF output')
            file.seek(7)
            file.write(b'\x53')
    (args.output / 'invalid.so').write_bytes(b'not an ELF library\n')


if __name__ == '__main__':
    main()
