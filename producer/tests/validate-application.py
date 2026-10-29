#!/usr/bin/env python3
"""Run an application payload on native Java in an isolated AArch64 HVF guest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def archive(entries, target):
    with target.open('wb') as output:
        for index, (name, mode, data) in enumerate([*entries, ('TRAILER!!!', 0, b'')], 1):
            encoded = name.encode() + b'\0'
            fields = [index, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0]
            header = b'070701' + ''.join(f'{v:08x}' for v in fields).encode()
            output.write(header + encoded)
            output.write(b'\0' * (-(len(header) + len(encoded)) % 4))
            output.write(data)
            output.write(b'\0' * (-len(data) % 4))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel', 'init', 'loader', 'java', 'java-home', 'app', 'arguments', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--qemu', required=True)
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--expect', required=True, help='Application-specific success marker')
    a = p.parse_args()
    args = json.loads(a.arguments.read_text())
    if not isinstance(args, list) or not args or any(not isinstance(v, str) or '\n' in v or '\r' in v or '\0' in v for v in args):
        p.error('--arguments must contain a nonempty JSON array of single-line strings')
    if (a.app / '.java-arguments').exists():
        p.error('Application payload uses the reserved .java-arguments name')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.pop('RUSTFLAGS', None); env.pop('CARGO_ENCODED_RUSTFLAGS', None)
    with (out / 'supervisor-build.log').open('w') as log:
        subprocess.run([env.get('SCARLET_RUSTC', 'rustc'), '--edition=2024', '--target=aarch64-unknown-scarlet',
            '-C', 'panic=abort', '-C', 'target-feature=+crt-static', '-C', 'relocation-model=static',
            '-C', 'link-arg=--no-dynamic-linker', '-O', str(HERE / 'application-supervisor.rs'), '-o', str(out / 'supervisor')],
            env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    entries = {name: (0o40755, b'') for name in ('bin', 'app', 'dev', 'etc', 'tmp', 'root', 'mnt', 'mnt/newroot')}
    inputs = {'kernel': sha(a.kernel), 'arguments': args}
    def add(path, name, executable=False):
        if path.is_symlink() or not path.is_file(): raise ValueError('Expected regular input: ' + str(path))
        for parent in Path(name).parents:
            if str(parent) != '.': entries[parent.as_posix()] = (0o40755, b'')
        entries[name] = (0o100755 if executable else 0o100644, path.read_bytes())
        inputs[name] = sha(path)
    for path, name in ((a.init, 'init'), (a.java, 'bin/java'), (a.loader, 'bin/scarlet-ld'), (out / 'supervisor', 'bin/application-test')):
        add(path, name, True)
    for base, target in ((a.java_home, 'usr/lib/jvm/' + a.java_home.name), (a.app, 'app')):
        for path in sorted(base.rglob('*')):
            if path.is_symlink(): raise ValueError('Symlink in payload: ' + str(path))
            if path.is_file(): add(path, target + '/' + path.relative_to(base).as_posix())
    entries['app/.java-arguments'] = (0o100644, ('\n'.join(args) + '\n').encode())
    image = out / 'initramfs.cpio'; archive([(n, *v) for n, v in sorted(entries.items())], image)
    command = [a.qemu, '-machine', 'virt,gic-version=3', '-accel', 'hvf', '-cpu', 'host', '-m', '4G', '-smp', '4',
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none', '-no-reboot',
        '-kernel', str(a.kernel.resolve()), '-initrd', str(image), '-append', 'console=ttyAMA0 init.exec=/bin/application-test']
    timed_out = False
    with (out / 'qemu.log').open('w') as log:
        try: status = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout).returncode
        except subprocess.TimeoutExpired: timed_out, status = True, None
    log = (out / 'qemu.log').read_text(errors='replace')
    passed = status == 0 and not timed_out and 'APPLICATION_GUEST PASS' in log and a.expect in log
    result = {'result': 'PASS' if passed else 'FAIL', 'inputs': inputs, 'command': command, 'qemu_exit': status,
              'timed_out': timed_out, 'expected_marker': a.expect, 'log_sha256': sha(out / 'qemu.log')}
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['result'], out / 'validation.json')
    if not passed: raise SystemExit(1)

if __name__ == '__main__': main()
