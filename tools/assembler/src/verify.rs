//! Immutable-bundle verification on Windows. No implicit build or bundle mutation.
use super::*;
use crate::{
    build::{check_elf, local_path},
    native::{self, Process},
};
use serde_json::{json, Value};
use std::{
    fs::{File, OpenOptions},
    io::{self, Read, Write},
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use time::{format_description::well_known::Rfc3339, OffsetDateTime};

static CANCELLED: AtomicBool = AtomicBool::new(false);
const LIMIT: usize = 1024 * 1024;
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Target {
    id: String,
    version: String,
    architecture: String,
    rust_target: String,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Tool {
    name: String,
    version: String,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Artifact {
    id: String,
    variant: String,
    path: String,
    sha256: String,
    size_bytes: u64,
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    schema_version: u32,
    bundle_id: String,
    created_at: String,
    complete: bool,
    target: Target,
    requested_features: Vec<String>,
    resolved_modules: Vec<Resolved>,
    inputs: Vec<Input>,
    tools: Vec<Tool>,
    artifacts: Vec<Artifact>,
    verification_recipe: RecipeIdentity,
}
struct Error {
    diagnostic: Diagnostic,
    exit: i32,
}
type VResult<T> = std::result::Result<T, Error>;
impl From<io::Error> for Error {
    fn from(value: io::Error) -> Self {
        error("VERIFY_IO", &value.to_string(), 8)
    }
}
fn error(code: &str, message: &str, exit: i32) -> Error {
    let mut diagnostic = Diagnostic::error(code, message, "verify");
    diagnostic.stage = "verification".into();
    Error { diagnostic, exit }
}
fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn sha(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn now() -> String {
    OffsetDateTime::now_utc()
        .format(
            &time::format_description::parse(
                "[year]-[month]-[day]T[hour]:[minute]:[second].[subsecond digits:3]Z",
            )
            .unwrap(),
        )
        .unwrap()
}
fn unique() -> String {
    format!(
        "v-{:x}-{:x}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    )
}
fn write_new(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut f = OpenOptions::new().write(true).create_new(true).open(path)?;
    f.write_all(bytes)?;
    f.sync_all()
}
fn stable(path: &Path, limit: usize) -> VResult<(File, Vec<u8>)> {
    if linked(&fs::symlink_metadata(path)?) {
        return Err(error(
            "UNSAFE_INPUT",
            "Linked/reparse inputs are unsupported",
            3,
        ));
    }
    let mut f = native::locked_read(path)?;
    if !f.metadata()?.is_file() || f.metadata()?.len() > limit as u64 {
        return Err(error(
            "INPUT_LIMIT",
            "Input is not a regular file within its size limit",
            3,
        ));
    }
    let mut bytes = vec![];
    Read::by_ref(&mut f)
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > limit {
        return Err(error("INPUT_LIMIT", "Input grew beyond its limit", 3));
    }
    Ok((f, bytes))
}
fn safe(base: &Path, relative: &str) -> VResult<PathBuf> {
    checked_path(base, relative, "UNSAFE_PATH").map_err(|diagnostic| Error {
        diagnostic,
        exit: 3,
    })
}
struct Prepared {
    emulator: Emulator,
    manifest: Manifest,
    manifest_bytes: Vec<u8>,
    recipe: Recipe,
    artifacts: Vec<Vec<u8>>,
    _locks: Vec<File>,
    bundle: PathBuf,
}
fn prepare(repo: &Path, path: &Path) -> VResult<Prepared> {
    let path = path
        .canonicalize()
        .map_err(|e| error("MANIFEST_INVALID", &e.to_string(), 3))?;
    let bundle = path.parent().unwrap().to_path_buf();
    if bundle
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .starts_with(".rustos-staging-")
        || bundle.join("incomplete.json").exists()
    {
        return Err(error(
            "INCOMPLETE_BUNDLE",
            "Staging/incomplete output is not consumable",
            3,
        ));
    }
    let (handle, bytes) = stable(&path, LIMIT)?;
    let manifest: Manifest =
        serde_json::from_slice(&bytes).map_err(|e| error("MANIFEST_INVALID", &e.to_string(), 3))?;
    if manifest.schema_version != 1
        || !manifest.complete
        || !id(&manifest.bundle_id)
        || manifest.bundle_id.len() > 128
        || manifest.target.id != "qemu-virt-a53"
        || !version(&manifest.target.version)
        || manifest.target.architecture != "aarch64"
        || manifest.target.rust_target != "aarch64-unknown-none-softfloat"
    {
        return Err(error(
            "MANIFEST_INVALID",
            "Unsupported schema, identity or target",
            3,
        ));
    }
    let created = OffsetDateTime::parse(&manifest.created_at, &Rfc3339)
        .map_err(|_| error("MANIFEST_INVALID", "Invalid creation timestamp", 3))?;
    if created.offset() != time::UtcOffset::UTC {
        return Err(error(
            "MANIFEST_INVALID",
            "Creation timestamp must be UTC",
            3,
        ));
    }
    ids(&manifest.requested_features, true, "requested_features").map_err(|diagnostic| Error {
        diagnostic,
        exit: 3,
    })?;
    if manifest.artifacts.len() != 2
        || manifest.inputs.is_empty()
        || manifest.inputs.len() > 4096
        || manifest.resolved_modules.is_empty()
        || manifest.tools.is_empty()
        || manifest
            .tools
            .iter()
            .any(|t| t.name.is_empty() || t.version.is_empty())
    {
        return Err(error(
            "MANIFEST_INVALID",
            "Missing or excessive manifest records",
            3,
        ));
    }
    let mut metadata = vec![];
    let profile: Profile = load(&safe(repo, "profiles/qemu-virt-a53.toml")?, &mut metadata)
        .map_err(|diagnostic| Error {
            diagnostic,
            exit: 3,
        })?;
    profile_valid(&profile, &manifest.target.id).map_err(|diagnostic| Error {
        diagnostic,
        exit: 3,
    })?;
    let recipe: Recipe = load(
        &safe(repo, "recipes/startup-and-panic-v1.toml")?,
        &mut metadata,
    )
    .map_err(|diagnostic| Error {
        diagnostic,
        exit: 3,
    })?;
    if manifest.target.version != profile.version
        || manifest.verification_recipe.id != recipe.id
        || manifest.verification_recipe.version != recipe.version
        || manifest.verification_recipe.sha256 != metadata.last().unwrap().sha256
    {
        return Err(error(
            "RECIPE_IDENTITY",
            "Manifest does not match the trusted target/recipe",
            3,
        ));
    }
    // Reuse strict recipe policy and module resolution against the captured project inputs.
    let snapshot = safe(&bundle, "source")?;
    let snapshot_inspection = inspect(
        &local_path(&snapshot),
        &local_path(&safe(&snapshot, "configuration.toml")?),
    )
    .map_err(|diagnostic| Error {
        diagnostic,
        exit: 3,
    })?;
    if serde_json::to_value(&manifest.resolved_modules).unwrap()
        != serde_json::to_value(&snapshot_inspection.plan.resolved_modules).unwrap()
        || manifest.requested_features != snapshot_inspection.plan.requested_features
        || manifest.verification_recipe.sha256
            != snapshot_inspection.plan.verification_recipe.sha256
    {
        return Err(error(
            "MANIFEST_IDENTITY",
            "Manifest selection differs from captured metadata",
            3,
        ));
    }
    let tool_names: BTreeSet<_> = manifest
        .tools
        .iter()
        .map(|tool| tool.name.as_str())
        .collect();
    if tool_names.len() != manifest.tools.len()
        || !tool_names.contains("cargo")
        || !tool_names.contains("rustc")
    {
        return Err(error(
            "MANIFEST_INVALID",
            "Distinct cargo and rustc tool identities are required",
            3,
        ));
    }
    let mut locks = vec![handle];
    let mut input_ids = BTreeSet::new();
    let mut source_total = 0usize;
    for input in &manifest.inputs {
        if !sha(&input.sha256) || !input_ids.insert(input.path.clone()) {
            return Err(error(
                "MANIFEST_INVALID",
                "Invalid/duplicate source input identity",
                3,
            ));
        }
        let (file, data) = stable(&safe(&snapshot, &input.path)?, 16 * LIMIT)?;
        source_total += data.len();
        if source_total > 64 * LIMIT {
            return Err(error(
                "INPUT_LIMIT",
                "Source identity set exceeds 64 MiB",
                3,
            ));
        }
        if hash(&data) != input.sha256 {
            return Err(error(
                "SOURCE_IDENTITY",
                "Captured source hash does not match manifest",
                3,
            ));
        }
        locks.push(file);
    }
    for required in [
        "configuration.toml",
        "Cargo.toml",
        "Cargo.lock",
        "profiles/qemu-virt-a53.toml",
        "catalog/modules.toml",
        "recipes/startup-and-panic-v1.toml",
    ] {
        if !input_ids.contains(required) {
            return Err(error(
                "MANIFEST_INVALID",
                "Required captured metadata identity is absent",
                3,
            ));
        }
    }
    let mut pending = vec![snapshot.clone()];
    let mut captured = BTreeSet::new();
    while let Some(directory) = pending.pop() {
        for entry in fs::read_dir(directory)? {
            let entry = entry?;
            let metadata = fs::symlink_metadata(entry.path())?;
            if linked(&metadata) {
                return Err(error(
                    "UNSAFE_INPUT",
                    "Captured source tree contains a reparse point",
                    3,
                ));
            }
            if metadata.is_dir() {
                pending.push(entry.path());
            } else {
                captured.insert(
                    entry
                        .path()
                        .strip_prefix(&snapshot)
                        .unwrap()
                        .to_string_lossy()
                        .replace('\\', "/"),
                );
                if captured.len() > 4096 {
                    return Err(error(
                        "INPUT_LIMIT",
                        "Captured source tree exceeds the file limit",
                        3,
                    ));
                }
            }
        }
    }
    if captured != input_ids {
        return Err(error(
            "SOURCE_IDENTITY",
            "Manifest must identify every captured source file exactly once",
            3,
        ));
    }
    let mut variants = BTreeSet::new();
    let mut paths = BTreeSet::new();
    let mut names = BTreeSet::new();
    let mut artifacts = vec![];
    for artifact in &manifest.artifacts {
        if !id(&artifact.id)
            || !sha(&artifact.sha256)
            || !["normal", "panic-test"].contains(&artifact.variant.as_str())
            || !variants.insert(&artifact.variant)
            || !paths.insert(&artifact.path)
            || !names.insert(&artifact.id)
        {
            return Err(error(
                "MANIFEST_INVALID",
                "Artifact identities/variants must be distinct and valid",
                3,
            ));
        }
        let (file, data) = stable(&safe(&bundle, &artifact.path)?, 16 * LIMIT)?;
        if data.len() as u64 != artifact.size_bytes || hash(&data) != artifact.sha256 {
            return Err(error(
                "ARTIFACT_IDENTITY",
                "Artifact size/hash does not match manifest",
                3,
            ));
        }
        check_elf(&data).map_err(|message| error("ARTIFACT_INVALID", &message, 3))?;
        locks.push(file);
        artifacts.push(data);
    }
    if manifest.artifacts[0].sha256 == manifest.artifacts[1].sha256 {
        return Err(error(
            "ARTIFACT_IDENTITY",
            "Normal and panic artifacts must differ",
            3,
        ));
    }
    Ok(Prepared {
        emulator: profile.emulator,
        manifest,
        manifest_bytes: bytes,
        recipe,
        artifacts,
        _locks: locks,
        bundle,
    })
}

pub fn marker(bytes: &[u8], expected: &str, final_read: bool) -> std::result::Result<bool, String> {
    if bytes.len() > LIMIT {
        return Err("Serial capture exceeds 1 MiB".into());
    }
    let text = match std::str::from_utf8(bytes) {
        Ok(text) => text,
        Err(e) if e.error_len().is_none() && !final_read => {
            std::str::from_utf8(&bytes[..e.valid_up_to()]).unwrap()
        }
        Err(_) => return Err("Invalid UTF-8 serial output".into()),
    };
    for forbidden in [
        "RUSTOS_BOOT_OK",
        "RUSTOS_EXPECTED_PANIC",
        "RUSTOS_UNEXPECTED_PANIC",
        "RUSTOS_EXCEPTION",
    ] {
        if forbidden != expected && text.contains(forbidden) {
            return Err(format!("Contradictory/fault marker: {forbidden}"));
        }
    }
    if text.split('\n').any(|line| line.len() > 4096) {
        return Err("Serial line exceeds 4096 bytes".into());
    }
    Ok(text.split_inclusive('\n').any(|line| {
        line.strip_suffix('\n')
            .is_some_and(|line| line.strip_suffix('\r').unwrap_or(line) == expected)
    }))
}
fn capture(path: &Path) -> io::Result<Vec<u8>> {
    let f = File::open(path)?;
    let mut bytes = vec![];
    f.take(LIMIT as u64 + 1).read_to_end(&mut bytes)?;
    Ok(bytes)
}
struct Qmp {
    pipe: File,
    buffer: Vec<u8>,
    transcript: Vec<u8>,
    greeted: bool,
    ready: bool,
}
impl Qmp {
    fn connect(name: &str, pid: u32) -> io::Result<Self> {
        let pipe = OpenOptions::new()
            .read(true)
            .write(true)
            .open(format!(r"\\.\pipe\{name}"))?;
        if native::pipe_owner(&pipe)? != pid {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "QMP pipe server is not the owned QEMU PID",
            ));
        }
        native::pipe_nonblocking(&pipe)?;
        Ok(Self {
            pipe,
            buffer: vec![],
            transcript: vec![],
            greeted: false,
            ready: false,
        })
    }
    fn send(&mut self, command: &str, id: &str) -> io::Result<()> {
        let bytes = format!("{{\"execute\":\"{command}\",\"id\":\"{id}\"}}\r\n").into_bytes();
        if self.transcript.len() + bytes.len() > LIMIT {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "QMP transcript overflow",
            ));
        }
        if self.pipe.write(&bytes)? != bytes.len() {
            return Err(io::Error::new(
                io::ErrorKind::WriteZero,
                "Incomplete nonblocking QMP command",
            ));
        }
        self.transcript.extend(bytes);
        Ok(())
    }
    fn poll(&mut self) -> io::Result<()> {
        let available = native::pipe_available(&self.pipe)? as usize;
        if available > 0 {
            if self.transcript.len() + available > LIMIT {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "QMP capture overflow",
                ));
            }
            let mut data = vec![0; available.min(65536)];
            let n = self.pipe.read(&mut data)?;
            data.truncate(n);
            self.buffer.extend(&data);
            self.transcript.extend(data);
        }
        while let Some(end) = self.buffer.iter().position(|b| *b == b'\n') {
            let line = self.buffer.drain(..=end).collect::<Vec<_>>();
            let value: Value = serde_json::from_slice(&line)
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
            if !self.greeted {
                if value.get("QMP").is_none() {
                    return Err(io::Error::new(
                        io::ErrorKind::InvalidData,
                        "Missing QMP greeting",
                    ));
                }
                self.greeted = true;
                self.send("qmp_capabilities", "capabilities")?;
            } else if value.get("error").is_some() {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "QMP command rejected",
                ));
            } else if value["id"] == "capabilities" && value.get("return").is_some() {
                self.ready = true;
            }
        }
        Ok(())
    }
}
fn diagnostic(code: &str, message: &str) -> Value {
    serde_json::to_value(error(code, message, 5).diagnostic).unwrap()
}
struct Scenario {
    step: Value,
    settled: bool,
    exit: i32,
}
fn scenario(
    qemu: &Path,
    artifact: &Artifact,
    image: &Path,
    root: &Path,
    run_id: &str,
    recipe: &Recipe,
    emulator: &Emulator,
) -> VResult<Scenario> {
    let id = if artifact.variant == "normal" {
        "startup"
    } else {
        "panic"
    };
    let expected = if id == "startup" {
        &recipe.startup_marker
    } else {
        &recipe.panic_marker
    };
    let directory = root.join(id);
    fs::create_dir(&directory)?;
    let name = format!("rustos-{run_id}-{id}");
    let args = [
        "-machine".into(),
        "virt-11.1,secure=off,virtualization=off,gic-version=2".into(),
        "-cpu".into(),
        "cortex-a53".into(),
        "-accel".into(),
        "tcg".into(),
        "-icount".into(),
        format!("shift={}", emulator.instruction_counting),
        "-smp".into(),
        "1".into(),
        "-m".into(),
        "128M".into(),
        "-display".into(),
        "none".into(),
        "-monitor".into(),
        "none".into(),
        "-serial".into(),
        "stdio".into(),
        "-nic".into(),
        "none".into(),
        "-chardev".into(),
        format!("pipe,id=qmp,path={name}"),
        "-qmp".into(),
        "chardev:qmp".into(),
        "-kernel".into(),
        local_path(image).display().to_string(),
    ];
    let process = Process::spawn(qemu, &args, &local_path(root), &directory)?;
    write_new(&directory.join("launch.json"), &serde_json::to_vec_pretty(&json!({"executable":qemu.display().to_string(),"arguments":args,"owned_pid":process.pid,"qmp_pipe":name,"instruction_counting":emulator.instruction_counting})).unwrap())?;
    let mut qmp: Option<Qmp> = None;
    let mut diagnostics = vec![];
    let mut observed = None;
    let mut status = "failed";
    let mut exit = 5;
    loop {
        if CANCELLED.load(Ordering::SeqCst) {
            status = "cancelled";
            exit = 7;
            diagnostics.push(diagnostic("CANCELLED", "Verification cancelled"));
            break;
        }
        if process.started.elapsed() >= Duration::from_millis(recipe.deadline_ms as u64) {
            status = "timed_out";
            exit = 6;
            diagnostics.push(diagnostic(
                "MARKER_TIMEOUT",
                "Expected marker was not established before deadline",
            ));
            break;
        }
        if process.exit_code()? != 259 {
            diagnostics.push(diagnostic("EARLY_EXIT", "QEMU exited before owned stop"));
            break;
        }
        if process.overflow(LIMIT as u64)? {
            diagnostics.push(diagnostic(
                "OUTPUT_LIMIT",
                "QEMU capture exceeded its per-stream limit",
            ));
            break;
        }
        if qmp.is_none() {
            match Qmp::connect(&name, process.pid) {
                Ok(channel) => qmp = Some(channel),
                Err(e) if matches!(e.raw_os_error(), Some(2 | 231)) => {}
                Err(e) => {
                    diagnostics.push(diagnostic("QMP_IDENTITY", &e.to_string()));
                    break;
                }
            }
        }
        if let Some(channel) = qmp.as_mut() {
            if let Err(e) = channel.poll() {
                diagnostics.push(diagnostic("QMP_PROTOCOL", &e.to_string()));
                break;
            }
            if channel.ready {
                match marker(&capture(&process.stdout)?, expected, false) {
                    Ok(true) => {
                        observed = Some(expected.clone());
                        status = "passed";
                        exit = 0;
                        break;
                    }
                    Ok(false) => {}
                    Err(message) => {
                        diagnostics.push(diagnostic("SERIAL_INVALID", &message));
                        break;
                    }
                }
            }
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    let mut stop_requested = false;
    if process.exit_code()? == 259 {
        if let Some(channel) = qmp.as_mut().filter(|q| q.ready) {
            match channel.send("quit", "stop") {
                Ok(()) => stop_requested = true,
                Err(e) => diagnostics.push(diagnostic("QMP_STOP", &e.to_string())),
            }
        }
    } else if status == "passed" {
        diagnostics.push(diagnostic(
            "EARLY_EXIT",
            "QEMU exited between marker and owned stop",
        ));
    }
    let stopped = if stop_requested {
        process.settle(Duration::from_millis(recipe.stop_budget_ms as u64))?
    } else {
        false
    };
    let forced = !stopped;
    if forced {
        process.terminate()?;
    }
    let actual_settled = if stopped {
        true
    } else {
        process.settle(Duration::from_millis(recipe.kill_budget_ms as u64))?
    };
    // Injection never suppresses the real cleanup above. Production builds omit the hook.
    let settled = cleanup_confirmation(actual_settled);
    if !settled {
        diagnostics.push(diagnostic(
            "CLEANUP_FAILED",
            "Owned QEMU tree settlement could not be confirmed",
        ));
        exit = 8;
        status = "failed";
    } else if forced {
        diagnostics.push(diagnostic(
            "FORCED_STOP",
            "QMP stop did not settle the process tree; owned job was terminated",
        ));
        if exit == 0 {
            exit = 5;
            status = "failed";
        }
    } else if process.exit_code()? != 0 {
        diagnostics.push(diagnostic(
            "QEMU_EXIT",
            "QEMU returned a nonzero exit after stop",
        ));
        if exit == 0 {
            exit = 5;
            status = "failed";
        }
    }
    let mut logs = vec![];
    for (stream, path) in [("stdout", &process.stdout), ("stderr", &process.stderr)] {
        let mut bytes = capture(path)?;
        if bytes.len() > LIMIT {
            diagnostics.push(diagnostic("OUTPUT_LIMIT", "Post-stop capture overflow"));
            if exit == 0 {
                exit = 5;
                status = "failed";
            }
            if settled {
                OpenOptions::new()
                    .write(true)
                    .open(path)?
                    .set_len(LIMIT as u64)?;
            }
            bytes.truncate(LIMIT);
        }
        if stream == "stdout" {
            match marker(&bytes, expected, true) {
                Ok(true) => {}
                Ok(false) => {
                    if exit == 0 {
                        diagnostics.push(diagnostic(
                            "MARKER_MISSING",
                            "Final capture lacks complete expected marker",
                        ));
                        exit = 5;
                        status = "failed";
                    }
                }
                Err(message) => {
                    diagnostics.push(diagnostic("SERIAL_INVALID", &message));
                    if exit == 0 {
                        exit = 5;
                        status = "failed";
                    }
                }
            }
        }
        logs.push(
            json!({"stream":stream,"path":format!("{id}/{stream}.log"),"sha256":hash(&bytes)}),
        );
    }
    if let Some(channel) = qmp {
        write_new(&directory.join("qmp.log"), &channel.transcript)?;
    }
    if !diagnostics.is_empty() && exit == 0 {
        exit = 5;
        status = "failed";
    }
    Ok(Scenario {
        step: json!({"id":id,"artifact_id":artifact.id,"artifact_sha256":artifact.sha256,"status":status,"deadline_ms":recipe.deadline_ms,"observed_marker":observed,"stop_requested":stop_requested,"logs":logs,"diagnostics":diagnostics}),
        settled,
        exit,
    })
}

fn qemu() -> VResult<PathBuf> {
    let from_path = std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default())
        .map(|p| p.join("qemu-system-aarch64.exe"))
        .find(|p| p.is_absolute() && p.is_file());
    from_path
        .or_else(|| {
            std::env::var_os("ProgramFiles")
                .map(PathBuf::from)
                .map(|p| p.join("qemu/qemu-system-aarch64.exe"))
                .filter(|p| p.is_file())
        })
        .ok_or_else(|| error("QEMU_MISSING", "Install QEMU 11.1.0 or add it to PATH", 3))
}
fn perform(
    repo: &Path,
    manifest_path: &Path,
    report_location: &mut Option<PathBuf>,
) -> VResult<Value> {
    let prepared = prepare(repo, manifest_path)?;
    let qemu = qemu()?;
    let relative = format!(
        ".rustos-reports/{}/{}",
        prepared.manifest.bundle_id,
        unique()
    );
    let report = safe(prepared.bundle.parent().unwrap(), &relative)?;
    fs::create_dir_all(report.parent().unwrap())?;
    fs::create_dir(&report)?;
    *report_location = Some(report.join("report.json"));
    let start = now();
    let run_id = report.file_name().unwrap().to_string_lossy().to_string();
    write_new(
        &report.join("input-manifest.json"),
        &prepared.manifest_bytes,
    )?;
    fs::create_dir(report.join("inputs"))?;
    let mut artifact_locks = vec![];
    for (artifact, bytes) in prepared.manifest.artifacts.iter().zip(&prepared.artifacts) {
        let path = report
            .join("inputs")
            .join(format!("{}.elf", artifact.variant));
        write_new(&path, bytes)?;
        artifact_locks.push(native::locked_read(&path)?);
    }
    let version = Process::spawn(
        &qemu,
        &["--version".into()],
        &local_path(&report),
        &report.join("qemu-version"),
    )?;
    let completed = version.supervise(Duration::from_secs(5), &CANCELLED, LIMIT as u64)?;
    if !completed.settled || completed.reason != native::StopReason::Exited(0) {
        return Err(error(
            "QEMU_VERSION",
            "QEMU version probe failed or did not settle",
            8,
        ));
    }
    let version_text = fs::read_to_string(&version.stdout)?;
    if version_text
        .lines()
        .next()
        .unwrap_or("")
        .split_whitespace()
        .nth(3)
        != Some("11.1.0")
    {
        return Err(error(
            "QEMU_VERSION",
            "Verification requires QEMU 11.1.0",
            3,
        ));
    }
    let mut steps = vec![];
    let mut settled = true;
    let mut exit = 0;
    let mut diagnostics = vec![];
    #[cfg(feature = "fault-injection")]
    if injected_cleanup_failure() {
        let mut notice = diagnostic(
            "TEST_FAULT_INJECTION",
            "Test-only build simulates unavailable cleanup confirmation after real owned cleanup",
        );
        notice["severity"] = "info".into();
        diagnostics.push(notice);
    }
    for variant in ["normal", "panic-test"] {
        let artifact = prepared
            .manifest
            .artifacts
            .iter()
            .find(|a| a.variant == variant)
            .unwrap();
        if exit != 0 {
            steps.push(json!({"id":"panic","artifact_id":artifact.id,"artifact_sha256":artifact.sha256,"status":"skipped","deadline_ms":prepared.recipe.deadline_ms,"observed_marker":null,"stop_requested":false,"logs":[],"diagnostics":[]}));
            continue;
        }
        match scenario(
            &qemu,
            artifact,
            &report.join("inputs").join(format!("{variant}.elf")),
            &report,
            &run_id,
            &prepared.recipe,
            &prepared.emulator,
        ) {
            Ok(result) => {
                settled &= result.settled;
                exit = result.exit;
                steps.push(result.step);
            }
            Err(failure) => {
                exit = failure.exit;
                settled = false;
                diagnostics.push(serde_json::to_value(failure.diagnostic).unwrap());
                steps.push(json!({"id":if variant=="normal" {"startup"} else {"panic"},"artifact_id":artifact.id,"artifact_sha256":artifact.sha256,"status":"failed","deadline_ms":prepared.recipe.deadline_ms,"observed_marker":null,"stop_requested":false,"logs":[],"diagnostics":[]}));
            }
        }
    }
    let status = match exit {
        0 => "passed",
        6 => "timed_out",
        7 => "cancelled",
        _ => "failed",
    };
    let result = json!({"schema_version":1,"run_id":run_id,"complete":true,"operation":"verify","target":prepared.manifest.target.id,"manifest_sha256":hash(&prepared.manifest_bytes),"verification_scope":"emulator","started_at":start,"finished_at":now(),"status":status,"steps":steps,"cleanup":{"status":if settled {"passed"} else {"failed"},"stop_budget_ms":5000,"kill_budget_ms":5000,"processes_settled":settled,"diagnostics":[]},"diagnostics":diagnostics,"evidence":["input-manifest.json","qemu-version/stdout.log"]});
    let publication = (|| -> io::Result<()> {
        write_new(
            &report.join("report.tmp"),
            &serde_json::to_vec_pretty(&result).unwrap(),
        )?;
        native::publish(&report.join("report.tmp"), &report.join("report.json"))
    })();
    if let Err(failure) = publication {
        let recovery = json!({"schema_version":1,"operation":"verify","complete":false,"failure_kind":"report-publication","attempted_report":result,"error":failure.to_string()});
        let recovered = write_new(
            &report.join("report-recovery.json"),
            &serde_json::to_vec_pretty(&recovery).unwrap(),
        )
        .is_ok();
        return Err(error("REPORT_FAILED",&format!("Could not publish terminal {} verification report: {failure}; recovery retained={recovered}",result["status"].as_str().unwrap()),8));
    }
    Ok(result)
}

#[cfg(feature = "fault-injection")]
fn injected_cleanup_failure() -> bool {
    std::env::var_os("RUSTOS_TEST_CLEANUP_UNCONFIRMED").is_some_and(|v| v == "1")
}
fn cleanup_confirmation(actual: bool) -> bool {
    #[cfg(feature = "fault-injection")]
    if injected_cleanup_failure() {
        return false;
    }
    actual
}
pub fn execute(repo: &Path, manifest: &Path) -> (Value, i32) {
    let mut location = None;
    let mut outcome = ctrlc::set_handler(|| CANCELLED.store(true, Ordering::SeqCst))
        .map_err(|e| error("SIGNAL_HANDLER", &e.to_string(), 8))
        .and_then(|_| perform(repo, manifest, &mut location));
    if let Err(failure) = &outcome {
        if let Some(path) = location.as_mut() {
            let fallback = path.with_file_name("failure.json");
            let bytes=serde_json::to_vec_pretty(&json!({"schema_version":1,"operation":"verify","complete":false,"status":"failed","diagnostics":[failure.diagnostic]})).unwrap();
            match write_new(&fallback, &bytes) {
                Ok(()) => *path = fallback,
                Err(e) => {
                    outcome = Err(error(
                        "REPORT_FAILED",
                        &format!("{}; final failure record: {e}", failure.diagnostic.message),
                        8,
                    ));
                    location = None;
                }
            }
        }
    }
    let evidence = location
        .as_ref()
        .and_then(|p| {
            manifest.canonicalize().ok().and_then(|m| {
                m.parent()
                    .and_then(Path::parent)
                    .and_then(|base| p.strip_prefix(base).ok())
                    .map(|p| p.to_string_lossy().replace('\\', "/"))
            })
        })
        .map(|p| vec![p])
        .unwrap_or_default();
    match outcome {
        Ok(report) => {
            let exit = match report["status"].as_str().unwrap() {
                "passed" => 0,
                "timed_out" => 6,
                "cancelled" => 7,
                _ => {
                    if report["cleanup"]["status"] == "failed" {
                        8
                    } else {
                        5
                    }
                }
            };
            (
                json!({"schema_version":1,"operation":"verify","status":report["status"],"target":report["target"],"build_ready":null,"diagnostics":[],"result":report,"evidence":evidence}),
                exit,
            )
        }
        Err(failure) => (
            json!({"schema_version":1,"operation":"verify","status":"failed","target":null,"build_ready":null,"diagnostics":[failure.diagnostic],"result":null,"evidence":evidence}),
            failure.exit,
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn marker_requires_complete_exact_lines() {
        assert!(!marker(b"RUSTOS_BOOT_OK", "RUSTOS_BOOT_OK", false).unwrap());
        assert!(!marker(b"prefix RUSTOS_BOOT_OK\n", "RUSTOS_BOOT_OK", true).unwrap());
        assert!(marker(b"RUSTOS_BOOT_OK\r\n", "RUSTOS_BOOT_OK", true).unwrap());
        assert!(!marker(b"RUSTOS_BOOT_OK\r\r\n", "RUSTOS_BOOT_OK", true).unwrap());
    }

    #[test]
    fn pi_commit_requires_final_lf_and_rejects_opposite_variant() {
        let prefix = b"RUSTOS_PI_CONSOLE_READY\nRUSTOS_BOOT_OK";
        assert!(!marker(prefix, "RUSTOS_BOOT_OK", true).unwrap());
        let normal = b"RUSTOS_PI_CONSOLE_READY\nRUSTOS_BOOT_OK\n";
        assert!(marker(normal, "RUSTOS_BOOT_OK", true).unwrap());
        assert!(marker(normal, "RUSTOS_EXPECTED_PANIC", true).is_err());
        let panic = b"RUSTOS_PI_CONSOLE_READY\nRUSTOS_PI_DELIBERATE_PANIC\nRUSTOS_EXPECTED_PANIC\n";
        assert!(marker(panic, "RUSTOS_EXPECTED_PANIC", true).unwrap());
        assert!(marker(panic, "RUSTOS_BOOT_OK", true).is_err());
        let contradictory = b"RUSTOS_BOOT_OK\nRUSTOS_EXPECTED_PANIC\n";
        assert!(marker(contradictory, "RUSTOS_BOOT_OK", true).is_err());
        assert!(marker(contradictory, "RUSTOS_EXPECTED_PANIC", true).is_err());
    }
    #[test]
    fn contradictions_and_limits_override_success() {
        assert!(marker(
            b"RUSTOS_BOOT_OK\nRUSTOS_EXCEPTION\n",
            "RUSTOS_BOOT_OK",
            true
        )
        .is_err());
        assert!(marker(&vec![b'x'; 4097], "RUSTOS_BOOT_OK", false).is_err());
        assert!(marker(&vec![b'\n'; LIMIT + 1], "RUSTOS_BOOT_OK", false).is_err());
    }
    #[test]
    fn utf8_fragment_is_only_allowed_while_capture_is_open() {
        assert!(!marker(&[0xe2, 0x82], "RUSTOS_BOOT_OK", false).unwrap());
        assert!(marker(&[0xe2, 0x82], "RUSTOS_BOOT_OK", true).is_err());
        assert!(marker(&[0xff], "RUSTOS_BOOT_OK", false).is_err());
    }
    #[test]
    fn qmp_rejects_a_pipe_owned_by_another_pid() {
        use windows_sys::Win32::{
            Foundation::{CloseHandle, INVALID_HANDLE_VALUE},
            Storage::FileSystem::PIPE_ACCESS_DUPLEX,
            System::Pipes::{CreateNamedPipeW, PIPE_NOWAIT, PIPE_TYPE_BYTE},
        };
        let name = format!("rustos-owner-test-{}", unique());
        let wide = native::wide(std::ffi::OsStr::new(&format!(r"\\.\pipe\{name}")));
        let handle = unsafe {
            CreateNamedPipeW(
                wide.as_ptr(),
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_NOWAIT,
                1,
                4096,
                4096,
                1000,
                std::ptr::null(),
            )
        };
        assert_ne!(handle, INVALID_HANDLE_VALUE);
        let result = Qmp::connect(&name, 0);
        unsafe {
            CloseHandle(handle);
        }
        assert!(matches!(result,Err(ref error) if error.kind()==io::ErrorKind::PermissionDenied));
    }
}
