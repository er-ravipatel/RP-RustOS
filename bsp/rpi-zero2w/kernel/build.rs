fn main() {
    let root = std::path::PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    println!("cargo:rustc-link-arg=-T{}", root.join("link.ld").display());
    println!("cargo:rerun-if-changed=link.ld");
    println!("cargo:rerun-if-changed=src/entry");
    println!("cargo:rerun-if-changed=src/entry.S");
}
