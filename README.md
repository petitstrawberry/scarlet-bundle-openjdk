# scarlet-bundle-openjdk

OpenJDK runtime bundles for native Scarlet AArch64. They use Scarlet's native
ABI (ELF OSABI `0x53`) and include HotSpot and the `java.base` module.

| Bundle | Default VM | Executable | Java home |
| --- | --- | --- | --- |
| `bundles/openjdk-21` | C1 | `/bin/java` | `/usr/lib/jvm/openjdk-21` |
| `bundles/openjdk-25` | C1 + C2 tiered compilation | `/bin/java` | `/usr/lib/jvm/openjdk-25` |

Select exactly one OpenJDK bundle per image; the bundles are mutually exclusive.
Run it with `java`, for example `java --version`. Each Java home also contains
`bin/java`.

## Use a bundle

Add an explicit layer to the consuming project's image configuration:

```toml
[[images.rootfs.layers]]
kind = "bundle"
source = { git = "https://github.com/petitstrawberry/scarlet-bundle-openjdk", rev = "<pinned-bundle-commit>" }
subdir = "bundles/openjdk-25"
```

Select `bundles/openjdk-21` for Java 21. Each bundle references a CI-built
release archive by fixed URL and SHA-256. Image composition downloads and
extracts it; consumers do not need a host JDK or the OpenJDK build toolchain.
Use a repository revision containing the desired release pin.

The launcher accepts VM options, `-cp`/`-classpath`/`--class-path`,
`-version`/`--version` and standard `static void main(String[])` entry points.
Java 25 also supports `-jar`, including manifest `Class-Path` dependencies.
`JAVA_HOME` can override the compiled-in Java home. The default heap is
16 MiB initial / 64 MiB maximum; the default class path is `.`.

## Supported scope

Java 25 includes C1 and C2 tiered compilation, Serial GC, platform threads,
reflection, method handles, JAR/ZIP reading, direct buffers, and initial NIO
file metadata/path operations. Java 21 retains the earlier C1 runtime;
JAR/NIO compatibility has only been established for the Java 25 recipe.

This is a headless `java.base` port. Dynamic JNI libraries, networking, NIO
channels/selectors, directory enumeration/mutation, AWT, JVMTI, JFR, virtual
threads/continuations, process creation and module-mode launch remain
unavailable or unported. It is not a complete or TCK-certified JDK.

See [the validation record](producer/VALIDATION.md) for tested behavior,
source and executable checksums, and the limits of those checks. CI compilation
and archive verification are distinct from execution in a Scarlet guest.

## CI and releases

The **Build OpenJDK runtimes** workflow builds both recipes on a native ARM64
Linux runner with the pinned Nix environment. It audits the native ELF,
packages `/bin/java` and the selected Java home, includes license notices and source
references, and verifies the archive and its candidate bundle manifest.
Build results are available as `openjdk-21` and `openjdk-25` workflow artifacts.

Producer changes on `main` publish a new experimental GitHub Release and
update both bundle pins after the uploaded assets have been downloaded and
checksum-verified. Existing releases are never overwritten. Documentation,
bundle-pin and test-only changes do not start another runtime build.

A manual build can select a fresh version:

```sh
gh workflow run build.yml -f version=v0.1.100 -f publish=false
```

`publish=false` produces workflow artifacts only. Publication is restricted to
`main` in CI. A release contains runtime archives, SHA-256 inventories, build
receipts and source indexes. Source indexes point to the existing repositories
at fixed revisions; the producer's source is also available from the release
tag. No separate source repository or duplicate source archive is created.

## Build from source

Maintainers can build either recipe independently of a Scarlet kernel checkout:

```sh
nix develop .#jdk25
python3 producer/build.py --jdk 25 --target java --boot-jdk "$JAVA_HOME"
```

Use `.#jdk21` and `--jdk 21` for Java 21. Java 25 defaults to `tiered`;
`--jvm-variant c1` and `--jvm-variant zero` select the other configurations.
The tiered profile requires Java 25 and excludes JVMCI.

The receipt at `producer/.build/jdk-25/java.json` identifies the executable and
Java home. Source archives, producer helpers, toolchain and boot JDK inputs
are recorded in the build identity. Edited prepared sources are rejected.
Use `--output` for a separate build directory. To install a local build into an
explicit image stage, use `producer/bundle.py --jdk 25 --destination /path/to/stage`.

OS port changes belong in [jdk25u/scarlet-25](https://github.com/petitstrawberry/jdk25u/tree/scarlet-25)
or [jdk21u/scarlet-21](https://github.com/petitstrawberry/jdk21u/tree/scarlet-21).
Update the fork commit, archive URL and SHA-256 in `versions/<major>/sources.json`
after publishing the port change.

## Validate in Scarlet

Supply a Scarlet AArch64 Linux-boot Image and native init with the native memory
and synchronous-fault ABI used by HotSpot:

```sh
python3 producer/tests/validate.py \
  --build-receipt producer/.build/jdk-25/java.json \
  --boot-jdk "$JAVA_HOME" \
  --kernel /path/to/Scarlet-Image \
  --init /path/to/native-init
```

The test uses an isolated diskless VM and records input checksums and results.
TCG is the default. For HVF, use `--accel hvf --qemu /path/to/compatible/qemu`;
the pinned stock QEMU has an HVF initialization issue on the validation macOS
host. Native memory/fault requirements and guest results are described in
[the validation record](producer/VALIDATION.md).

Host checks require Python 3.11 or newer:

```sh
python3 -m unittest discover -s producer/tests -p 'test_*.py'
```

## License

Original producer code and documentation are licensed under **GPLv2 with the
Classpath Exception**. OpenJDK and other dependencies retain their upstream
licenses and notices. See [LICENSE](LICENSE), [NOTICE](NOTICE) and
[ATTRIBUTION.md](ATTRIBUTION.md).
