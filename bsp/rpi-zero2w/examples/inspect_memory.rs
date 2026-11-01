//! Host reference for explicit synthetic handoff fixtures, not physical memory.
fn main() {
    let mut args = std::env::args().skip(1);
    let path = args.next().expect("DTB fixture path");
    let address = u64::from_str_radix(&args.next().expect("physical address in hex"), 16)
        .expect("hex address");
    let bytes = std::fs::read(path).expect("read DTB fixture");
    match rustos_bsp_rpi_zero2w::inspect_boot_memory(&bytes, address) {
        Ok(info) => println!("OK {info:?}"),
        Err(error) => println!("ERR {error:?}"),
    }
}
