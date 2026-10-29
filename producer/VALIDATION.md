# Validation record

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
