//! M1 snapshot build and no-replacement publication. Verification is a separate operation.
use super::*;
use crate::native::{locked_read, publish, Process, StopReason};
use serde_json::{json, Value};
use std::{
    ffi::OsString,
    io::{self, Read, Write},
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use time::{format_description::well_known::Rfc3339, OffsetDateTime};

static CANCELLED: AtomicBool = AtomicBool::new(false);
pub(super) type BuildResult<T> = std::result::Result<T, Failure>;
pub(super) struct Failure {
    pub(super) diagnostic: Diagnostic,
    exit: i32,
}
impl Failure {
    pub(super) fn new(code: &str, message: &str, exit: i32) -> Self {
        let mut diagnostic = Diagnostic::error(code, message, "build");
        diagnostic.stage = "build".into();
        Self { diagnostic, exit }
    }
}
impl From<io::Error> for Failure {
    fn from(error: io::Error) -> Self {
        Self::new("BUILD_IO", &error.to_string(), 4)
    }
}
pub(super) fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn info(code: &str, stage: &str, message: &str) -> Diagnostic {
    let mut d = Diagnostic::error(code, message, stage);
    d.severity = "info".into();
    d.stage = stage.into();
    d
}
fn stamp() -> String {
    OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .expect("UTC date")
}
pub(crate) fn local_path(path: &Path) -> PathBuf {
    if matches!(path.components().next(), Some(std::path::Component::Prefix(prefix)) if matches!(prefix.kind(), std::path::Prefix::VerbatimDisk(_)))
    {
        use std::os::windows::ffi::{OsStrExt, OsStringExt};
        return PathBuf::from(OsString::from_wide(
            &path.as_os_str().encode_wide().skip(4).collect::<Vec<_>>(),
        ));
    }
    path.into()
}
pub(super) fn write_new(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}
pub(super) fn checked_file(path: &Path) -> BuildResult<Vec<u8>> {
    if linked(&fs::symlink_metadata(path)?) {
        return Err(Failure::new(
            "UNSAFE_INPUT",
            "Snapshot inputs cannot be links or reparse points",
            3,
        ));
    }
    let mut file = locked_read(path)?;
    if !file.metadata()?.is_file() || file.metadata()?.len() > 16 * 1024 * 1024 {
        return Err(Failure::new(
            "SOURCE_LIMIT",
            "Input is not a regular file within the 16 MiB per-file limit",
            3,
        ));
    }
    let mut bytes = Vec::new();
    Read::by_ref(&mut file)
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > 16 * 1024 * 1024 {
        return Err(Failure::new(
            "SOURCE_LIMIT",
            "Input grew beyond snapshot limit",
            3,
        ));
    }
    Ok(bytes)
}
fn snapshot_file(
    source: &Path,
    destination: &Path,
    relative: &str,
    inputs: &mut Vec<Input>,
) -> BuildResult<()> {
    let bytes = checked_file(source)?;
    fs::create_dir_all(destination.parent().unwrap())?;
    write_new(destination, &bytes)?;
    inputs.push(Input {
        path: relative.into(),
        sha256: hash(&bytes),
    });
    if inputs.len() > 4096 {
        return Err(Failure::new(
            "SOURCE_LIMIT",
            "Snapshot exceeds 4096 files",
            3,
        ));
    }
    Ok(())
}
pub(super) fn snapshot_tree(
    repo: &Path,
    snapshot: &Path,
    relative: &Path,
    inputs: &mut Vec<Input>,
    total: &mut u64,
) -> BuildResult<()> {
    let source = repo.join(relative);
    let metadata = fs::symlink_metadata(&source)?;
    if linked(&metadata) {
        return Err(Failure::new(
            "UNSAFE_INPUT",
            "Snapshot tree contains a link or reparse point",
            3,
        ));
    }
    if metadata.is_dir() {
        let mut entries = fs::read_dir(&source)?.collect::<std::result::Result<Vec<_>, _>>()?;
        entries.sort_by_key(|entry| entry.file_name());
        for entry in entries {
            if ["target", ".git"].contains(&entry.file_name().to_string_lossy().as_ref()) {
                continue;
            }
            snapshot_tree(
                repo,
                snapshot,
                &relative.join(entry.file_name()),
                inputs,
                total,
            )?;
        }
    } else {
        *total += metadata.len();
        if *total > 64 * 1024 * 1024 {
            return Err(Failure::new("SOURCE_LIMIT", "Snapshot exceeds 64 MiB", 3));
        }
        snapshot_file(
            &source,
            &snapshot.join(relative),
            &relative.to_string_lossy().replace('\\', "/"),
            inputs,
        )?;
    }
    Ok(())
}
pub(super) fn find(name: &str) -> BuildResult<PathBuf> {
    std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default())
        .map(|directory| directory.join(format!("{name}.exe")))
        .find(|path| path.is_absolute() && path.is_file())
        .ok_or_else(|| {
            Failure::new(
                "TOOL_MISSING",
                &format!("{name}.exe is missing from PATH"),
                3,
            )
        })
}
pub(super) fn environment(home: &Path) -> Vec<(OsString, OsString)> {
    const ALLOWED: &[&str] = &[
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "COMMONPROGRAMFILES",
        "LIB",
        "LIBPATH",
        "INCLUDE",
        "VCINSTALLDIR",
        "VCTOOLSINSTALLDIR",
        "WINDOWSSDKDIR",
        "WINDOWSSDKVERSION",
        "RUSTUP_HOME",
    ];
    let mut values: Vec<_> = std::env::vars_os()
        .filter(|(key, _)| ALLOWED.contains(&key.to_string_lossy().to_uppercase().as_str()))
        .collect();
    values.push(("CARGO_HOME".into(), home.as_os_str().into()));
    values
}
pub(super) fn run(
    exe: &Path,
    args: &[String],
    cwd: &Path,
    logs: &Path,
    env: &[(OsString, OsString)],
) -> BuildResult<String> {
    if CANCELLED.load(Ordering::SeqCst) {
        return Err(Failure::new(
            "CANCELLED",
            "Build cancelled before tool launch",
            7,
        ));
    }
    let process = Process::spawn_with_environment(exe, args, cwd, logs, Some(env))?;
    write_new(&logs.join("process.json"),&serde_json::to_vec_pretty(&json!({"owned_pid":process.pid,"executable":exe.display().to_string(),"arguments":args})).unwrap()).map_err(|e|Failure::new("REPORT_FAILED",&e.to_string(),8))?;
    let result = process.supervise(Duration::from_secs(120), &CANCELLED, 1024 * 1024)?;
    if !result.settled {
        return Err(Failure::new(
            "CLEANUP_FAILED",
            "Owned tool processes did not settle",
            8,
        ));
    }
    match result.reason {
        StopReason::Exited(0) => Ok(fs::read_to_string(&process.stdout)?),
        StopReason::Exited(code) => Err(Failure::new(
            "TOOL_FAILED",
            &format!(
                "{} exited with {code}; logs: {}",
                exe.display(),
                logs.display()
            ),
            4,
        )),
        StopReason::Deadline => Err(Failure::new(
            "BUILD_TIMEOUT",
            "Tool exceeded the 120-second deadline",
            6,
        )),
        StopReason::Cancelled => Err(Failure::new(
            "CANCELLED",
            "Build cancelled; owned processes settled",
            7,
        )),
        StopReason::OutputLimit => Err(Failure::new(
            "OUTPUT_LIMIT",
            "Tool exceeded the 1 MiB per-stream capture limit",
            4,
        )),
    }
}
fn strings(values: &[&str]) -> Vec<String> {
    values.iter().map(|value| (*value).into()).collect()
}
pub(super) fn no_ancestor_cargo_config(path: &Path) -> BuildResult<()> {
    for ancestor in path.ancestors() {
        for name in ["config", "config.toml"] {
            if ancestor.join(".cargo").join(name).exists() {
                return Err(Failure::new(
                    "UNTRACKED_CARGO_CONFIG",
                    "Ancestor Cargo configuration is unsupported by this snapshot builder",
                    3,
                ));
            }
        }
    }
    Ok(())
}
fn check_workspace(snapshot: &Path) -> BuildResult<()> {
    let root: toml::Value = toml::from_str(&fs::read_to_string(snapshot.join("Cargo.toml"))?)
        .map_err(|e| Failure::new("SOURCE_INVALID", &e.to_string(), 3))?;
    let expected = ["core/kernel", "hal", "bsp/qemu-virt", "drivers/console"];
    let members = root
        .get("workspace")
        .and_then(|value| value.get("members"))
        .and_then(toml::Value::as_array)
        .ok_or_else(|| {
            Failure::new(
                "UNSUPPORTED_LAYOUT",
                "Explicit workspace members required",
                3,
            )
        })?;
    let actual: BTreeSet<_> = members.iter().filter_map(toml::Value::as_str).collect();
    if actual != expected.into_iter().collect() || members.len() != 4 {
        return Err(Failure::new(
            "UNSUPPORTED_LAYOUT",
            "M1 builder supports exactly the four selected kernel crates",
            3,
        ));
    }
    for relative in expected {
        let manifest: toml::Value = toml::from_str(&fs::read_to_string(
            snapshot.join(relative).join("Cargo.toml"),
        )?)
        .map_err(|e| Failure::new("SOURCE_INVALID", &e.to_string(), 3))?;
        if let Some(dependencies) = manifest.get("dependencies").and_then(toml::Value::as_table) {
            for dependency in dependencies.values() {
                let path = dependency
                    .get("path")
                    .and_then(toml::Value::as_str)
                    .ok_or_else(|| {
                        Failure::new(
                            "UNSUPPORTED_DEPENDENCY",
                            "M1 requires repository-local path dependencies",
                            3,
                        )
                    })?;
                let resolved = snapshot.join(relative).join(path).canonicalize()?;
                if Path::new(path).is_absolute() || !resolved.starts_with(snapshot) {
                    return Err(Failure::new(
                        "UNSAFE_DEPENDENCY",
                        "Dependency escapes the source snapshot",
                        3,
                    ));
                }
            }
        }
    }
    Ok(())
}
pub fn check_elf(bytes: &[u8]) -> std::result::Result<(), String> {
    fn u16_at(b: &[u8], n: usize) -> u16 {
        u16::from_le_bytes(b[n..n + 2].try_into().unwrap())
    }
    fn u32_at(b: &[u8], n: usize) -> u32 {
        u32::from_le_bytes(b[n..n + 4].try_into().unwrap())
    }
    fn u64_at(b: &[u8], n: usize) -> u64 {
        u64::from_le_bytes(b[n..n + 8].try_into().unwrap())
    }
    if bytes.len() < 64
        || &bytes[..7] != b"\x7fELF\x02\x01\x01"
        || u16_at(bytes, 16) != 2
        || u16_at(bytes, 18) != 183
        || u64_at(bytes, 24) != 0x40080000
        || u16_at(bytes, 54) != 56
    {
        return Err("Expected AArch64 executable ELF64 with entry 0x40080000".into());
    }
    let offset =
        usize::try_from(u64_at(bytes, 32)).map_err(|_| "Program header offset overflow")?;
    let count = u16_at(bytes, 56) as usize;
    if count == 0
        || offset
            .checked_add(count * 56)
            .is_none_or(|end| end > bytes.len())
    {
        return Err("Invalid program header table".into());
    }
    let mut ranges = vec![];
    let mut entry = false;
    for i in 0..count {
        let p = offset + i * 56;
        if u32_at(bytes, p) != 1 {
            continue;
        }
        let flags = u32_at(bytes, p + 4);
        let file = u64_at(bytes, p + 8);
        let address = u64_at(bytes, p + 16);
        let physical = u64_at(bytes, p + 24);
        let size = u64_at(bytes, p + 32);
        let memory = u64_at(bytes, p + 40);
        let end = address.checked_add(memory).ok_or("Segment overflow")?;
        if address != physical
            || address < 0x40080000
            || end > 0x40200000
            || memory < size
            || file
                .checked_add(size)
                .is_none_or(|end| end > bytes.len() as u64)
            || flags & 3 == 3
        {
            return Err("Unsafe or out-of-bounds load segment".into());
        }
        if memory > 0 {
            if ranges.iter().any(|&(a, b)| address < b && a < end) {
                return Err("Overlapping load segments".into());
            }
            ranges.push((address, end));
        }
        if flags & 1 != 0 && address <= 0x40080000 && address + size > 0x40080000 {
            entry = true;
        }
    }
    if !entry {
        return Err("Entry is not in an executable load segment".into());
    }
    Ok(())
}

