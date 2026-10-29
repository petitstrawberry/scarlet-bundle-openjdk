use std::io::{BufRead, Write};

fn main() {
    let arguments = std::fs::read_to_string("/app/.java-arguments").unwrap();
    let mut child = std::process::Command::new("/bin/java")
        .args(arguments.split_terminator('\n'))
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .expect("console test process");
    let mut input = child.stdin.take().unwrap();
    for line in std::io::BufReader::new(child.stdout.take().unwrap()).lines() {
        let line = line.expect("console test output");
        println!("{line}");
        if line == "CONSOLE_READY" {
            input.write_all("日本語 stop\n".as_bytes()).unwrap();
            input.flush().unwrap();
        }
    }
    let status = child.wait();
    println!(
        "APPLICATION_GUEST {} {status:?}",
        if status.as_ref().is_ok_and(|s| s.success()) {
            "PASS"
        } else {
            "FAIL"
        }
    );
    unsafe {
        core::arch::asm!("svc #0", inout("x0") 0usize => _, inout("x1") 0usize => _,
            inout("x8") 1000usize => _, clobber_abi("C"));
    }
}
