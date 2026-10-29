import java.lang.management.*;

public class ManagementSmoke {
    static void require(boolean ok, String what) {
        if (!ok) throw new AssertionError(what);
    }
    public static void main(String[] args) throws Exception {
        var runtime = ManagementFactory.getRuntimeMXBean();
        require(runtime.getInputArguments().contains("-Dscarlet.management.probe=true"), "VM arguments");
        require(runtime.getStartTime() > 0 && runtime.getUptime() >= 0, "VM start time");
        require(ManagementFactory.getOperatingSystemMXBean().getAvailableProcessors()
                == Runtime.getRuntime().availableProcessors(), "processor count");
        var memory = ManagementFactory.getMemoryMXBean().getHeapMemoryUsage();
        require(memory.getMax() == Runtime.getRuntime().maxMemory() && memory.getUsed() > 0, "heap usage");
        require(!ManagementFactory.getMemoryPoolMXBeans().isEmpty(), "memory pools");
        var threads = ManagementFactory.getThreadMXBean();
        require(threads.getThreadCount() > 0 && threads.getAllThreadIds().length > 0, "live threads");
        long before = ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount).sum();
        System.gc();
        long after = ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount).sum();
        require(after > before, "GC collection counters");
        System.out.println("MANAGEMENT PASS gc=" + before + "->" + after);
    }
}
