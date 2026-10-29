import java.io.*;

public class ConsoleInputSmoke {
    public static void main(String[] args) throws Exception {
        var input = new FileInputStream(FileDescriptor.in);
        if (input.available() < 0) throw new AssertionError("negative pipe estimate");
        System.out.println("CONSOLE_READY");
        System.out.flush();
        var reader = new BufferedReader(new InputStreamReader(new BufferedInputStream(input)));
        if (!"日本語 stop".equals(reader.readLine())) throw new AssertionError("console line");
        input.close();
        try {
            input.available();
            throw new AssertionError("closed descriptor accepted");
        } catch (IOException expected) {}
        System.out.println("CONSOLE_INPUT PASS");
    }
}
