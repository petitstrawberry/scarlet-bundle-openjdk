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
