// SPDX-License-Identifier: MIT
fn main() {
    let version = std::process::Command::new("/bin/java")
        .args(["-XX:ErrorFile=/tmp/openjdk-error.log", "-version"])
        .status();
    if !matches!(version, Ok(ref status) if status.success()) {
        println!("OPENJDK_GUEST FAIL version {version:?}");
        report_crash();
    }
    let result = std::process::Command::new("/bin/java")
        .args([
            "-XX:ErrorFile=/tmp/openjdk-error.log",
            "-Xlog:gc",
            "-cp",
            "/app",
            "Hello",
            "Scarlet",
            "いちご🍓",
        ])
        .status();
    match result {
        Ok(status) if status.success() => println!("OPENJDK_GUEST PASS child exit=0"),
        other => {
            println!("OPENJDK_GUEST FAIL {other:?}");
            report_crash();
        }
    }
    #[cfg(jar)]
    {
        let jar = std::process::Command::new("/bin/java")
            .args([
                "-XX:ErrorFile=/tmp/openjdk-error.log",
                "-cp",
                "/does/not/exist",
                "-Djava.class.path=/also/missing",
                "-jar",
                "/app/compat.jar",
                "Scarlet",
                "いちご🍓",
                "-Xnot-a-vm-option",
            ])
            .status();
        match jar {
            Ok(status) if status.success() => println!("OPENJDK_GUEST JAR child exit=0"),
            other => {
                println!("OPENJDK_GUEST FAIL JAR {other:?}");
                report_crash();
            }
        }
        let invalid_jar = std::process::Command::new("/bin/java")
            .args(["-jar", "/app/no-main.jar"])
            .status();
        match invalid_jar {
            Ok(status) if status.code() == Some(1) => {
                println!("OPENJDK_GUEST invalid JAR rejected exit=1");
            }
            other => {
                println!("OPENJDK_GUEST FAIL invalid JAR {other:?}");
                report_crash();
            }
        }
    }
    #[cfg(jit)]
    {
        // Force C2 even for trivial getters in the exception/GC tests. The
        // separate Tiered process below exercises normal C1-to-C2 promotion.
        let compiler_options: &[&str] = if cfg!(tiered) {
            &["-XX:CompilationMode=high-only"]
        } else {
            &[]
        };
        let result = std::process::Command::new("/bin/java")
            .args(compiler_options)
            .args([
                "-XX:ErrorFile=/tmp/openjdk-error.log",
                "-Xcomp",
                "-XX:-BackgroundCompilation",
                "-XX:+PrintCompilation",
                "-XX:CompileCommand=compileonly,Jit::*",
                "-XX:CompileCommand=dontinline,Jit::*",
                "-cp",
                "/app",
                "Jit",
            ])
            .status();
        match result {
            Ok(status) if status.success() => println!("OPENJDK_GUEST JIT child exit=0"),
            other => {
                println!("OPENJDK_GUEST FAIL JIT {other:?}");
                report_crash();
            }
        }
        println!("OPENJDK_GUEST JIT stress start");
        let result = std::process::Command::new("/bin/java")
            .args(compiler_options)
            .args([
                "-XX:ErrorFile=/tmp/openjdk-error.log",
                "-Xcomp",
                "-XX:-BackgroundCompilation",
                "-XX:+PrintCompilation",
                "-Xlog:gc",
                "-XX:CompileCommand=compileonly,JitStress::*",
                "-XX:CompileCommand=dontinline,JitStress::*",
                "-cp",
                "/app",
                "JitStress",
            ])
            .status();
        match result {
            Ok(status) if status.success() => println!("OPENJDK_GUEST JIT stress child exit=0"),
            other => {
                println!("OPENJDK_GUEST FAIL JIT stress {other:?}");
                report_crash();
            }
        }
    }
    #[cfg(tiered)]
    {
        println!("OPENJDK_GUEST tiered start");
        let result = std::process::Command::new("/bin/java")
            .args([
                "-XX:ErrorFile=/tmp/openjdk-error.log",
                "-XX:-BackgroundCompilation",
                "-XX:+PrintCompilation",
                "-XX:CompileThresholdScaling=0.1",
                "-Xlog:deoptimization=debug,gc",
                "-XX:CompileCommand=compileonly,Tiered::dispatch",
                "-XX:CompileCommand=compileonly,Tiered::materialize",
                "-XX:CompileCommand=compileonly,Tiered::osr",
                "-XX:CompileCommand=dontinline,Tiered::escape",
                "-cp",
                "/app",
                "Tiered",
            ])
            .status();
        match result {
            Ok(status) if status.success() => println!("OPENJDK_GUEST tiered child exit=0"),
            other => {
                println!("OPENJDK_GUEST FAIL tiered {other:?}");
                report_crash();
            }
        }
    }
    // This disposable validation VM owns its lifecycle; the Java launcher does not.
    unsafe {
        core::arch::asm!("svc #0", inout("x0") 0usize => _, inout("x1") 0usize => _,
            inout("x8") 1000usize => _, clobber_abi("C"));
    }
    std::process::exit(1);
}

fn report_crash() {
    if let Ok(log) = std::fs::read_to_string("/tmp/openjdk-error.log") {
        println!("{log}");
    }
}
