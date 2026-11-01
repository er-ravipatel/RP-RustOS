use std::{
    io::{self, Write},
    process::Command,
    time::Duration,
};
fn main() {
    match std::env::args().nth(1).as_deref() {
        Some("echo") => println!(
            "{}",
            serde_json::to_string(&std::env::args().skip(2).collect::<Vec<_>>()).unwrap()
        ),
        Some("environment") => println!(
            "{}",
            serde_json::to_string(&std::env::vars().collect::<std::collections::BTreeMap<_, _>>())
                .unwrap()
        ),
        Some("tree") => {
            let mut child = Command::new(std::env::current_exe().unwrap())
                .arg("sleep")
                .spawn()
                .unwrap();
            println!("{}", child.id());
            io::stdout().flush().unwrap();
            child.wait().unwrap();
        }
        Some("orphan") => {
            orphan();
        }
        Some("flood") => {
            io::stdout()
                .write_all(&vec![b'x'; 2 * 1024 * 1024])
                .unwrap();
        }
        _ => std::thread::sleep(Duration::from_secs(30)),
    }
}

// Deliberately exit before the child to test job ownership after root exit.
// The test supervisor owns and settles this descendant through its Windows job.
#[allow(clippy::zombie_processes)]
fn orphan() {
    let child = Command::new(std::env::current_exe().unwrap())
        .arg("sleep")
        .spawn()
        .unwrap();
    println!("{}", child.id());
}
