# Validation record

## 2026-10-31 — Java 25 G1 collector

The Java 25 C1 and tiered profiles now include G1 alongside Serial GC.
The launcher leaves collector selection to HotSpot ergonomics and accepts an
explicit collector flag without a conflicting implicit Serial flag. Java 21
and Zero retain their existing Serial-only build profiles.

A fresh producer build used fork commit
`4225128a91a9b6145d9a98fcab3cc0eba25321ec`, whose tree matches the current
`scarlet-25` head `0b21d8d828cf9a4289c7c6bafa78cac6165606f8`.
Native Java SHA-256:
`6cda456566d988ea57df09f2f844c9d8b277cdf2c41c31db9f48b52d09d0b5cc`.
The ELF audit passed. All 43 producer host checks passed in the pinned Nix
shell. The earlier system-Python invocation could not import `tomllib`;
that environment failure is retained in its separate log.

The existing native guest suite passed under AArch64 HVF with four CPUs and
4 GiB RAM. The log confirms G1 selection, 128 MiB of allocation, four-thread
compiled-root survival across eight full collections, implicit exception
recovery, C1/C2 promotion, OSR, deoptimization, JAR loading and dynamic JNI
with `-Xcheck:jni`. The guest-memory option allows this suite to exercise
HotSpot's server-class collector ergonomics; its default remains 1 GiB.
The evidence is in `producer/artifacts/g1-native-qa/`.

An external graphical application completed a 180.210-second world observation
with the new runtime, four CPUs, 8 GiB guest RAM and an unchanged
`-Xms256m -Xmx1536m` heap. The existing graphics runtime and the 100-to-160-second
frame capture window were unchanged. Complete standard safepoint records show:

| Collector | Records | Median | P95 | Maximum | Stops over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Serial, preceding run | 74 | 278.818 ms | 564.364 ms | 829.946 ms | 55 |
| G1 | 75 | 19.521 ms | 65.311 ms | 454.893 ms | 1 |

The G1 run exercised concurrent marking and mixed collections and exited
normally. Its slowest recorded safepoint was a remark pause. A 491.706 ms
frame still remained, including 437.719 ms outside the classified graphics
calls. This does not establish that notification stalls are fixed. User
movement differed between runs, so these are observed pause distributions,
not a controlled FPS comparison. UART-interleaved partial records may be
omitted. The legacy application verifier's five-minute stability criterion
was not met by this intentionally unchanged three-minute observation.
The application logs and input hashes are in
`producer/artifacts/client-validation/26.3/launch-20261030/hvf-main-requirements-112-g1-jvm-pauses/`.

A repeated launch exposed a native futex registration race: a broadcast could
wake existing waiters after a new thread checked its word but before that thread
joined the wait queue. Scarlet now rechecks the word after registration for both
timed and untimed waits. The existing G1/C2/JNI guest suite passed on the fixed
kernel. The first graphical retry accidentally used a kernel without the pending
GPU capability changes and failed device selection; it is retained as a failure.
The subsequent retry used the integrated GPU-capability and graphics-optimization
sources plus the futex fix, entered the world and exercised concurrent/mixed G1
collections. Manual feedback reported improved notification stutter. This is
subjective confirmation, not a controlled FPS comparison or a claim that all
stalls are resolved. Evidence: `g1-native-qa-futex/` and application attempts
`113-g1-jvm-pauses-repeat`, `114-g1-futex-wake`, and `115-g1-futex-integrated`
under the validation directory above (each prefixed `hvf-main-requirements-`).

## 2026-10-29 — application startup and shutdown

Fork commit `4225128a91a9b6145d9a98fcab3cc0eba25321ec` adds the Native
NIO TCP/poll/pipe backend, interface enumeration, whole-file nonblocking locks,
synchronous file-channel writes, JavaBeans platform classes and management
library registration. The SDK dependency is
`515e5e47eec47b2da559e8faef346fee9dc0a2bf`. Its Native runtime build passed,
as did all 200 freestanding C/C++ header checks on AArch64 and RV64.

The development build compiled a fresh C1+C2 VM with management enabled,
the selected Java modules, and all Native libraries. It reused the existing
launcher/support objects and configured-build staging directory; it is a local
development image, not a CI release artifact. Native Java SHA-256:
`086ecf74085b08792c51eaaddb6f159845998ae6b2881fa79f3ebefa2d350de7`.
The final module image SHA-256 is
`d2beb8a9b520575fe89ef4f437a528da43d0511c2a950075b09d0cd752b21f25`.
The kernel, init and loader are the explicit artifacts recorded below.

