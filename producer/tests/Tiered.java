/* SPDX-License-Identifier: MIT */
public final class Tiered {
    interface Operation { int apply(int n); }
    static final class First implements Operation {
        public int apply(int n) { return n + 7; }
    }
    // Resolve this class only after dispatch has compiled with one implementor.
    public static final class Later implements Operation {
        public int apply(int n) { return n - 7; }
    }
    static final class Box {
        int value;
        Box(int value) { this.value = value; }
    }
    static volatile Box escaped;
    static volatile long sink;

    static int dispatch(Operation operation, int n) { return operation.apply(n) + 1; }
    static int escape(Box box) { escaped = box; return box.value - 1; }
    static int materialize(int n, boolean rare) {
        Box box = new Box(n);
        if (rare) return escape(box);
        return box.value + 1;
    }
    static long osr(int n) {
        long value = 0;
        for (int i = 0; i < n; i++) value += (long)i * i + 3 * i;
        return value;
    }
    public static void main(String[] args) throws Exception {
        Operation first = new First();
        for (int i = 0; i < 100_000; i++) {
            if (dispatch(first, i) != i + 8) throw new AssertionError("warm dispatch");
            if (materialize(i, false) != i + 1) throw new AssertionError("warm allocation");
        }
        System.out.println("OPENJDK_TIERED warmed");
        // The never-taken branch exercises deoptimization with an object
        // eligible for scalar replacement. Check its value and full-GC survival.
        if (materialize(12345, true) != 12344 || escaped.value != 12345)
            throw new AssertionError("deoptimized object");
        System.gc();
        if (escaped.value != 12345) throw new AssertionError("materialized GC root");
        Operation later = (Operation)Class.forName("Tiered$Later").getDeclaredConstructor().newInstance();
        for (int i = 0; i < 100_000; i++) {
            if (dispatch(first, i) != i + 8 || dispatch(later, i) != i - 6)
                throw new AssertionError("class hierarchy invalidation");
        }
        int n = 1_000_000; // The closed-form reference must also fit in a long.
        long expected = (long)n * (n - 1) * (2L * n - 1) / 6 + 3L * n * (n - 1) / 2;
        sink = osr(n);
        if (sink != expected) throw new AssertionError("OSR arithmetic");
        System.out.println("OPENJDK_TIERED PASS dispatch=ok materialize=ok gc=ok osr=ok");
    }
}
