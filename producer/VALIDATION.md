# Validation record — 2026-10-28

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
deoptimizations, recompilation and correct dispatch results. No Minecraft
performance measurements have been made.

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
These checks do not establish Java TCK
compatibility, dynamic JNI support, a complete NIO implementation or Minecraft
execution.
