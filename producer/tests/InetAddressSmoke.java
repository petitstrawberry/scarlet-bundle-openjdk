import java.net.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;

public class InetAddressSmoke {
    static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        boolean nativeTest = args.length != 0 && args[0].startsWith("native");
        boolean enhanced = nativeTest && args[0].equals("native");
        if (nativeTest) java.security.Security.setProperty("jdk.includeInExceptions", enhanced ? "hostInfo" : "");
        require(InetAddress.getLoopbackAddress().isLoopbackAddress(), "loopback address");
        require(InetAddress.getByName("127.0.0.1").isLoopbackAddress(), "numeric IPv4");
        require(InetAddress.getByName("0.0.0.0").isAnyLocalAddress(), "wildcard address");
        byte[] bytes = {(byte)203, 0, 113, (byte)199};
        InetAddress address = InetAddress.getByAddress(bytes);
        require(address.getHostAddress().equals("203.0.113.199"), "unsigned IPv4 bytes");
        require(address.getCanonicalHostName().equals("203.0.113.199"), "reverse lookup fallback");
        byte[] ipv6 = new byte[16];
        ipv6[15] = 1;
        require(InetAddress.getByAddress(ipv6).isLoopbackAddress(), "IPv6 value initialization");

        if (nativeTest) {
            require(InetAddress.getLocalHost().isLoopbackAddress(), "native hostname fallback");
            Field implField = InetAddress.class.getDeclaredField("impl");
            implField.setAccessible(true);
            Object impl = implField.get(null);
            require(impl.getClass().getName().equals("java.net.Inet4AddressImpl"), "IPv4 backend selection");
            Method ipv4Available = InetAddress.class.getDeclaredMethod("isIPv4Available");
            ipv4Available.setAccessible(true);
            require((Boolean)ipv4Available.invoke(null), "native IPv4 socket probe");
            Method ipv6Supported = InetAddress.class.getDeclaredMethod("isIPv6Supported");
            ipv6Supported.setAccessible(true);
            require(!(Boolean)ipv6Supported.invoke(null), "IPv6 backend capability");
            // Numeric getByName normally bypasses JNI. Call the actual native
            // resolver too, so byte order and libc getaddrinfo are exercised.
            Method lookup = impl.getClass().getDeclaredMethod("lookupAllHostAddr", String.class);
            lookup.setAccessible(true);
            InetAddress[] numeric = (InetAddress[])lookup.invoke(impl, "203.0.113.199");
            require(numeric.length == 1 && Arrays.equals(numeric[0].getAddress(), bytes), "native numeric lookup");
            InetAddress[] resolved = InetAddress.getAllByName("many.test");
            require(Arrays.stream(resolved).map(InetAddress::getHostAddress).toList()
                    .equals(List.of("192.0.2.1", "203.0.113.7")), "resolver order and duplicate removal");
            require(resolved[0].getHostName().equals("many.test"), "requested hostname retained");
            try {
                InetAddress.getByName("missing.test");
                throw new AssertionError("missing name resolved");
            } catch (UnknownHostException expected) {}
            try {
                lookup.invoke(impl, "bad..name");
                throw new AssertionError("invalid name resolved");
            } catch (InvocationTargetException expected) {
                require(expected.getCause() instanceof UnknownHostException, "invalid name exception mapping");
                require(expected.getCause().getMessage().contains("bad..name") == enhanced,
                        "native exception hostname policy");
            }
            try (var pool = Executors.newFixedThreadPool(4)) {
                var tasks = new ArrayList<Future<?>>();
                for (int i = 0; i < 4; ++i) {
                    int worker = i;
                    tasks.add(pool.submit(() -> {
                        try {
                            for (int n = 0; n < 8; ++n) {
                                InetAddress found = InetAddress.getByName("worker" + worker + "-" + n + ".test");
                                require(found.getHostAddress().equals("198.51.100.42"), "concurrent resolver bytes");
                            }
                        } catch (Exception e) { throw new RuntimeException(e); }
                    }));
                }
                for (var task : tasks) task.get();
            }
            try {
                address.isReachable(null, 1, 50);
                throw new AssertionError("unsupported TTL silently accepted");
            } catch (java.io.IOException expected) {}
            require(InetAddress.getByName("127.0.0.1").isReachable(500), "TCP echo reachability");
        }
        System.out.println("INET_ADDRESS PASS");
    }
}