AArch64 HVF checks passed:

- Real JMM runtime arguments, start time, heap usage/limits, thread counts,
  memory pools and changing GC counters.
- JavaBeans events/introspection and ZIP filesystem reads, including Unicode.
- Foreign-process whole-file lock contention, shared/exclusive acquisition,
  release/reopen, and rejection of unsupported ranges/blocking calls without
  leaving a provisional Java lock-table entry.
- SYNC/DSYNC scalar, positioned and vector writes, truncation, interrupt/close
  behavior, and legacy `java.io.File.mkdirs`.
- Selector wakeup, nonblocking pipes, loopback TCP connection/accept/readiness,
  scatter/gather payloads and peer addresses under `-Xcheck:jni`.
- A real isolated virtio NIC's name/index lookups, MTU and fixed test MAC.
- Buffered UTF-8 console input through a Native pipe and closed-stream errors.
- The complete C2/GC/deoptimization/JAR/JNI regression suite on the final image.

An unmodified external dedicated-server JAR (SHA-1
`64bb6d763bed0a9f1d632ec347938594144943ed`) created a world, reached its
ready message, accepted `stop` on piped stdin, saved all dimensions and exited
with status zero. This run used a diskless guest, loopback binding, no NIC,
and online authentication enabled. It does not establish external DNS/TLS,
player login, multiplayer sessions, client rendering or persistence across VM
restarts. The startup/shutdown run used the same native executable and module
image `385a61afc833c3b464ee5b74d3c3ff6d6192a42ba1a8e86711efab167554c735`;
the subsequent module rebuild only adjusted source indentation.

Logs and input manifests are retained locally in
`producer/artifacts/app-validation/`, including `management-native-1`,
`application-resources-2`, `whole-file-lock-3`, `synchronous-files-1`,
`interfaces-network-2`, `console-input-1`, `application-c2-qa` and
`server-start-accepted-4`. Earlier failed attempts are retained separately.
All 43 producer host tests passed. No graphical toolkit, blocking/range lock,
IPv6, multicast or complete socket compatibility claim is made.

## 2026-10-29 — IPv4 address resolution

Fork commit `5475cd6a2fcc749dc8a3e32ff449aa2f0cf3da15` adds the Scarlet
`libnet` backend. The producer selects the shared InetAddress class initializers
and the platform resolver implementation, links the archive, and registers its
JNI exports in the built-in library table. The local development build reuses
the verified unchanged C2 VM archive described below; it is not a release build.
Native Java SHA-256:
`2c691f17a67dcce2cbfd448c11137ff24d1133c12ce8c39a730b77e76eb2b45d`.
The module image SHA-256 remains
`02862d283152451affca0e5ffca9651d437b3a9181ca0f363644b1dfdf230960`.

`InetAddressSmoke` passed under AArch64 HVF with `-Xcheck:jni`, both with hostname
information enabled in exception messages and with it excluded. It verifies
native IPv4 capability probing, IPv4 backend selection, IPv6 value initialization,
local hostname fallback, native numeric resolution, ordered multi-address
results with duplicates removed, retained hostnames, negative/error mapping,
reverse-lookup numeric fallback, and four concurrent resolver callers. A real
Native TCP listener on loopback port 7 verifies the reachability fallback;
an unsupported explicit TTL reports an IOException. No JNI warnings occurred.

`inet-supervisor.rs` provides a deterministic resolverd-protocol test service,
so named lookups exercise JNI, native libc, Rust std and Scarlet local-socket
IPC without depending on external DNS. It is a test fixture, not a replacement
resolver. Invoke `validate-application.py` with
`--supervisor producer/tests/inet-supervisor.rs`, a payload containing the compiled
smoke class, and arguments `-Xcheck:jni`,
`--add-opens=java.base/java.net=ALL-UNNAMED`, `-cp`, `/app`, `InetAddressSmoke`,
`native` (or `native-private` for excluded hostname information).

The file/NIO and runtime-resource regressions also passed on this image.
An unmodified external server JAR passed InetAddress initialization and reached
logging configuration. Its next fatal failure is the missing
`java.beans.PropertyChangeEvent` class; optional management/JNDI lookups also
report unavailable modules. That application run remains a failure.

