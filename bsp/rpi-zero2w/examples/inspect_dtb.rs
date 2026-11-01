//! Host-only file check; the address is a test placement, not observed firmware state.
fn main() {
    let path = std::env::args().nth(1).expect("supply a DTB file path");
    let data = std::fs::read(path).expect("read DTB");
    let layout = rustos_bsp_rpi_zero2w::validate_board(&data, 0x100_0000)
        .expect("DTB structure and board preflight");
    println!("File preflight at synthetic placement 0x1000000: {layout:?}");
    println!(
        "Memory semantics (not a boot test): {:?}",
        rustos_bsp_rpi_zero2w::validate_boot_memory(&data, 0x100_0000)
    );
}
