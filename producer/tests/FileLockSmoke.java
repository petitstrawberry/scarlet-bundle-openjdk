import java.nio.channels.*;
import java.nio.file.*;

public class FileLockSmoke {
    static void require(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }
    public static void main(String[] args) throws Exception {
        Path path = Path.of("/tmp/foreign.lock");
        try (var channel = FileChannel.open(path, StandardOpenOption.READ, StandardOpenOption.WRITE)) {
            require(channel.tryLock() == null, "foreign process lock contention");
            Files.writeString(Path.of("/tmp/unlock-request"), "unlock");
            long deadline = System.nanoTime() + 5_000_000_000L;
            while (!Files.exists(Path.of("/tmp/unlock-ready"))) {
                require(System.nanoTime() < deadline, "foreign unlock timeout");
                Thread.sleep(5);
            }
            try (FileLock held = channel.tryLock()) {
                require(held != null && held.isValid() && !held.isShared(), "exclusive acquisition");
            }
            try (FileLock held = channel.tryLock(0, Long.MAX_VALUE, true)) {
                require(held != null && held.isShared(), "shared acquisition after release");
            }
            try {
                channel.tryLock(1, 1, false);
                throw new AssertionError("range was silently widened");
            } catch (java.io.IOException expected) {}
            try {
                channel.lock();
                throw new AssertionError("blocking lock was silently changed");
            } catch (java.io.IOException expected) {}
        }
        try (var channel = FileChannel.open(path, StandardOpenOption.WRITE);
             FileLock held = channel.tryLock()) {
            require(held != null, "reopen and acquire");
        }
        Files.delete(path);
        System.out.println("FILE_LOCK PASS");
    }
}