Receipts and logs are preserved locally in
`producer/artifacts/app-validation/inet-final/`, `inet-private-final/`,
`inet-nio-final/`, `inet-resources-final/`, and `inet-server-final/`.
The first fixture attempt exposed a test-listener lifetime error; it was fixed
before the passing runs and is not counted as a runtime pass.
All 43 producer host tests passed. This work does not enable Java socket APIs,
IPv6 transport or native PTR resolution, which the current libc lacks.

## 2026-10-29 — native NIO and runtime resources

The Java 25 native library snapshot committed as
`a7c7484172adb6e2fdfc91f3c911f6eba7d98bcc` passed application tests under
AArch64 HVF with the kernel and loader recorded below. The development link
reused the existing C2 VM archive after verifying that `src/hotspot` has the
same Git tree as `27cf2dbd8fca4c21daf9f64885ee56ff780854f0`. It rebuilt the
native libraries and built-in JNI table and packaged the updated platform
classes. This local development image is not a CI release artifact.

Native Java SHA-256:
`73022095254a8bfd14359fc1296582df3a110c1cd7c1c5816ea1b3f2d1154eeb`.
Module image SHA-256:
`02862d283152451affca0e5ffca9651d437b3a9181ca0f363644b1dfdf230960`.
The image includes `java.base`, `java.logging`, `java.xml` and `jdk.unsupported`,
with generated configuration, time-zone data, CA certificates and legal notices.

`NioFilesSmoke` passed directory creation/listing, Unicode paths, symlinks,
rename/delete and error mapping, file-channel positioned/direct I/O,
truncation, and mixed heap/direct scatter/gather transfers larger than 1 MiB.
It checks transferred bytes, partial-transfer buffer positions, file cursors
and EOF. `RuntimeResourcesSmoke` passed SHA-256, Asia/Tokyo rules, loading
110 CA certificates, XML parsing and logger initialization.

The application runner also unpacked an unmodified external server JAR and
reached its main class and XML logging configuration. That run failed at the
unimplemented `java.net.InetAddress.init` entry point; it is not counted as a
successful application launch. The runner requires an application marker as
well as exit status because an exception in an application-created thread
can leave the JVM's exit status at zero.

Logs and SHA-256 input manifests are retained locally in
`producer/artifacts/app-validation/local-nio-final/`, `local-resources-3/`,
and `local-server-3/`. All 43 producer host tests also passed. The tests in
this record used HVF only; CI independently rebuilds the pinned full runtime.

## 2026-10-29 — native JNI loading

Java 25 was rebuilt from fork commit
`27cf2dbd8fca4c21daf9f64885ee56ff780854f0` with the pinned Nix toolchain.
The executable is an AArch64 Scarlet PIE using `/bin/scarlet-ld`; its only
undefined symbols are `dlopen`, `dlsym`, `dlclose` and `dlerror`. It has no
DT_NEEDED libraries, text relocations, symbol versions or RELR relocations.

The local Java SHA-256 is
`f8384ea1aaf5ddd30458742130263d292555bdeaa3940801408fdef1394aabd1`.
The full suite passed under HVF, including `java --version`, the previous
JAR/NIO, C1/C2, deoptimization and GC checks. Dynamic JNI tests run with
`-Xcheck:jni`; the log also requires C2 level 4 compilation of `Jni::callback`.
They exercise JNI_OnLoad and RegisterNatives, dependent shared libraries,
constructors, malloc/free, Java callbacks, arrays and DirectBuffer access,
JNI exceptions, missing symbols, missing/invalid libraries, four Java threads,
and a pthread that attaches to the VM, calls Java and detaches.

The interpreter was built from Scarlet commit
`602e4359884155006693566f361a2b4b42392f05`, with SHA-256
`b7a709906cb79d637579f6f5fbcfdd856aed5ed7fa11be1c2a07ee01e5bf29b2`.
The kernel is the same explicit artifact as the baseline below.
`validate.py --loader <scarlet-ld>` builds the JNI fixtures and includes them
in the guest automatically for loader-linked Java receipts.

Two initial builds exposed non-PIC built-in symbol tables and a legacy
libjava process-handle token. These were fixed; the failed runs are not
counted as passes. Host regression tests: 43 passed. Local logs and receipts
are retained in `producer/artifacts/jni-loader/`. These tests do not establish
DSO TLS, overlapping loader operations, physical unloading, or compatibility
with libraries built for another operating system.

## 2026-10-28 — static runtime


The results below used the earlier `java21`/`java25` installation layout.
Current bundles provide `/bin/java` and are mutually exclusive; select one
OpenJDK version per image.

