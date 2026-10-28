/* SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0 */
package fixture;

public class Dependency {
    public final int value;
    public Dependency(int value) { this.value = value; }
    public static String greet(String name) { return "Hello " + name; }
}
