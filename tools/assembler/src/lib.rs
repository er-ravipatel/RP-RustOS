//! Read-only metadata inspection, plus Windows execution primitives for the P5 backend.
//! `inspect` never launches a subprocess or creates output files.
use serde::{Deserialize, Serialize};
mod pi_build;
mod target_profile;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Diagnostic {
    pub code: String,
    pub severity: String,
    pub stage: String,
    pub message: String,
    pub input: Option<String>,
    pub field: Option<String>,
    pub dependency_chain: Vec<String>,
}
impl Diagnostic {
    pub fn error(code: &str, message: &str, field: &str) -> Self {
        Self {
            code: code.into(),
            severity: "error".into(),
            stage: "inspection".into(),
            message: message.into(),
            input: None,
            field: Some(field.into()),
            dependency_chain: vec![],
        }
    }
    fn at(mut self, path: &Path) -> Self {
        self.input = Some(path.display().to_string());
        self
    }
    fn chain(mut self, chain: Vec<String>) -> Self {
        self.dependency_chain = chain;
        self
    }
}
type Result<T> = std::result::Result<T, Diagnostic>;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    schema_version: u32,
    target: String,
    features: Vec<String>,
    output_dir: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Profile {
    schema_version: u32,
    id: String,
    version: String,
    architecture: String,
    rust_target: String,
    base_modules: Vec<String>,
    supported_features: Vec<String>,
    artifact_format: String,
    emulator: Emulator,
    verification: Verification,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Emulator {
    qemu_version: String,
    machine: String,
    cpu: String,
    memory_mib: u32,
    cores: u32,
    accelerator: String,
    instruction_counting: String,
    secure: bool,
    virtualization: bool,
    gic_version: u32,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Verification {
    scope: String,
    recipe: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Catalog {
    schema_version: u32,
    modules: Vec<Module>,
    features: Vec<Feature>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Module {
    id: String,
    version: String,
    kind: String,
    source_dir: String,
    #[serde(default)]
    source_overrides: BTreeMap<String, String>,
    architectures: Vec<String>,
    targets: Vec<String>,
    requires: Vec<String>,
    conflicts: Vec<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Feature {
    id: String,
    requires: Vec<String>,
}

impl Module {
    fn source_for(&self, target: &str) -> &str {
        self.source_overrides
            .get(target)
            .map(String::as_str)
            .unwrap_or(&self.source_dir)
    }
}
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Recipe {
    pub schema_version: u32,
    pub id: String,
    pub version: String,
    pub startup_marker: String,
    pub panic_marker: String,
    pub deadline_ms: u32,
    pub stop_budget_ms: u32,
    pub kill_budget_ms: u32,
    pub max_line_bytes: u32,
    pub max_stream_bytes: u32,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Input {
    pub path: String,
    pub sha256: String,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(deny_unknown_fields)]
pub struct Reason {
    pub kind: String,
    pub from: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Resolved {
    pub id: String,
    pub version: String,
    pub reasons: Vec<Reason>,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecipeIdentity {
    pub id: String,
    pub version: String,
    pub sha256: String,
}
#[derive(Debug, Serialize)]
pub struct Plan {
    pub requested_features: Vec<String>,
    pub resolved_modules: Vec<Resolved>,
    pub build_order: Vec<String>,
    pub inputs: Vec<Input>,
    pub artifact_format: String,
    pub verification_recipe: RecipeIdentity,
    pub missing_prerequisites: Vec<Diagnostic>,
}
pub struct Inspection {
    pub target: String,
    pub ready: bool,
    pub plan: Plan,
}

fn id(value: &str) -> bool {
    value.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
        && value
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
}
fn version(value: &str) -> bool {
    let parts: Vec<_> = value.split('.').collect();
    parts.len() == 3
        && parts
            .iter()
            .all(|s| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit()))
}
fn ids(values: &[String], nonempty: bool, field: &str) -> Result<()> {
    if (nonempty && values.is_empty())
        || values.iter().any(|s| !id(s))
        || values.iter().collect::<BTreeSet<_>>().len() != values.len()
    {
        return Err(Diagnostic::error(
            "SCHEMA_INVALID",
            "Expected distinct valid identifiers",
            field,
        ));
    }
    Ok(())
}
fn path_text(value: &str, code: &str) -> Result<()> {
    let invalid = value.is_empty()
        || value.starts_with('/')
        || value
            .chars()
            .any(|c| c.is_control() || "\\:<>\"|?*".contains(c))
        || value.split('/').any(|part| {
            let name = part.split('.').next().unwrap_or("").to_ascii_uppercase();
            part.is_empty()
                || [".", ".."].contains(&part)
                || part.ends_with(['.', ' '])
                || ["CON", "PRN", "AUX", "NUL"].contains(&name.as_str())
                || ((name.starts_with("COM") || name.starts_with("LPT"))
                    && name.len() == 4
                    && matches!(name.as_bytes()[3], b'1'..=b'9'))
        });
    if invalid {
        return Err(Diagnostic::error(
            code,
            "Expected a safe relative path using / separators",
            value,
        ));
    }
    Ok(())
}
fn linked(meta: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        meta.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        meta.file_type().is_symlink()
    }
}
fn checked_path(base: &Path, relative: &str, code: &str) -> Result<PathBuf> {
    path_text(relative, code)?;
    let mut path = base.to_path_buf();
    for component in relative.split('/') {
        path.push(component);
        match fs::symlink_metadata(&path) {
            Ok(meta) if linked(&meta) => {
                return Err(Diagnostic::error(
                    code,
                    "Linked/reparse path is not supported",
                    relative,
                )
                .at(&path))
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(Diagnostic::error(code, &e.to_string(), relative).at(&path)),
        }
    }
    Ok(path)
}
fn overlaps(a: &Path, b: &Path) -> bool {
    #[cfg(windows)]
    {
        let a = a.to_string_lossy().replace('\\', "/").to_lowercase();
        let b = b.to_string_lossy().replace('\\', "/").to_lowercase();
        a == b || a.starts_with(&(b.clone() + "/")) || b.starts_with(&(a + "/"))
    }
    #[cfg(not(windows))]
    {
        a.starts_with(b) || b.starts_with(a)
    }
}
fn load<T: serde::de::DeserializeOwned>(path: &Path, inputs: &mut Vec<Input>) -> Result<T> {
    load_versions(path, inputs, &[1])
}

fn load_versions<T: serde::de::DeserializeOwned>(
    path: &Path,
    inputs: &mut Vec<Input>,
    versions: &[i64],
) -> Result<T> {
    let bytes = fs::read(path)
        .map_err(|e| Diagnostic::error("INPUT_READ", &e.to_string(), "input").at(path))?;
    let text = std::str::from_utf8(&bytes)
        .map_err(|e| Diagnostic::error("CONFIG_PARSE", &e.to_string(), "input").at(path))?;
    let raw: toml::Value = toml::from_str(text)
        .map_err(|e| Diagnostic::error("CONFIG_PARSE", &e.to_string(), "input").at(path))?;
    if !raw
        .get("schema_version")
        .and_then(toml::Value::as_integer)
        .is_some_and(|v| versions.contains(&v))
    {
        return Err(Diagnostic::error(
            "CONFIG_SCHEMA_VERSION",
            &format!("schema_version must be an integer in {versions:?}"),
            "schema_version",
        )
        .at(path));
    }
    let parsed: T = toml::from_str(text).map_err(|e| {
        let message = e.to_string();
        let code = if message.contains("unknown field") {
            "CONFIG_UNKNOWN_FIELD"
        } else {
            "SCHEMA_INVALID"
        };
        Diagnostic::error(code, &message, "input").at(path)
    })?;
    inputs.push(Input {
        path: path.display().to_string(),
        sha256: format!("{:x}", Sha256::digest(bytes)),
    });
    Ok(parsed)
}

fn profile_valid(profile: &Profile, target: &str) -> Result<()> {
    let e = &profile.emulator;
    if profile.schema_version != 1
        || profile.id != target
        || !version(&profile.version)
        || profile.architecture != "aarch64"
        || profile.rust_target != "aarch64-unknown-none-softfloat"
        || profile.artifact_format != "elf"
        || e.qemu_version != "11.1.0"
        || e.machine != "virt-11.1"
        || e.cpu != "cortex-a53"
        || e.memory_mib != 128
        || e.cores != 1
        || e.accelerator != "tcg"
        || e.instruction_counting != "auto"
        || e.secure
        || e.virtualization
        || e.gic_version != 2
        || profile.verification.scope != "emulator"
        || profile.verification.recipe != "startup-and-panic-v1"
    {
        return Err(Diagnostic::error(
            "PROFILE_INVALID",
            "Profile differs from the supported M1 contract or filename ID",
            "profile",
        ));
    }
    ids(&profile.base_modules, true, "base_modules")?;
    ids(&profile.supported_features, true, "supported_features")
}

fn graph_visit(
    name: &str,
    modules: &BTreeMap<String, &Module>,
    visiting: &mut Vec<String>,
    done: &mut BTreeSet<String>,
) -> Result<()> {
    if done.contains(name) {
        return Ok(());
    }
    if visiting.iter().any(|s| s == name) {
        let mut chain = visiting.clone();
        chain.push(name.into());
        return Err(
            Diagnostic::error("DEPENDENCY_CYCLE", "Module dependency cycle", "requires")
                .chain(chain),
        );
    }
    let module = modules.get(name).ok_or_else(|| {
        Diagnostic::error("MODULE_UNKNOWN", "Unknown module dependency", "requires")
            .chain(vec![name.into()])
    })?;
    visiting.push(name.into());
    for dependency in &module.requires {
        graph_visit(dependency, modules, visiting, done)?;
    }
    visiting.pop();
    done.insert(name.into());
    Ok(())
}

#[derive(Clone)]
pub(crate) struct ModuleSelection {
    id: String,
    architecture: String,
    base_modules: Vec<String>,
    supported_features: Vec<String>,
}

type CatalogResolution = (Catalog, BTreeMap<String, BTreeSet<Reason>>, Vec<String>);

fn resolve_catalog(
    root: &Path,
    selection: &ModuleSelection,
    requested_features: &[String],
    inputs: &mut Vec<Input>,
) -> Result<CatalogResolution> {
    let catalog_path = checked_path(root, "catalog/modules.toml", "CATALOG_INVALID")?;
    let catalog: Catalog = load(&catalog_path, inputs)?;
    if catalog.schema_version != 1 || catalog.modules.is_empty() || catalog.features.is_empty() {
        return Err(Diagnostic::error(
            "CATALOG_INVALID",
            "Catalog requires modules and features",
            "catalog",
        ));
    }
    let mut modules = BTreeMap::new();
    for module in &catalog.modules {
        if !id(&module.id)
            || !version(&module.version)
            || !["kernel", "hal", "bsp", "driver"].contains(&module.kind.as_str())
        {
            return Err(Diagnostic::error(
                "CATALOG_INVALID",
                "Invalid module identity, kind or version",
                "modules",
            ));
        }
        ids(&module.targets, true, "targets")?;
        ids(&module.requires, false, "requires")?;
        ids(&module.conflicts, false, "conflicts")?;
        if module.architectures.is_empty()
            || module.architectures.iter().any(|s| s.is_empty())
            || module.architectures.iter().collect::<BTreeSet<_>>().len()
                != module.architectures.len()
        {
            return Err(Diagnostic::error(
                "CATALOG_INVALID",
                "Invalid architectures",
                "architectures",
            ));
        }
        checked_path(root, &module.source_dir, "SOURCE_UNSAFE")?;
        for (target, source) in &module.source_overrides {
            if !module.targets.contains(target) {
                return Err(Diagnostic::error(
                    "CATALOG_INVALID",
                    "Source override names an unsupported module target",
                    "source_overrides",
                ));
            }
            checked_path(root, source, "SOURCE_UNSAFE")?;
        }
        if modules.insert(module.id.clone(), module).is_some() {
            return Err(Diagnostic::error(
                "MODULE_DUPLICATE",
                "Duplicate module ID",
                "modules",
            ));
        }
    }
    let mut features = BTreeMap::new();
    for feature in &catalog.features {
        if !id(&feature.id) {
            return Err(Diagnostic::error(
                "CATALOG_INVALID",
                "Invalid feature ID",
                "features",
            ));
        }
        ids(&feature.requires, true, "feature.requires")?;
        if features.insert(feature.id.clone(), feature).is_some() {
            return Err(Diagnostic::error(
                "FEATURE_DUPLICATE",
                "Duplicate feature ID",
                "features",
            ));
        }
    }
    for feature in &selection.supported_features {
        if !features.contains_key(feature) {
            return Err(Diagnostic::error(
                "FEATURE_UNKNOWN",
                "Profile lists an undefined feature",
                "supported_features",
            ));
        }
    }
    // Validate the full catalog graph, including currently unselected entries.
    for module in modules.values() {
        for other in module.requires.iter().chain(module.conflicts.iter()) {
            if !modules.contains_key(other) {
                return Err(Diagnostic::error(
                    "MODULE_UNKNOWN",
                    "Unknown module in catalog edge",
                    "modules",
                )
                .chain(vec![module.id.clone(), other.clone()]));
            }
        }
    }
    for feature in features.values() {
        for other in &feature.requires {
            if !modules.contains_key(other) {
                return Err(Diagnostic::error(
                    "MODULE_UNKNOWN",
                    "Unknown feature module",
                    "requires",
                )
                .chain(vec![feature.id.clone(), other.clone()]));
            }
        }
    }
    let mut done = BTreeSet::new();
    for name in modules.keys() {
        graph_visit(name, &modules, &mut vec![], &mut done)?;
    }
    let mut reasons: BTreeMap<String, BTreeSet<Reason>> = BTreeMap::new();
    for name in &selection.base_modules {
        reasons.entry(name.clone()).or_default().insert(Reason {
            kind: "base".into(),
            from: selection.id.clone(),
        });
    }
    for name in requested_features {
        if !selection.supported_features.contains(name) {
            return Err(Diagnostic::error(
                "FEATURE_UNSUPPORTED",
                "Feature is not supported by this target",
                "features",
            )
            .chain(vec![name.clone()]));
        }
        for module in &features[name].requires {
            reasons.entry(module.clone()).or_default().insert(Reason {
                kind: "feature".into(),
                from: name.clone(),
            });
        }
    }
    let mut expanded = BTreeSet::new();
    loop {
        let next = reasons.keys().find(|s| !expanded.contains(*s)).cloned();
        let Some(name) = next else {
            break;
        };
        let module = modules.get(&name).ok_or_else(|| {
            Diagnostic::error(
                "MODULE_UNKNOWN",
                "Unknown selected/base module",
                "base_modules",
            )
            .chain(vec![name.clone()])
        })?;
        if !module.targets.contains(&selection.id)
            || !module.architectures.contains(&selection.architecture)
        {
            return Err(Diagnostic::error(
                "MODULE_INCOMPATIBLE",
                "Selected module does not support target/architecture",
                "modules",
            )
            .chain(vec![name]));
        }
        expanded.insert(name.clone());
        for dependency in &module.requires {
            reasons
                .entry(dependency.clone())
                .or_default()
                .insert(Reason {
                    kind: "dependency".into(),
                    from: name.clone(),
                });
        }
    }
    for name in reasons.keys() {
        for conflict in &modules[name].conflicts {
            if reasons.contains_key(conflict) {
                return Err(Diagnostic::error(
                    "MODULE_CONFLICT",
                    "Selected modules conflict",
                    "conflicts",
                )
                .chain(vec![name.clone(), conflict.clone()]));
            }
        }
    }
    let mut order = vec![];
    let mut ordered = BTreeSet::new();
    while ordered.len() < reasons.len() {
        let name = reasons
            .keys()
            .find(|name| {
                !ordered.contains(*name)
                    && modules[*name]
                        .requires
                        .iter()
                        .all(|dep| ordered.contains(dep))
            })
            .unwrap()
            .clone();
        ordered.insert(name.clone());
        order.push(name);
    }
    let boards: Vec<_> = reasons
        .keys()
        .filter(|id| modules[*id].kind == "bsp")
        .collect();
    if boards.len() != 1 {
        return Err(Diagnostic::error(
            "BOARD_SELECTION_INVALID",
            "Select exactly one compatible BSP",
            "base_modules",
        ));
    }
    Ok((catalog, reasons, order))
}

fn inspect_sources(
    root: &Path,
    output: &Path,
    target: &str,
    catalog: &Catalog,
    reasons: &BTreeMap<String, BTreeSet<Reason>>,
    inputs: &mut Vec<Input>,
) -> Result<Vec<Diagnostic>> {
    let modules: BTreeMap<_, _> = catalog.modules.iter().map(|m| (m.id.clone(), m)).collect();
    for protected in [
        "profiles",
        "catalog",
        "recipes",
        "tools/assembler",
        "assets",
    ] {
        if overlaps(output, &root.join(protected)) {
            return Err(Diagnostic::error(
                "OUTPUT_UNSAFE",
                "Output overlaps repository metadata or host-tool sources",
                "output_dir",
            )
            .at(output));
        }
    }
    if inputs
        .iter()
        .any(|input| overlaps(output, Path::new(&input.path)))
    {
        return Err(Diagnostic::error(
            "OUTPUT_UNSAFE",
            "Output overlaps a consumed input",
            "output_dir",
        )
        .at(output));
    }
    let mut missing = vec![];
    for name in reasons.keys() {
        let module = modules[name];
        let source_dir = module.source_for(target);
        let source = checked_path(root, source_dir, "SOURCE_UNSAFE")?;
        if overlaps(output, &source) {
            return Err(Diagnostic::error(
                "OUTPUT_UNSAFE",
                "Output overlaps selected source tree",
                "output_dir",
            )
            .at(output));
        }
        let manifest = checked_path(root, &format!("{source_dir}/Cargo.toml"), "SOURCE_UNSAFE")?;
        let library = checked_path(root, &format!("{source_dir}/src/lib.rs"), "SOURCE_UNSAFE")?;
        let binary = checked_path(root, &format!("{source_dir}/src/main.rs"), "SOURCE_UNSAFE")?;
        if !manifest.is_file() || (!library.is_file() && !binary.is_file()) {
            let mut warning = Diagnostic::error(
                "SOURCE_MISSING",
                &format!("{name} needs Cargo.toml and a default src/lib.rs or src/main.rs"),
                "source_dir",
            )
            .at(&source);
            warning.severity = "warning".into();
            missing.push(warning);
        } else {
            // P3 only supports default source layout. Validate readable package metadata.
            let bytes = fs::read(&manifest).map_err(|e| {
                Diagnostic::error("INPUT_READ", &e.to_string(), "source").at(&manifest)
            })?;
            let text = std::str::from_utf8(&bytes).map_err(|e| {
                Diagnostic::error("SOURCE_INVALID", &e.to_string(), "source").at(&manifest)
            })?;
            let value: toml::Value = toml::from_str(text).map_err(|e| {
                Diagnostic::error("SOURCE_INVALID", &e.to_string(), "source").at(&manifest)
            })?;
            if value
                .get("package")
                .and_then(|p| p.get("name"))
                .and_then(toml::Value::as_str)
                .is_none()
            {
                return Err(Diagnostic::error(
                    "SOURCE_INVALID",
                    "Source manifest needs a package name",
                    "source_dir",
                )
                .at(&manifest));
            }
            inputs.push(Input {
                path: manifest.display().to_string(),
                sha256: format!("{:x}", Sha256::digest(bytes)),
            });
            if target == "rpi-zero2w-a53"
                && name == "kernel"
                && value
                    .get("package")
                    .and_then(|p| p.get("name"))
                    .and_then(toml::Value::as_str)
                    != Some("rustos-pi-kernel")
            {
                return Err(Diagnostic::error(
                    "SOURCE_INVALID",
                    "Pi kernel mapping requires the rustos-pi-kernel package",
                    "package.name",
                )
                .at(&manifest));
            }
        }
    }
    Ok(missing)
}

pub fn inspect(repo: &Path, config: &Path) -> Result<Inspection> {
    if repo.to_string_lossy().starts_with("\\\\") {
        return Err(Diagnostic::error(
            "REPO_INVALID",
            "Use a local repository path",
            "repo",
        ));
    }
    let root = repo
        .canonicalize()
        .map_err(|e| Diagnostic::error("REPO_INVALID", &e.to_string(), "repo"))?;
    if !root.is_dir() {
        return Err(Diagnostic::error(
            "REPO_INVALID",
            "Repository must be a directory",
            "repo",
        ));
    }
    let config_path = config
        .canonicalize()
        .map_err(|e| Diagnostic::error("INPUT_READ", &e.to_string(), "config"))?;
    let mut inputs = vec![];
    let config: Config = load(&config_path, &mut inputs)?;
    if config.schema_version != 1 || !id(&config.target) {
        return Err(Diagnostic::error(
            "SCHEMA_INVALID",
            "Invalid target identifier",
            "target",
        ));
    }
    ids(&config.features, true, "features")?;
    let output = checked_path(
        config_path.parent().unwrap(),
        &config.output_dir,
        "OUTPUT_UNSAFE",
    )?;
    let profile_path = checked_path(
        &root,
        &format!("profiles/{}.toml", config.target),
        "PROFILE_INVALID",
    )?;
    if !profile_path.is_file() {
        return Err(Diagnostic::error(
            "TARGET_UNKNOWN",
            "No repository profile for requested target",
            "target",
        )
        .at(&profile_path));
    }
    let value: toml::Value = load_versions(&profile_path, &mut inputs, &[1, 2])?;
    let profile = match target_profile::TargetProfile::decode(value).map_err(|message| {
        let code = if message.contains("unknown field") {
            "CONFIG_UNKNOWN_FIELD"
        } else if message.starts_with("Unsupported or invalid profile schema_version") {
            "PROFILE_INVALID"
        } else {
            "SCHEMA_INVALID"
        };
        Diagnostic::error(code, &message, "profile").at(&profile_path)
    })? {
        target_profile::TargetProfile::Emulator(profile) => profile,
        target_profile::TargetProfile::Pi(profile) => {
            profile.validate(&config.target).map_err(|message| {
                Diagnostic::error("PROFILE_INVALID", &message, "profile").at(&profile_path)
            })?;
            let (catalog, reasons, selected) =
                resolve_catalog(&root, &profile.selection(), &config.features, &mut inputs)?;
            let missing = inspect_sources(
                &root,
                &output,
                &config.target,
                &catalog,
                &reasons,
                &mut inputs,
            )?;
            let kernel_plan = pi_build::PiKernelPlan::prepare(&profile, &catalog, &selected)?;
            let missing_text = missing
                .iter()
                .map(|d| d.message.as_str())
                .collect::<Vec<_>>()
                .join("; ");
            return Err(Diagnostic::error(
                "TARGET_BACKEND_PENDING",
                &format!("Pi metadata/module selection: {}. Typed kernel inputs: {}. Missing source prerequisites: {}. Standalone Pi entry/console is implemented; assembler snapshot build, Pi image packaging and image/hardware verification integration are pending. Asset bytes were not checked.", selected.join(", "), serde_json::to_string(&kernel_plan).expect("serializable Pi input description"), if missing_text.is_empty() { "none detected by basic layout checks" } else { &missing_text }) ,
                "target",
            ).at(&profile_path));
        }
    };
    profile_valid(&profile, &config.target)?;
    let selection = ModuleSelection {
        id: profile.id.clone(),
        architecture: profile.architecture.clone(),
        base_modules: profile.base_modules.clone(),
        supported_features: profile.supported_features.clone(),
    };
    let (catalog, reasons, order) =
        resolve_catalog(&root, &selection, &config.features, &mut inputs)?;
    let modules: BTreeMap<_, _> = catalog.modules.iter().map(|m| (m.id.clone(), m)).collect();
    let recipe_path = checked_path(
        &root,
        &format!("recipes/{}.toml", profile.verification.recipe),
        "RECIPE_INVALID",
    )?;
    let recipe: Recipe = load(&recipe_path, &mut inputs)?;
    if recipe.schema_version != 1
        || recipe.id != profile.verification.recipe
        || !version(&recipe.version)
        || recipe.startup_marker != "RUSTOS_BOOT_OK"
        || recipe.panic_marker != "RUSTOS_EXPECTED_PANIC"
        || recipe.deadline_ms != 10000
        || recipe.stop_budget_ms != 5000
        || recipe.kill_budget_ms != 5000
        || recipe.max_line_bytes != 4096
        || recipe.max_stream_bytes != 1048576
    {
        return Err(Diagnostic::error(
            "RECIPE_INVALID",
            "Recipe differs from approved M1 policy",
            "recipe",
        ));
    }
    let recipe_hash = inputs.last().unwrap().sha256.clone();
    let mut missing = inspect_sources(
        &root,
        &output,
        &config.target,
        &catalog,
        &reasons,
        &mut inputs,
    )?;
    // Read-only inspection does not run toolchain or compilation probes.
    let mut backend = Diagnostic::error("EXECUTION_PREREQUISITES_UNCHECKED", "Read-only inspection does not execute toolchain probes; build performs execution prerequisite checks", "build");
    backend.severity = "warning".into();
    missing.push(backend);
    let resolved = order
        .iter()
        .map(|name| Resolved {
            id: name.clone(),
            version: modules[name].version.clone(),
            reasons: reasons[name].iter().cloned().collect(),
        })
        .collect();
    inputs.sort_by(|a, b| a.path.cmp(&b.path));
    Ok(Inspection {
        target: config.target,
        ready: false,
        plan: Plan {
            requested_features: config.features,
            resolved_modules: resolved,
            build_order: order,
            inputs,
            artifact_format: profile.artifact_format,
            verification_recipe: RecipeIdentity {
                id: recipe.id,
                version: recipe.version,
                sha256: recipe_hash,
            },
            missing_prerequisites: missing,
        },
    })
}
#[cfg(windows)]
pub mod build;
#[cfg(windows)]
pub mod execution;
#[cfg(windows)]
pub mod native;
#[cfg(windows)]
pub mod verify;
