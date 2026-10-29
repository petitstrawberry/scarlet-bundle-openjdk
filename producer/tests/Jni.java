// SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicReference;

public class Jni {
    static { System.loadLibrary("jni_probe"); }
    static native int registered(int value);
    static native int exercise(byte[] data, ByteBuffer direct);
    static native int attached();
    static native void fail();
    static native void missing();
    static int callback(int value) { return value * 3; }

    static void check(boolean value) {
        if (!value) throw new AssertionError("JNI result mismatch");
    }

    public static void main(String[] args) throws Exception {
        check(registered(7) == 50);
        check(attached() == 129);
        byte[] data = {1, 2, 3};
        ByteBuffer direct = ByteBuffer.allocateDirect(8);
        check(exercise(data, direct) == 129);
        check(data[1] == 42 && direct.get(0) == 99);
        try { fail(); throw new AssertionError("missing JNI exception"); }
        catch (IllegalStateException expected) { check(expected.getMessage().equals("native exception")); }
        try { missing(); throw new AssertionError("missing symbol accepted"); }
        catch (UnsatisfiedLinkError expected) { }
        try { System.load("/app/lib/absent.so"); throw new AssertionError("missing library accepted"); }
        catch (UnsatisfiedLinkError expected) { check(!expected.getMessage().isEmpty()); }
        try { System.load("/app/lib/invalid.so"); throw new AssertionError("invalid ELF accepted"); }
        catch (UnsatisfiedLinkError expected) { check(!expected.getMessage().isEmpty()); }
        AtomicReference<Throwable> error = new AtomicReference<>();
        Thread[] threads = new Thread[4];
        for (int i = 0; i < threads.length; i++) {
            threads[i] = new Thread(() -> {
                try { for (int n = 0; n < 1000; n++) check(registered(n) == n + 43); }
                catch (Throwable t) { error.compareAndSet(null, t); }
            });
            threads[i].start();
        }
        for (Thread thread : threads) thread.join();
        if (error.get() != null) throw new AssertionError(error.get());
        System.loadLibrary("jni_probe");
        check(registered(0) == 43);
        System.out.println("OPENJDK_JNI PASS onload=ok register=ok dependency=ok callback=ok array=ok direct=ok exception=ok errors=ok attach=ok threads=4");
    }
}
