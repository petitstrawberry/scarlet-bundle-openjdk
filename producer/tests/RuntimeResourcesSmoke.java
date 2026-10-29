import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.time.*;
import java.util.HexFormat;
import java.io.StringReader;
import java.util.logging.Logger;
import javax.xml.parsers.DocumentBuilderFactory;
import org.xml.sax.InputSource;
import java.beans.Introspector;
import java.beans.PropertyChangeSupport;

public class RuntimeResourcesSmoke {
    static void require(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }
    public static void main(String[] args) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256")
            .digest("abc".getBytes(StandardCharsets.UTF_8));
        require(HexFormat.of().formatHex(digest).equals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"), "SHA-256");
        require(ZoneId.of("Asia/Tokyo").getRules().getOffset(Instant.EPOCH)
            .getTotalSeconds() == 32400, "time-zone database");
        var trust = KeyStore.getInstance(KeyStore.getDefaultType());
        try (var input = Files.newInputStream(Path.of(System.getProperty("java.home"), "lib/security/cacerts"))) {
            trust.load(input, "changeit".toCharArray());
        }
        require(trust.size() > 0, "default certificate store");
        var xml = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(new InputSource(new StringReader("<configuration status=\"ok\"/>")));
        require(xml.getDocumentElement().getAttribute("status").equals("ok"), "XML parser");
        require(Logger.getLogger("scarlet.runtime").getName().equals("scarlet.runtime"), "logging module");
        var changes = new PropertyChangeSupport(new Object());
        int[] events = {0};
        changes.addPropertyChangeListener(event -> {
            require(event.getPropertyName().equals("value") && event.getNewValue().equals(2), "bean event");
            events[0]++;
        });
        changes.firePropertyChange("value", 1, 2);
        require(events[0] == 1, "bean listener delivery");
        require(Introspector.getBeanInfo(String.class).getPropertyDescriptors().length > 0, "bean introspection");
        Path archive = Path.of("runtime-zipfs-probe.zip");
        try (var zip = new java.util.zip.ZipOutputStream(Files.newOutputStream(archive))) {
            zip.putNextEntry(new java.util.zip.ZipEntry("data/日本語.txt"));
            zip.write("zip filesystem".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
        }
        try (var zip = FileSystems.newFileSystem(archive)) {
            require(Files.readString(zip.getPath("/data/日本語.txt")).equals("zip filesystem"), "ZIP filesystem provider");
        }
        Files.delete(archive);
        System.out.println("RUNTIME_RESOURCES PASS providers=" + Security.getProviders().length + " certificates=" + trust.size());
    }
}
