{
  description = "Versioned native OpenJDK bundle producer for Scarlet";
  nixConfig = {
    extra-substituters = [ "https://scarlet-rust-toolchain.cachix.org" ];
    extra-trusted-public-keys = [ "scarlet-rust-toolchain.cachix.org-1:p+coBExi0nNTIvWF/oM9H9/1/GhwFtqGZ2Vs+4pYl6o=" ];
  };
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    scarlet-rust-toolchain.url = "github:petitstrawberry/scarlet-rust-nix/3c23906c35053e28d56f3aa9b1d29142535ffab7";
    scarlet-sdk = {
      url = "github:petitstrawberry/scarlet-sdk/a071222231e8bbd96c1d54f38d99d1b27ec90805";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.scarlet-rust-toolchain.follows = "scarlet-rust-toolchain";
    };
  };
  outputs = { self, nixpkgs, scarlet-rust-toolchain, scarlet-sdk }:
    let
      systems = [ "aarch64-darwin" "aarch64-linux" "x86_64-linux" ];
    in {
      devShells = nixpkgs.lib.genAttrs systems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          rust = scarlet-rust-toolchain.packages.${system}.scarlet-rust-toolchain;
          llvm = pkgs.llvmPackages_21;
          shell = major:
            let jdk = builtins.getAttr ((if pkgs.stdenv.isDarwin then "zulu" else "jdk") + major) pkgs;
            in pkgs.mkShell {
              packages = [ rust jdk scarlet-sdk.packages.${system}.cargo-scarlet
                llvm.clang llvm.llvm pkgs.lld_21 pkgs.python3 pkgs.git pkgs.curl
                pkgs.autoconf pkgs.automake pkgs.libtool pkgs.gnumake pkgs.pkg-config
                pkgs.unzip pkgs.zip pkgs.file pkgs.which pkgs.gnused pkgs.gnugrep
                pkgs.gawk pkgs.diffutils pkgs.findutils pkgs.gnutar pkgs.gzip
                pkgs.qemu pkgs.libffi pkgs.zlib ];
              JAVA_HOME = "${jdk.home}";
              SCARLET_NATIVE_RUNTIME = "${scarlet-sdk.packages.${system}.scarlet-native-runtime}";
              SCARLET_NATIVE_CC = "${llvm.clang-unwrapped}/bin/clang";
              SCARLET_NATIVE_CXX = "${llvm.clang-unwrapped}/bin/clang++";
              SCARLET_NATIVE_AR = "${llvm.llvm}/bin/llvm-ar";
              SCARLET_NATIVE_NM = "${llvm.llvm}/bin/llvm-nm";
              SCARLET_NATIVE_RANLIB = "${llvm.llvm}/bin/llvm-ranlib";
              SCARLET_RUSTC = "${rust}/bin/rustc";
            };
        in { default = shell "25"; jdk25 = shell "25"; jdk21 = shell "21"; });
    };
}