fn perform(
    repo: &Path,
    config_path: &Path,
    staging: &mut Option<PathBuf>,
) -> BuildResult<(Value, String)> {
    let inspection = inspect(repo, config_path).map_err(|diagnostic| Failure {
        diagnostic,
        exit: 2,
    })?;
    if let Some(diagnostic) = inspection
        .plan
        .missing_prerequisites
        .iter()
        .find(|d| d.code != "EXECUTION_PREREQUISITES_UNCHECKED")
    {
        return Err(Failure::new("PREREQUISITE_MISSING", &diagnostic.message, 3));
    }
    let repo = repo.canonicalize()?;
    let config_path = config_path.canonicalize()?;
    let bytes = checked_file(&config_path)?;
    let config: Config = toml::from_str(
        std::str::from_utf8(&bytes)
            .map_err(|_| Failure::new("CONFIG_INVALID", "Config is not UTF-8", 2))?,
    )
    .map_err(|e| Failure::new("CONFIG_INVALID", &e.to_string(), 2))?;
    if inspection
        .plan
        .inputs
        .iter()
        .find(|input| Path::new(&input.path) == config_path)
        .is_none_or(|input| input.sha256 != hash(&bytes))
    {
        return Err(Failure::new(
            "INPUT_CHANGED",
            "Configuration changed after inspection",
            3,
        ));
    }
    let output = checked_path(
        config_path.parent().unwrap(),
        &config.output_dir,
        "OUTPUT_INVALID",
    )
    .map_err(|diagnostic| Failure {
        diagnostic,
        exit: 2,
    })?;
    if output.exists() {
        return Err(Failure::new(
            "OUTPUT_EXISTS",
            "Output destination already exists; it will not be replaced",
            4,
        ));
    }
    no_ancestor_cargo_config(output.parent().unwrap())?;
    // The supported M1 backend is deliberately narrower than metadata inspection.
    let catalog: Catalog = toml::from_str(&fs::read_to_string(repo.join("catalog/modules.toml"))?)
        .map_err(|e| Failure::new("CATALOG_INVALID", &e.to_string(), 2))?;
    let selected: BTreeSet<_> = inspection
        .plan
        .build_order
        .iter()
        .map(String::as_str)
        .collect();
    let layouts: BTreeMap<_, _> = [
        ("hal", "hal"),
        ("bsp-qemu-virt", "bsp/qemu-virt"),
        ("console-pl011", "drivers/console"),
        ("kernel", "core/kernel"),
    ]
    .into_iter()
    .collect();
    if selected != layouts.keys().copied().collect()
        || catalog
            .modules
            .iter()
            .filter(|m| selected.contains(m.id.as_str()))
            .any(|m| layouts.get(m.id.as_str()).copied() != Some(m.source_for(&inspection.target)))
    {
        return Err(Failure::new(
            "UNSUPPORTED_LAYOUT",
            "M1 build requires the four approved module layouts",
            3,
        ));
    }
    if !repo.join("Cargo.lock").is_file() {
        return Err(Failure::new(
            "PREREQUISITE_MISSING",
            "Root Cargo.lock is required",
            3,
        ));
    }
    let rustup = find("rustup")?;
    fs::create_dir_all(output.parent().unwrap())?;
    let output_parent = output.parent().unwrap().canonicalize()?;
    let output = output_parent.join(output.file_name().unwrap());
    let bundle_id = format!(
        "m1-{:x}-{:x}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let stage = output_parent.join(format!(".rustos-staging-{bundle_id}"));
    let longest_host_path = stage.join(
        "c/n/release/build/rustos-kernel-0000000000000000/build_script_build-0000000000000000.exe",
    );
    if local_path(&longest_host_path).as_os_str().len() >= 260 {
        return Err(Failure::new(
            "OUTPUT_PATH_TOO_LONG",
            "Choose a shorter output parent for the Windows host linker",
            3,
        ));
    }
    fs::create_dir(&stage)?;
    *staging = Some(stage.clone());
    write_new(&stage.join("incomplete.json"), serde_json::to_vec_pretty(&json!({"schema_version":1,"complete":false,"operation":"build","bundle_id":bundle_id,"started_at":stamp()})).unwrap().as_slice())?;
    let snapshot = stage.join("source");
    fs::create_dir(&snapshot)?;
    let mut inputs = vec![];
    let mut total = 0;
    for relative in [
        "Cargo.toml",
        "Cargo.lock",
        "hal",
        "bsp/qemu-virt",
        "drivers/console",
        "core/kernel",
        "profiles/qemu-virt-a53.toml",
        "catalog/modules.toml",
        "recipes/startup-and-panic-v1.toml",
    ] {
        snapshot_tree(
            &repo,
            &snapshot,
            Path::new(relative),
            &mut inputs,
            &mut total,
        )?;
    }
    snapshot_file(
        &config_path,
        &snapshot.join("configuration.toml"),
        "configuration.toml",
        &mut inputs,
    )?;
    // Check every parsed input against the snapshot, including metadata read before copying.
    for input in &inspection.plan.inputs {
        let original = Path::new(&input.path);
        let relative = if original == config_path {
            Path::new("configuration.toml")
        } else {
            original
                .strip_prefix(&repo)
                .map_err(|_| Failure::new("INPUT_IDENTITY", "Input is outside repository", 3))?
        };
        if hash(&fs::read(snapshot.join(relative))?) != input.sha256 {
            return Err(Failure::new(
                "INPUT_CHANGED",
                "An inspected input changed before snapshot capture",
                3,
            ));
        }
    }
    let snapshot_inspection = inspect(
        &local_path(&snapshot),
        &local_path(&snapshot.join("configuration.toml")),
    )
    .map_err(|diagnostic| Failure {
        diagnostic,
        exit: 2,
    })?;
    check_workspace(&snapshot)?;
    // Keep snapshot read handles open throughout both builds, denying concurrent writes/deletes.
    let mut locks = vec![];
    for input in &inputs {
        let file = locked_read(&snapshot.join(&input.path))?;
        if hash(&fs::read(snapshot.join(&input.path))?) != input.sha256 {
            return Err(Failure::new(
                "INPUT_CHANGED",
                "Snapshot input changed before locking",
                3,
            ));
        }
        locks.push(file);
    }
    let mut env = environment(&stage.join("cargo-home"));
    fs::create_dir(stage.join("cargo-home"))?;
    let cargo_path = run(
        &rustup,
        &strings(&["which", "cargo"]),
        &snapshot,
        &stage.join("logs/locate-cargo"),
        &env,
    )?;
    let rustc_path = run(
        &rustup,
        &strings(&["which", "rustc"]),
        &snapshot,
        &stage.join("logs/locate-rustc"),
        &env,
    )?;
    let cargo = PathBuf::from(cargo_path.trim());
    let rustc = PathBuf::from(rustc_path.trim());
    if !cargo.is_absolute() || !rustc.is_absolute() {
        return Err(Failure::new(
            "TOOL_IDENTITY",
            "rustup returned a nonabsolute tool path",
            3,
        ));
    }
    env.push(("RUSTC".into(), rustc.as_os_str().into()));
    let cargo_version = run(
        &cargo,
        &strings(&["--version"]),
        &snapshot,
        &stage.join("logs/cargo-version"),
        &env,
    )?;
    let rustc_version = run(
        &rustc,
        &strings(&["-vV"]),
        &snapshot,
        &stage.join("logs/rustc-version"),
        &env,
    )?;
    let sysroot = run(
        &rustc,
        &strings(&["--print", "sysroot"]),
        &snapshot,
        &stage.join("logs/sysroot"),
        &env,
    )?;
    if !Path::new(sysroot.trim())
        .join("lib/rustlib/aarch64-unknown-none-softfloat/lib")
        .is_dir()
    {
        return Err(Failure::new(
            "TARGET_MISSING",
            "Install aarch64-unknown-none-softfloat for the selected toolchain",
            3,
        ));
    }
    let mut artifacts = vec![];
    for (variant, name) in [
        ("normal", "kernel.elf"),
        ("panic-test", "kernel-panic-test.elf"),
    ] {
        if CANCELLED.load(Ordering::SeqCst) {
            return Err(Failure::new(
                "CANCELLED",
                "Build cancelled before compilation",
                7,
            ));
        }
        let target_dir = stage
            .join("c")
            .join(if variant == "normal" { "n" } else { "p" });
        let mut args = strings(&[
            "build",
            "--locked",
            "--offline",
            "--release",
            "--manifest-path",
        ]);
        args.push(
            local_path(&snapshot.join("Cargo.toml"))
                .display()
                .to_string(),
        );
        args.extend(strings(&[
            "-p",
            "rustos-kernel",
            "--target",
            "aarch64-unknown-none-softfloat",
            "--target-dir",
        ]));
        args.push(local_path(&target_dir).display().to_string());
        if variant == "panic-test" {
            args.extend(strings(&["--features", "panic-test"]));
        }
        run(
            &cargo,
            &args,
            &snapshot,
            &stage.join("logs").join(variant),
            &env,
        )
        .map_err(|mut failure| {
            failure.diagnostic.stage = "compilation".into();
            failure
        })?;
        let bytes =
            checked_file(&target_dir.join("aarch64-unknown-none-softfloat/release/rustos-kernel"))?;
        check_elf(&bytes).map_err(|message| Failure::new("ARTIFACT_INVALID", &message, 4))?;
        write_new(&stage.join(name), &bytes)?;
        artifacts.push(json!({"id":if variant=="normal" {"kernel"} else {"kernel-panic-test"},"variant":variant,"path":name,"sha256":hash(&bytes),"size_bytes":bytes.len()}));
    }
    if artifacts[0]["sha256"] == artifacts[1]["sha256"] {
        return Err(Failure::new(
            "VARIANT_IDENTITY",
            "Normal and deliberate-panic artifacts must differ",
            4,
        ));
    }
    let profile: Profile = toml::from_str(&fs::read_to_string(
        snapshot.join("profiles/qemu-virt-a53.toml"),
    )?)
    .map_err(|e| Failure::new("PROFILE_INVALID", &e.to_string(), 2))?;
    inputs.sort_by(|a, b| a.path.cmp(&b.path));
    let manifest = json!({"schema_version":1,"bundle_id":bundle_id,"created_at":stamp(),"complete":true,"target":{"id":profile.id,"version":profile.version,"architecture":profile.architecture,"rust_target":profile.rust_target},"requested_features":snapshot_inspection.plan.requested_features,"resolved_modules":snapshot_inspection.plan.resolved_modules,"inputs":inputs,"tools":[{"name":"cargo","version":cargo_version.trim()},{"name":"rustc","version":rustc_version.trim()}],"artifacts":artifacts,"verification_recipe":snapshot_inspection.plan.verification_recipe});
    let bytes = serde_json::to_vec_pretty(&manifest).unwrap();
    write_new(&stage.join("manifest.json"), &bytes)?;
    if CANCELLED.load(Ordering::SeqCst) {
        return Err(Failure::new(
            "CANCELLED",
            "Build cancelled before publication",
            7,
        ));
    }
    drop(locks);
    fs::remove_file(stage.join("incomplete.json"))?;
    publish(&stage, &output)?;
    *staging = None;
    Ok((
        json!({"manifest_path":local_path(&output.join("manifest.json")).display().to_string(),"manifest_sha256":hash(&bytes)}),
        profile.id,
    ))
}

pub fn execute(repo: &Path, config: &Path) -> (Value, i32) {
    if let Err(error) = ctrlc::set_handler(|| CANCELLED.store(true, Ordering::SeqCst)) {
        return (
            json!({"schema_version":1,"operation":"build","status":"failed","target":null,"build_ready":null,"diagnostics":[Diagnostic::error("SIGNAL_HANDLER",&error.to_string(),"build")],"result":null,"evidence":[]}),
            8,
        );
    }
    let mut staging = None;
    match perform(repo, config, &mut staging) {
        Ok((result, target)) => (
            json!({"schema_version":1,"operation":"build","status":"passed","target":target,"build_ready":true,"diagnostics":[info("COMPILATION_PASSED","compilation","Normal and deliberate-panic kernels compiled"),info("PACKAGING_PASSED","packaging","Checked artifacts and manifest published without replacement"),info("VERIFICATION_NOT_RUN","verification","Emulator verification was not requested by build; run verify separately")],"result":result,"evidence":[]}),
            0,
        ),
        Err(failure) => {
            let status = match failure.exit {
                6 => "timed_out",
                7 => "cancelled",
                _ => "failed",
            };
            let mut diagnostics = vec![failure.diagnostic];
            if diagnostics[0].stage == "compilation" {
                diagnostics.push(info(
                    "PACKAGING_SKIPPED",
                    "packaging",
                    "Compilation did not complete; publication skipped",
                ));
            }
            diagnostics.push(info(
                "VERIFICATION_NOT_RUN",
                "verification",
                "No emulator verification was run by this build operation",
            ));
            let mut exit = failure.exit;
            let mut evidence = vec![];
            if let Some(stage) = staging {
                if !stage.join("incomplete.json").exists() {
                    if let Err(error) = write_new(
                        &stage.join("incomplete.json"),
                        b"{\"schema_version\":1,\"operation\":\"build\",\"complete\":false}",
                    ) {
                        diagnostics.push(Diagnostic::error(
                            "REPORT_FAILED",
                            &error.to_string(),
                            "build",
                        ));
                        exit = 8;
                    }
                }
                let record = stage.join("failure.json");
                let base = config
                    .canonicalize()
                    .ok()
                    .and_then(|p| p.parent().map(Path::to_path_buf));
                if let Some(relative) = base
                    .as_ref()
                    .and_then(|base| record.strip_prefix(base).ok())
                {
                    evidence.push(relative.to_string_lossy().replace('\\', "/"));
                }
                if let Err(error)=write_new(&record,&serde_json::to_vec_pretty(&json!({"schema_version":1,"operation":"build","complete":false,"status":status,"finished_at":stamp(),"diagnostics":diagnostics})).unwrap()) { diagnostics.push(Diagnostic::error("REPORT_FAILED",&error.to_string(),"build")); exit=8; }
            }
            (
                json!({"schema_version":1,"operation":"build","status":status,"target":null,"build_ready":false,"diagnostics":diagnostics,"result":null,"evidence":evidence}),
                exit,
            )
        }
    }
}
