import java.io.FileOutputStream;
import java.nio.file.*;
import java.util.*;

public class NioFilesSmoke {
    static void require(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        Path nested = root.resolve("nested/日本語");
        Files.createDirectories(nested);
        require(Files.isDirectory(nested), "nested mkdir");
        Path legacy = root.resolve("legacy/child");
        require(legacy.toFile().mkdirs() && legacy.toFile().isDirectory(), "java.io directory creation");
        Files.delete(legacy);
        Files.delete(legacy.getParent());
        Files.createDirectories(nested);
        try {
            Files.createDirectory(nested);
            throw new AssertionError("existing directory was accepted");
        } catch (FileAlreadyExistsException expected) {}
        Path file = nested.resolve("payload");
        try (var stream = new FileOutputStream(file.toFile())) {
            stream.write(new byte[] {1,2,3,4});
        }
        require(Files.size(file) == 4, "file metadata");
        Path channelFile = nested.resolve("channel");
        Files.write(channelFile, new byte[] {5,6,7,8});
        require(Arrays.equals(Files.readAllBytes(channelFile), new byte[] {5,6,7,8}), "NIO byte I/O");
        try (var channel = java.nio.channels.FileChannel.open(channelFile,
                StandardOpenOption.READ, StandardOpenOption.WRITE)) {
            channel.position(2);
            require(channel.write(java.nio.ByteBuffer.wrap(new byte[] {9}), 0) == 1, "positioned write");
            require(channel.position() == 2, "positioned write preserves position");
            channel.truncate(3);
            require(channel.size() == 3 && channel.position() == 2, "truncate and cursor");
            var buffer = java.nio.ByteBuffer.allocateDirect(3);
            require(channel.read(buffer, 0) == 3, "direct positioned read");
            require(buffer.get(0) == 9 && buffer.get(2) == 7, "direct bytes");
        }
        Files.delete(channelFile);
        for (var mode : List.of(StandardOpenOption.SYNC, StandardOpenOption.DSYNC)) {
            Path synchronous = nested.resolve("sync-" + mode);
            Files.write(synchronous, new byte[] {1,2}, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, mode);
            try (var channel = java.nio.channels.FileChannel.open(synchronous,
                    StandardOpenOption.READ, StandardOpenOption.WRITE, mode)) {
                require(channel.write(java.nio.ByteBuffer.wrap(new byte[] {3}), 1) == 1, "synchronous positioned write");
                require(channel.write(new java.nio.ByteBuffer[] {
                    java.nio.ByteBuffer.wrap(new byte[] {4}), java.nio.ByteBuffer.wrap(new byte[] {5})}) == 2,
                    "synchronous vector write");
                channel.truncate(1);
            }
            require(Arrays.equals(Files.readAllBytes(synchronous), new byte[] {4}), "synchronous bytes and truncation");
            var interrupted = java.nio.channels.FileChannel.open(synchronous, StandardOpenOption.WRITE, mode);
            Thread.currentThread().interrupt();
            try {
                interrupted.write(java.nio.ByteBuffer.wrap(new byte[] {6}));
                throw new AssertionError("interrupted synchronous channel remained writable");
            } catch (java.nio.channels.ClosedByInterruptException expectedInterrupt) {
                require(!interrupted.isOpen(), "interrupted synchronous channel closed");
            } finally {
                Thread.interrupted();
                interrupted.close();
            }
            Files.delete(synchronous);
        }
        Path vectorFile = nested.resolve("vectors");
        byte[] expected = new byte[1_200_004];
        for (int i = 0; i < expected.length; ++i) expected[i] = (byte)(i * 31);
        var first = java.nio.ByteBuffer.wrap(expected, 0, 700_001);
        var second = java.nio.ByteBuffer.allocateDirect(expected.length - first.remaining() + 10);
        second.position(5);
        second.put(expected, 700_001, expected.length - 700_001).flip().position(5);
        try (var channel = java.nio.channels.FileChannel.open(vectorFile,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.READ, StandardOpenOption.WRITE)) {
            var sources = new java.nio.ByteBuffer[] {java.nio.ByteBuffer.allocate(0), first, second};
            long written = 0;
            while (first.hasRemaining() || second.hasRemaining()) {
                long before = first.position() + second.position();
                long count = channel.write(sources);
                require(count > 0 && count == first.position() + second.position() - before,
                        "gather write progress and buffer positions");
                written += count;
                require(channel.position() == written, "gather write file position");
            }
            require(written == expected.length && channel.size() == expected.length, "gather write size");
            channel.position(0);
            byte[] actual = new byte[expected.length + 6];
            var head = java.nio.ByteBuffer.wrap(actual, 3, 303_001);
            var tail = java.nio.ByteBuffer.allocateDirect(expected.length - 303_001 + 8);
            tail.position(4).limit(tail.capacity() - 4);
            var targets = new java.nio.ByteBuffer[] {head, java.nio.ByteBuffer.allocate(0), tail};
            long read = 0;
            while (head.hasRemaining() || tail.hasRemaining()) {
                long before = head.position() + tail.position();
                long count = channel.read(targets);
                require(count > 0 && count == head.position() + tail.position() - before,
                        "scatter read progress and buffer positions");
                read += count;
                require(channel.position() == read, "scatter read file position");
            }
            tail.flip().position(4);
            tail.get(actual, 3 + 303_001, expected.length - 303_001);
            require(Arrays.equals(expected, Arrays.copyOfRange(actual, 3, actual.length - 3)), "vector bytes");
            require(actual[0] == 0 && actual[actual.length - 1] == 0, "scatter buffer boundaries");
            require(channel.read(new java.nio.ByteBuffer[] {java.nio.ByteBuffer.allocate(1)}) == -1,
                    "scatter EOF");
        }
        Files.delete(vectorFile);
        Set<String> names = new HashSet<>();
        try (DirectoryStream<Path> entries = Files.newDirectoryStream(nested)) {
            for (Path entry : entries) names.add(entry.getFileName().toString());
        }
        require(names.equals(Set.of("payload")), "directory entries: " + names);
        Path link = nested.resolve("link");
        Files.createSymbolicLink(link, Path.of("payload"));
        require(Files.readSymbolicLink(link).equals(Path.of("payload")), "symlink target");
        Files.delete(link);
        Path renamed = nested.resolve("renamed");
        Files.move(file, renamed);
        require(!Files.exists(file) && Files.size(renamed) == 4, "rename");
        Files.delete(renamed);
        try {
            Files.delete(renamed);
            throw new AssertionError("missing file was accepted");
        } catch (NoSuchFileException missing) {}
        Files.delete(nested);
        Files.delete(nested.getParent());
        Files.delete(root);
        System.out.println("NIO_FILES PASS");
    }
}
