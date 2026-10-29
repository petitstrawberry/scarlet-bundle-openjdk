fn main() {
    // Native init retains the administrative root-view capability at handle 3
    // for PID 1. Mount only ephemeral test state; exec does not pass that
    // CLOEXEC capability to Java. VfsViewMount is native ABI operation 524.
    let result: usize;
    unsafe {
        core::arch::asm!("svc #0", inout("x0") 3usize => result,
            in("x1") c"/tmp".as_ptr(), in("x2") c"tmpfs".as_ptr(),
            in("x3") c"size=128M".as_ptr(), in("x8") 524usize,
            clobber_abi("C"));
    }
    assert_ne!(result, usize::MAX, "mount writable application state");
    let arguments = std::fs::read_to_string("/app/.java-arguments").expect("application arguments");
    let status = std::process::Command::new("/bin/java")
        .current_dir("/tmp")
        .arg("-XX:ErrorFile=/tmp/application-jvm-error.log")
        .args(arguments.split_terminator('\n'))
        .status();
    println!(
        "APPLICATION_GUEST {} {status:?}",
        if status.as_ref().is_ok_and(|s| s.success()) {
            "PASS"
        } else {
            "FAIL"
        }
    );
    if let Ok(log) = std::fs::read_to_string("/tmp/application-jvm-error.log") {
        println!("{log}");
    }
    unsafe {
        core::arch::asm!("svc #0", inout("x0") 0usize => _, inout("x1") 0usize => _, inout("x8") 1000usize => _, clobber_abi("C"));
    }
}
