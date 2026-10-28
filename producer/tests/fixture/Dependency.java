/* SPDX-License-Identifier: MIT */
package fixture;

public class Dependency {
    public final int value;
    public Dependency(int value) { this.value = value; }
    public static String greet(String name) { return "Hello " + name; }
}
