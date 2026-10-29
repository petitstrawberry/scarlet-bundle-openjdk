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
        } catch (NoSuchFileException expected) {}
        Files.delete(nested);
        Files.delete(nested.getParent());
        Files.delete(root);
        System.out.println("NIO_FILES PASS");
    }
}
