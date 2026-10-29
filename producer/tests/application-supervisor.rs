fn main() {
    let arguments = std::fs::read_to_string("/app/.java-arguments").expect("application arguments");
    let status = std::process::Command::new("/bin/java")
        .current_dir("/app")
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
