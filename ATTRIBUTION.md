# Licensing and source references

The producer's original code and documentation use **GPL-2.0-only WITH
Classpath-exception-2.0**, as stated in [LICENSE](LICENSE) and [NOTICE](NOTICE).
The MIT notice from earlier versions remains in `LICENSES/MIT-legacy.txt`.

OpenJDK retains its per-file licenses, including GPLv2, the Classpath Exception
where applicable, and the Assembly Exception. Each Java home includes the
upstream `LICENSE`, `ADDITIONAL_LICENSE_INFO`, `ASSEMBLY_EXCEPTION` and
`legal/java.base` notices. See upstream's
[licensing information](https://github.com/openjdk/jdk25u/blob/master/ADDITIONAL_LICENSE_INFO).

The statically linked Scarlet SDK and Scarlet ABI, LLVM C/C++ libraries,
Rust runtime and dependencies, and libffi retain their own licenses. Their
notices are installed under `legal/scarlet-runtime` in the versioned Java home.
Changing the producer's license does not relicense those components.

Every release records exact producer and dependency revisions in `sources.json`.
The producer sources are available from the release tag; the OpenJDK port is
available from the existing `jdk21u` or `jdk25u` fork at the recorded commit.
The index links to immutable source downloads and pinned dependency manifests.
There is no separate source repository or duplicate source archive.

Retain these source references and copyright/license notices when redistributing
the runtime. The bundle's archive checksum identifies the exact binary release;
source commits and build receipts identify its build inputs.
