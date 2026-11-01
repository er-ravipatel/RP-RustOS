#![cfg(all(windows, feature = "test-fixtures"))]
use rustos_assembler::native::{locked_read, publish, Process, StopReason};
use std::sync::atomic::AtomicBool;
use std::{
    fs,
    path::Path,
    time::{Duration, Instant},
};
use windows_sys::Win32::{
    Foundation::CloseHandle,
    System::Threading::{OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE},
};

fn spawn(mode: &str, root: &Path) -> Process {
    Process::spawn(
        Path::new(env!("CARGO_BIN_EXE_job-fixture")),
        &[mode.into()],
        root,
        &root.join("logs"),
    )
    .unwrap()
}
fn until(mut predicate: impl FnMut() -> bool) {
    let start = Instant::now();
    while !predicate() {
        assert!(
            start.elapsed() < Duration::from_secs(5),
            "bounded observation timed out"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
}
fn child_pid(process: &Process) -> u32 {
    until(|| {
        fs::read_to_string(&process.stdout)
            .unwrap_or_default()
            .trim()
            .parse::<u32>()
            .is_ok()
    });
    fs::read_to_string(&process.stdout)
        .unwrap()
        .trim()
        .parse()
        .unwrap()
}
#[test]
fn termination_settles_the_whole_owned_tree() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("tree", root.path());
    let child = child_pid(&process);
    until(|| {
        let ids = process.process_ids().unwrap();
        ids.contains(&(process.pid as usize)) && ids.contains(&(child as usize))
    });
    process.terminate().unwrap();
    assert!(process.settle(Duration::from_secs(5)).unwrap());
    assert_eq!(process.active().unwrap(), 0);
    assert_ne!(process.exit_code().unwrap(), 259);
}
#[test]
fn root_exit_does_not_hide_a_live_descendant() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("orphan", root.path());
    let child = child_pid(&process);
    until(|| process.exit_code().unwrap() != 259);
    assert_eq!(process.exit_code().unwrap(), 0);
    assert!(process.process_ids().unwrap().contains(&(child as usize)));
    assert!(process.active().unwrap() >= 1);
    assert!(!process.settle(Duration::from_millis(50)).unwrap());
    process.terminate().unwrap();
    assert!(process.settle(Duration::from_secs(5)).unwrap());
}
#[test]
fn dropping_owner_kills_descendant_and_preserves_unrelated_process() {
    let root = tempfile::tempdir().unwrap();
    let unrelated_root = tempfile::tempdir().unwrap();
    let unrelated = spawn("sleep", unrelated_root.path());
    let process = spawn("tree", root.path());
    let child = child_pid(&process);
    let handle = unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, child) };
    assert!(!handle.is_null());
    drop(process);
    assert_eq!(unsafe { WaitForSingleObject(handle, 5000) }, 0);
    unsafe {
        CloseHandle(handle);
    }
    assert!(unrelated
        .process_ids()
        .unwrap()
        .contains(&(unrelated.pid as usize)));
    assert_eq!(unrelated.exit_code().unwrap(), 259);
}
#[test]
fn log_capture_exposes_overflow_without_stdout_contamination() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("flood", root.path());
    assert!(process.settle(Duration::from_secs(5)).unwrap());
    assert!(process.overflow(1024 * 1024).unwrap());
    assert_eq!(
        fs::metadata(&process.stdout).unwrap().len(),
        2 * 1024 * 1024
    );
    assert_eq!(fs::metadata(&process.stderr).unwrap().len(), 0);
}
#[test]
fn publication_never_replaces_an_existing_destination() {
    let root = tempfile::tempdir().unwrap();
    let source = root.path().join("stage");
    let destination = root.path().join("bundle");
    fs::create_dir(&source).unwrap();
    fs::write(source.join("manifest.json"), "new").unwrap();
    fs::create_dir(&destination).unwrap();
    fs::write(destination.join("manifest.json"), "original").unwrap();
    assert!(publish(&source, &destination).is_err());
    assert_eq!(
        fs::read_to_string(destination.join("manifest.json")).unwrap(),
        "original"
    );
    assert!(source.is_dir());
    let fresh = root.path().join("fresh");
    publish(&source, &fresh).unwrap();
    assert!(!source.exists());
    assert_eq!(
        fs::read_to_string(fresh.join("manifest.json")).unwrap(),
        "new"
    );
}
#[test]
fn stable_read_denies_writes_and_replacement_until_closed() {
    let root = tempfile::tempdir().unwrap();
    let artifact = root.path().join("kernel.elf");
    fs::write(&artifact, "original").unwrap();
    let held = locked_read(&artifact).unwrap();
    assert!(fs::OpenOptions::new().write(true).open(&artifact).is_err());
    assert!(fs::remove_file(&artifact).is_err());
    assert!(fs::rename(&artifact, root.path().join("other")).is_err());
    drop(held);
    fs::write(&artifact, "replacement").unwrap();
}