These results come from the independent producer's own pinned Nix environments.
The kernel and native init were supplied as explicit artifacts. No Scarlet
checkout was used to build either JDK or to compose the bundle image.

| Recipe / profile | Source fork commit | Native Java SHA-256 | Guest |
| --- | --- | --- | --- |
| 21 / C1 | `0717bf3566f846527897e2c4fe22a1340718b9a3` | `5301247dea874ab8d53b2ddb8189f14b5916cb6391e5d56e96714ceec4402611` | TCG |
| 25 / C1 baseline | `39d6c28044976b5c9b04cf261152391f6336940c` | `e607f9ca4cf2a9abad1b3198e11917c4db823eb8de6af1b469494317c362c738` | TCG and HVF |
| 25 / C1+C2 (default) | `d6c39082a7c743784f13424938b576a352357d75` | `58da53c47fec152b3af3b9ed80d1681b4ce30bd2968e76f413256bf2b10276fb` | TCG and HVF |

All native executables passed ELF auditing (AArch64, Scarlet OSABI 0x53,
static, no dynamic interpreter). The C1 baselines passed version reporting,
UTF-8 arguments, four-thread atomics/TLS, a 128 MiB Serial GC workload, file IO,
C1 compilation, implicit null faults and stack overflow recovery, and the
four-thread compiled-root stress test with eight requested full collections.

The Java 25 runs additionally passed manifest JAR launch with an independent
dependency JAR, reflection, method handles, dynamic proxies, compressed resource
reading, direct buffers, NIO metadata/path operations and missing-file errors.
A JAR without Main-Class was rejected with exit 1 and its expected diagnostic.
Java 21 does not yet provide that NIO backend; the JAR test is intentionally
limited to the 25 recipe.

The final C1+C2 binary was rebuilt from the published fork archive and passed
the complete Java 25 suite under both TCG and HVF. The exception and compiled
root stress processes used `CompilationMode=high-only`, with level 4 compilation
required for arithmetic, getters, recursion and the frame holding GC roots.
They recovered from null and stack guard faults and completed eight full GCs
with all four worker threads and their live objects intact.

A separate normal-tiered process produced level 3 then level 4 compilations for
`Tiered::dispatch` and `Tiered::materialize`, and level 4 OSR for `Tiered::osr`.
Its log recorded a level 4 `unstable_if` uncommon trap in `materialize`;
the object state and its survival across a subsequent full GC were checked.
Loading a second interface implementation also produced level 4 `class_check`
deoptimizations, recompilation and correct dispatch results.

For the earlier C1 baseline, the actual `cargo scarlet image` command consumed `bundles/openjdk-25` as an
external local bundle, invoked its source build, and produced a newc image.
Both versioned Java executable paths and the module image were checked in the
resulting archive. The installed Java SHA-256 matches the Java 25 C1 guest results above.
No `/bin/java` was installed. The image SHA-256 was
`0776945325d1c8be27b90835e64fe7a3e24741bc39d5702c341dc3afbd72e3c4`.

The updated Java 25 bundle build script was also invoked with an explicit
image stage. It selected the default tiered build and installed the exact
guest-tested C2 executable at both versioned paths, without creating `/bin/java`.

Thirty-four host tests passed, including concurrent version installation without
replacing a project's default Java, checksum/version rejection and symlink
isolation, compiler profile selection and rejection of missing C2 compilation
or deoptimization evidence. The native supervisor passed rustfmt, and bundle shell scripts
passed syntax checking.

TCG uses the stock QEMU from this repository's Nix shell. On this macOS host,
that QEMU aborts during HVF host initialization with an SMCR_EL1 assertion.
The successful HVF run explicitly selected QEMU 11.1.0-scarlet with `--qemu`.
The failed stock-HVF attempt is not counted as a guest pass.

The input kernel SHA-256 was
`f474d06aeb849efbb7d0e13009c6d61537dd9b0656f2b1a2b8485fe9726c0d16`.
Scarlet's separate AArch64 and RISC-V64 kernel suites passed 1,576 and 1,590
checks after removal of its JDK producer tools. Kernel ABI changes are reviewed
in [Scarlet PR #612](https://github.com/petitstrawberry/Scarlet/pull/612).

Local receipts, logs and installable runtime trees are preserved under the
ignored `producer/artifacts/` directory, with the C2 results in `c2-tiered/`.
These checks do not establish Java TCK compatibility, dynamic JNI support or
a complete NIO implementation.
