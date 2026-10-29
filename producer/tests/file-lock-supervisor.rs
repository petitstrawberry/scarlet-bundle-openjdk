#[path = "application-supervisor.rs"]
#[allow(dead_code)]
mod application;

use std::os::fd::AsRawFd;

fn lock(file: &std::fs::File, operation: usize) {
    let result: usize;
    unsafe {
        core::arch::asm!("svc #0", inout("x0") file.as_raw_fd() as usize => result,
            in("x1") operation, in("x8") 310usize, clobber_abi("C"));
    }
    assert_eq!(result, 0, "native whole-file lock");
}

fn fixture() {
    let (ready, started) = std::sync::mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let file = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open("/tmp/foreign.lock")
            .unwrap();
        lock(&file, 2 | 4); // LOCK_EX | LOCK_NB
        ready.send(()).unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(15);
        while !std::path::Path::new("/tmp/unlock-request").exists() {
            assert!(
                std::time::Instant::now() < deadline,
                "unlock request timeout"
            );
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        lock(&file, 8); // LOCK_UN
        std::fs::write("/tmp/unlock-ready", b"unlocked").unwrap();
    });
    started.recv().unwrap();
}

fn main() {
    application::run(fixture);
}
