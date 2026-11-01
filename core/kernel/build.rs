fn main() {
    let script =
        std::path::Path::new(&std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("link.ld");
    println!("cargo:rustc-link-arg=-T{}", script.display());
    println!("cargo:rerun-if-changed=link.ld");
    println!("cargo:rerun-if-changed=src/entry.S");
}
