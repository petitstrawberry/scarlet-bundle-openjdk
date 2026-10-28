/* SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0 */
import java.io.InputStream;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;

/** Exercises APIs used by launchers and native-library wrappers, inside a JAR. */
public class JarMain {
    public interface Greeting { String greet(String name); }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Throwable {
        check(args.length == 3 && args[0].equals("Scarlet") && args[1].equals("いちご🍓")
            && args[2].equals("-Xnot-a-vm-option"), "JAR application arguments");
        check(System.getProperty("java.class.path").equals("/app/compat.jar"), "JAR class path");
        // Only dependency.jar contains this class. The manifest's folded
        // Class-Path entry must resolve it relative to compat.jar.
        Class<?> dependency = Class.forName("fixture.Dependency");
        check(dependency.getMethod("greet", String.class).invoke(null, "Scarlet")
            .equals("Hello Scarlet"), "reflection across dependency JAR");
        Object instance = dependency.getConstructor(int.class).newInstance(73);
        check(dependency.getField("value").getInt(instance) == 73, "reflective construction/field");
        var greet = MethodHandles.publicLookup().findStatic(dependency, "greet",
            MethodType.methodType(String.class, String.class));
        check(((String) greet.invokeExact("JIT")).equals("Hello JIT"), "method handle");
        Greeting proxy = (Greeting) Proxy.newProxyInstance(JarMain.class.getClassLoader(),
            new Class<?>[] { Greeting.class }, (object, method, values) -> greet.invoke(values[0]));
        check(proxy.greet("Proxy").equals("Hello Proxy"), "dynamic proxy");
        System.out.println("OPENJDK_COMPAT reflection and dependency JAR passed");

        try (InputStream resource = JarMain.class.getResourceAsStream("/payload.bin")) {
            check(resource != null, "compressed JAR resource");
            byte[] buffer = new byte[3071];
            int total = 0, size;
            while ((size = resource.read(buffer)) != -1) {
                for (int i = 0; i < size; ++i)
                    check((buffer[i] & 255) == (total + i) % 251, "resource byte " + (total + i));
                total += size;
            }
            check(total == 98317, "complete ZIP decompression");
        }
        ByteBuffer memory = ByteBuffer.allocateDirect(98317).order(ByteOrder.LITTLE_ENDIAN);
        check(memory.isDirect(), "native direct buffer");
        for (int offset = 0; offset + 8 <= memory.capacity(); offset += 8)
            memory.putLong(offset, 0x123456789abcdef0L ^ offset);
        for (int offset = 0; offset + 8 <= memory.capacity(); offset += 8)
            check(memory.getLong(offset) == (0x123456789abcdef0L ^ offset), "direct buffer round trip");
        check(memory.get(0) == (byte) 0xf0, "direct buffer byte order");
        Path jar = Path.of("/app/compat.jar");
        BasicFileAttributes attrs = Files.readAttributes(jar, BasicFileAttributes.class);
        check(attrs.isRegularFile() && attrs.size() == jar.toFile().length(), "NIO file metadata");
        BasicFileAttributes dependencyAttrs = Files.readAttributes(Path.of("/app/dependency.jar"),
            BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        check(attrs.fileKey() != null && !attrs.fileKey().equals(dependencyAttrs.fileKey()),
            "distinct JAR file keys");
        check(Files.readAttributes(Path.of("/app"), BasicFileAttributes.class).isDirectory(),
            "NIO directory metadata");
        check(Files.isReadable(jar) && jar.toRealPath().equals(jar), "NIO access and real path");
        Path missing = Path.of("/app/no-such-file");
        check(!Files.exists(missing), "missing path existence");
        try {
            Files.readAttributes(missing, BasicFileAttributes.class);
            throw new AssertionError("missing path must throw");
        } catch (NoSuchFileException expected) {
            check(expected.getFile().equals(missing.toString()), "NIO errno/path translation");
        }
        System.out.println("OPENJDK_COMPAT PASS jar=ok resource=ok reflection=ok handles=ok proxy=ok direct=ok metadata=ok args=ok");
    }
}
