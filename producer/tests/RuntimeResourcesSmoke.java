import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.time.*;
import java.util.HexFormat;
import java.io.StringReader;
import java.util.logging.Logger;
import javax.xml.parsers.DocumentBuilderFactory;
import org.xml.sax.InputSource;

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
        System.out.println("RUNTIME_RESOURCES PASS providers=" + Security.getProviders().length + " certificates=" + trust.size());
    }
}
