#!/usr/bin/env python3
"""Build an isolated Scarlet guest and execute the native OpenJDK smoke test.

Run in this producer’s Nix shell after build.py --target java. Kernel and init
are explicit input artifacts; no Scarlet checkout is required.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWNER = 'scarlet-openjdk-guest-v1\n'

def jar_fixtures(classes, destination):
    """Keep JAR-only classes off the loose class path to detect loader regressions."""
    with zipfile.ZipFile(destination/'compat.jar', 'w', zipfile.ZIP_DEFLATED) as jar:
        jar.writestr('META-INF/MANIFEST.MF',
                     'Manifest-Version: 1.0\r\nMain-Class: JarMain\r\n'
                     'Class-Path: depen\r\n dency.jar\r\n\r\n')
        for path in sorted(classes.glob('JarMain*.class')):
            jar.write(path, path.name)
        jar.writestr('payload.bin', bytes(i % 251 for i in range(98317)))
    with zipfile.ZipFile(destination/'dependency.jar', 'w', zipfile.ZIP_DEFLATED) as jar:
        jar.write(classes/'fixture/Dependency.class', 'fixture/Dependency.class')
    with zipfile.ZipFile(destination/'no-main.jar', 'w', zipfile.ZIP_DEFLATED) as jar:
        jar.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\r\n\r\n')

def run(command, log, env):
    print('Running '+str(command[0])+'; log: '+str(log), flush=True)
    with log.open('w') as stream:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(errors='replace')[-5000:])
        raise SystemExit(f'Failed: {log}')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True, help='Scarlet Linux-boot AArch64 Image')
    p.add_argument('--init', type=Path, required=True, help='Scarlet native init executable')
    p.add_argument('--loader', type=Path, help='scarlet-ld, required for loader-linked Java')
    p.add_argument('--build-receipt', type=Path, required=True)
    p.add_argument('--boot-jdk', type=Path, required=True)
    p.add_argument('--output', type=Path, default=ROOT/'producer/.build/guest')
    p.add_argument('--accel', choices=('tcg','hvf'), default='tcg')
    p.add_argument('--qemu', default='qemu-system-aarch64', help='QEMU executable or PATH name')
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--memory', default='1G', help='Guest RAM (use at least 2G to exercise default G1 selection)')
    a = p.parse_args()
    receipt = json.loads(a.build_receipt.read_text())
    a.jni = receipt.get('elf', {}).get('interpreter') == '/bin/scarlet-ld'
    a.openjdk_source = Path(receipt['inputs']['sources']['openjdk'])
    if a.jni and (not a.loader or not a.loader.is_file()):
        p.error('Loader-linked Java requires --loader pointing to scarlet-ld')
    a.jar = Path(receipt['java_home']).name == 'openjdk-25'
    a.jit = receipt.get('inputs', {}).get('jvm_variant', 'zero') != 'zero'
    a.tiered = receipt.get('inputs', {}).get('jvm_variant') == 'tiered'
    java, java_home = Path(receipt['artifact']), Path(receipt['java_home'])
    if not java.is_file() or not (java_home/'lib/modules').is_file():
        p.error('Receipt must point to a compiled native Java runtime')
    if a.output.is_symlink(): p.error('Output must not be a symlink')
    o = a.output.absolute()
    o.mkdir(parents=True, exist_ok=True)
    marker = o/'.scarlet-openjdk-guest'
    if marker.exists():
        if marker.is_symlink() or marker.read_text() != OWNER: p.error('Unrecognized output owner')
    else:
        if any(o.iterdir()): p.error('Output must be empty or owned by this helper')
        marker.write_text(OWNER)
    import fcntl
    with marker.open() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build_and_run(a, o, java, java_home)

def build_and_run(a, o, java, java_home):
    env = os.environ.copy()
    env.pop('RUSTFLAGS', None)
    env.pop('CARGO_ENCODED_RUSTFLAGS', None)
    run(['rustc','--edition=2024','--target=aarch64-unknown-scarlet','-C','panic=abort',
         '-C','target-feature=+crt-static','-C','relocation-model=static',
         '-C','link-arg=--no-dynamic-linker','-O',HERE/'supervisor.rs','-o',o/'supervisor']
        + (['--cfg','jit'] if a.jit else []) + (['--cfg','jar'] if a.jar else [])
        + (['--cfg','tiered'] if a.tiered else [])
        + (['--cfg','jni'] if a.jni else []),o/'supervisor-build.log',env)
    run([a.boot_jdk.resolve()/'bin/javac','-encoding','UTF-8','-d',o/'classes',
         HERE/'Hello.java',HERE/'Jit.java',HERE/'JitStress.java',HERE/'Tiered.java']
        + ([HERE/'Jni.java'] if a.jni else []),o/'javac.log',env)
    if a.jar:
        run([a.boot_jdk.resolve()/'bin/javac','-encoding','UTF-8','-d',o/'jar-classes',
             HERE/'JarMain.java',HERE/'fixture/Dependency.java'],o/'jar-javac.log',env)
        jar_fixtures(o/'jar-classes', o/'classes')
    if a.jni:
        run([sys.executable, HERE/'build-jni.py', '--source', a.openjdk_source,
             '--output', o/'jni-libraries'], o/'jni-build.log', env)
    run([sys.executable,HERE/'run-java.py','--kernel',a.kernel.resolve(),'--init',a.init.resolve(),'--java',java,
         '--java-home',java_home,'--supervisor',o/'supervisor','--classes',o/'classes',
         '--output',o/'java-qa','--accel',a.accel,'--qemu',a.qemu,'--timeout',a.timeout,'--memory',a.memory]
        + (['--jit'] if a.jit else []) + (['--tiered'] if a.tiered else [])
        + (['--loader', a.loader.resolve(), '--jni-libraries', o/'jni-libraries'] if a.jni else []),o/'run.log',env)
    print('Native OpenJDK guest PASS: '+str(o/'java-qa/validation.json'))

if __name__ == '__main__':
    main()
