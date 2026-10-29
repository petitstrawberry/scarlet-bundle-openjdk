import java.net.*;
import java.nio.*;
import java.nio.channels.*;
import java.util.concurrent.*;

public class NioNetworkSmoke {
    static void require(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }
    public static void main(String[] args) throws Exception {
        int interfaces = 0;
        var enumeration = NetworkInterface.networkInterfaces().iterator();
        while (enumeration.hasNext()) {
            var device = enumeration.next();
            require(NetworkInterface.getByName(device.getName()).getIndex() == device.getIndex(), "interface name lookup");
            require(NetworkInterface.getByIndex(device.getIndex()).getName().equals(device.getName()), "interface index lookup");
            require(device.getMTU() > 0, "interface MTU");
            device.isUp(); device.isLoopback(); device.isPointToPoint(); device.supportsMulticast();
            byte[] mac = device.getHardwareAddress();
            if (args.length != 0 && args[0].equals("interfaces")) {
                require(java.util.Arrays.equals(mac, new byte[] {0x52,0x54,0,0x12,0x34,0x56}), "test NIC MAC");
            }
            interfaces++;
        }
        if (args.length != 0 && args[0].equals("interfaces")) require(interfaces > 0, "real test interface enumerated");
        try (Selector selector = Selector.open()) {
            require(selector.selectNow() == 0, "empty selector");
            var wake = new Thread(() -> {
                try { Thread.sleep(100); selector.wakeup(); }
                catch (InterruptedException e) { throw new RuntimeException(e); }
            });
            wake.start();
            long start = System.nanoTime();
            require(selector.select(5000) == 0, "explicit wakeup");
            require(System.nanoTime() - start < 2_000_000_000L, "wakeup latency");
            wake.join();
            Pipe pipe = Pipe.open();
            try (Pipe.SourceChannel source = pipe.source(); Pipe.SinkChannel sink = pipe.sink()) {
                source.configureBlocking(false);
                require(source.read(ByteBuffer.allocate(1)) == 0, "nonblocking empty pipe");
            }
            try (ServerSocketChannel server = ServerSocketChannel.open(); SocketChannel client = SocketChannel.open()) {
                server.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0));
                server.configureBlocking(false);
                SelectionKey listener = server.register(selector, SelectionKey.OP_ACCEPT);
                client.configureBlocking(false);
                client.connect(server.getLocalAddress());
                long deadline = System.nanoTime() + 5_000_000_000L;
                while (!client.finishConnect()) {
                    require(System.nanoTime() < deadline, "connect timeout");
                    Thread.sleep(1);
                }
                require(selector.select(1000) > 0 && listener.isAcceptable(), "accept readiness");
                selector.selectedKeys().clear();
                try (SocketChannel accepted = server.accept()) {
                    require(accepted != null, "accepted channel");
                    accepted.configureBlocking(false);
                    SelectionKey reader = accepted.register(selector, SelectionKey.OP_READ);
                    require(client.write(new ByteBuffer[] {ByteBuffer.wrap(new byte[] {1,2}), ByteBuffer.wrap(new byte[] {3,4})}) == 4,
                            "gather socket write");
                    require(selector.select(1000) > 0 && reader.isReadable(), "read readiness");
                    ByteBuffer first = ByteBuffer.allocate(1), second = ByteBuffer.allocateDirect(3);
                    require(accepted.read(new ByteBuffer[] {first, second}) == 4, "scatter socket read");
                    require(first.get(0) == 1 && second.get(2) == 4, "socket bytes");
                    require(accepted.getRemoteAddress().equals(client.getLocalAddress()), "peer address");
                }
            }
        }
        System.out.println("NIO_NETWORK PASS");
    }
}