#[test]
fn deadline_terminates_and_settles_a_tool_tree() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("tree", root.path());
    let _child = child_pid(&process);
    let result = process
        .supervise(
            Duration::from_millis(100),
            &AtomicBool::new(false),
            1024 * 1024,
        )
        .unwrap();
    assert_eq!(result.reason, StopReason::Deadline);
    assert!(result.forced && result.settled);
    assert_eq!(process.active().unwrap(), 0);
}
#[test]
fn cancellation_is_terminal_and_settles_the_tree() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("tree", root.path());
    let _child = child_pid(&process);
    let result = process
        .supervise(Duration::from_secs(30), &AtomicBool::new(true), 1024 * 1024)
        .unwrap();
    assert_eq!(result.reason, StopReason::Cancelled);
    assert!(result.forced && result.settled);
    assert_eq!(process.active().unwrap(), 0);
}
#[test]
fn overflow_cannot_become_success_and_retained_capture_is_bounded() {
    let root = tempfile::tempdir().unwrap();
    let process = spawn("flood", root.path());
    let result = process
        .supervise(Duration::from_secs(5), &AtomicBool::new(false), 1024 * 1024)
        .unwrap();
    assert_eq!(result.reason, StopReason::OutputLimit);
    assert!(result.forced && result.settled);
    assert!(result.captured_bytes_before_truncation[0] > 1024 * 1024);
    assert_eq!(fs::metadata(&process.stdout).unwrap().len(), 1024 * 1024);
    assert_eq!(process.active().unwrap(), 0);
}

#[test]
fn actual_child_receives_exact_windows_arguments() {
    let root = tempfile::tempdir().unwrap();
    let values = vec![
        "",
        "two words",
        "quote\"inside",
        "C:\\path with spaces\\",
        "slash\\\"quote",
        "Ravi-नमस्ते",
    ];
    let mut args = vec!["echo".to_string()];
    args.extend(values.iter().map(|s| s.to_string()));
    let process = Process::spawn(
        Path::new(env!("CARGO_BIN_EXE_job-fixture")),
        &args,
        root.path(),
        &root.path().join("logs"),
    )
    .unwrap();
    let result = process
        .supervise(Duration::from_secs(5), &AtomicBool::new(false), 1024 * 1024)
        .unwrap();
    assert_eq!(result.reason, StopReason::Exited(0));
    assert!(result.settled && !result.forced);
    let actual: Vec<String> =
        serde_json::from_slice(&fs::read(process.stdout.clone()).unwrap()).unwrap();
    assert_eq!(actual, values);
}

#[test]
fn explicit_environment_is_unicode_and_excludes_ambient_variables() {
    let root = tempfile::tempdir().unwrap();
    let environment = vec![("RUSTOS_TEST_VALUE".into(), "नमस्ते with spaces".into())];
    let process = Process::spawn_with_environment(
        Path::new(env!("CARGO_BIN_EXE_job-fixture")),
        &["environment".into()],
        root.path(),
        &root.path().join("logs"),
        Some(&environment),
    )
    .unwrap();
    let completion = process
        .supervise(Duration::from_secs(5), &AtomicBool::new(false), 1024 * 1024)
        .unwrap();
    assert_eq!(completion.reason, StopReason::Exited(0));
    assert!(completion.settled);
    let actual: std::collections::BTreeMap<String, String> =
        serde_json::from_slice(&fs::read(&process.stdout).unwrap()).unwrap();
    assert_eq!(actual.get("RUSTOS_TEST_VALUE").unwrap(), "नमस्ते with spaces");
    assert!(!actual.contains_key("PATH"));
    assert!(!actual.contains_key("USERPROFILE"));
}
