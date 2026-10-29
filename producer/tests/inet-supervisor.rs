// Deterministic resolverd-protocol fixture. This tests JNI -> native libc ->
// Scarlet's resolver IPC, without depending on public DNS or a network device.
#[path = "application-supervisor.rs"]
#[allow(dead_code)]
mod application;

struct Handle(usize);

fn native(number: usize, a: usize, b: usize, c: usize) -> usize {
    let result;
    unsafe {
        core::arch::asm!("svc #0", inout("x0") a => result,
            in("x1") b, in("x2") c, in("x8") number, clobber_abi("C"));
    }
    assert!(
        result <= isize::MAX as usize,
        "Native fixture operation {number}: {result:#x}"
    );
    result
}

impl Drop for Handle {
    fn drop(&mut self) {
        native(102, self.0, 0, 0); // HandleClose
    }
}

fn start_fixture() {
    let (ready, started) = std::sync::mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let server = Handle(native(900, 1, 1, 0)); // SocketCreate: local, stream
        let path = b"/tmp/resolverd.sock";
        native(901, server.0, path.as_ptr() as usize, path.len()); // SocketBind
        native(902, server.0, 64, 0); // SocketListen
        ready.send(()).unwrap();
        loop {
            let client = Handle(native(904, server.0, 0, 0)); // SocketAccept
            let mut request = Vec::new();
            loop {
                let mut buffer = [0; 128];
                let count = native(200, client.0, buffer.as_mut_ptr() as usize, buffer.len());
                request.extend_from_slice(&buffer[..count]);
                if count == 0 || request.contains(&b'\n') || request.len() > 512 {
                    break;
                }
            }
            let request = std::str::from_utf8(&request).unwrap().trim();
            println!("INET_RESOLVER_REQUEST {request}");
            let response = if request == "A many.test" {
                "OK 192.0.2.1 203.0.113.7 192.0.2.1\n"
            } else if request.starts_with("A worker") && request.ends_with(".test") {
                "OK 198.51.100.42\n"
            } else {
                "ERR no A records\n"
            };
            let mut bytes = response.as_bytes();
            while !bytes.is_empty() {
                let count = native(201, client.0, bytes.as_ptr() as usize, bytes.len()); // StreamWrite
                assert!(count > 0, "fixture response progress");
                bytes = &bytes[count..];
            }
        }
    });
    started.recv().expect("resolver listener readiness");
    // A real Native TCP listener exercises the echo-port reachability path.
    let echo = std::net::TcpListener::bind("127.0.0.1:7").expect("echo listener");
    std::thread::spawn(move || {
        loop {
            drop(echo.accept().expect("echo accept"));
        }
    });
    println!("INET_FIXTURE_READY");
}

fn main() {
    application::run(start_fixture);
}
