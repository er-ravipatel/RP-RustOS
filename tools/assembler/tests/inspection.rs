use rustos_assembler::inspect;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

fn pi_fixture() -> Fixture {
    let fixture = Fixture::new();
    fixture.edit("config.toml", "qemu-virt-a53", "rpi-zero2w-a53");
    fs::write(
        fixture.root.join("profiles/rpi-zero2w-a53.toml"),
        include_str!("../../../profiles/rpi-zero2w-a53.toml"),
    )
    .unwrap();
    fs::write(
        fixture.root.join("catalog/modules.toml"),
        include_str!("../../../catalog/modules.toml"),
    )
    .unwrap();
    fixture
}

#[test]
fn pi_profile_is_recognized_but_cannot_claim_runtime_readiness() {
    let fixture = pi_fixture();
    let error = inspect(&fixture.root, &fixture.config()).err().unwrap();
    assert_eq!(error.code, "TARGET_BACKEND_PENDING");
    assert!(error.message.contains("bsp-rpi-zero2w"));
    assert!(!error.message.contains("bsp-qemu-virt"));
    assert!(!fixture.root.join(".rustos").exists());
    assert!(!fixture.root.join("out").exists());
}

#[test]
fn pi_kernel_override_uses_its_real_manifest_and_stays_gated() {
    let fixture = pi_fixture();
    let kernel = fixture.root.join("bsp/rpi-zero2w/kernel");
    fs::create_dir_all(kernel.join("src")).unwrap();
    fs::write(
        kernel.join("Cargo.toml"),
        "[package]\nname='rustos-pi-kernel'\nversion='0.1.0'\n",
    )
    .unwrap();
    fs::write(kernel.join("src/main.rs"), "#![no_std]\n").unwrap();
    let error = inspect(&fixture.root, &fixture.config()).err().unwrap();
    assert_eq!(error.code, "TARGET_BACKEND_PENDING");
    assert!(error.message.contains("bsp/rpi-zero2w/kernel/Cargo.toml"));
    assert!(!error.message.contains("core/kernel"));
    assert!(!error.message.contains("kernel needs Cargo.toml"));
    assert!(!fixture.root.join("out").exists());
    fs::write(
        kernel.join("Cargo.toml"),
        "[package]\nname='rustos-kernel'\nversion='0.1.0'\n",
    )
    .unwrap();
    assert_eq!(
        inspect(&fixture.root, &fixture.config())
            .err()
            .unwrap()
            .code,
        "SOURCE_INVALID"
    );
}

#[test]
fn invalid_target_source_overrides_fail_closed() {
    for (key, value, code) in [
        ("rpi-zero2w-a53", "../outside", "SOURCE_UNSAFE"),
        ("rpi-zero2w-a53", "C:/outside", "SOURCE_UNSAFE"),
        ("unknown-board", "bsp/rpi-zero2w/kernel", "CATALOG_INVALID"),
        ("rpi-zero2w-a53", "core/kernel", "PI_SOURCE_MAPPING"),
    ] {
        let fixture = pi_fixture();
        fixture.edit(
            "catalog/modules.toml",
            "source_overrides = { rpi-zero2w-a53 = \"bsp/rpi-zero2w/kernel\" }",
            &format!("source_overrides = {{ {key} = \"{value}\" }}"),
        );
        assert_eq!(
            inspect(&fixture.root, &fixture.config())
                .err()
                .unwrap()
                .code,
            code
        );
    }
}

#[test]
fn pi_requires_exactly_one_board_module() {
    let fixture = pi_fixture();
    fixture.edit(
        "catalog/modules.toml",
        "id = \"bsp-rpi-zero2w\"\nversion = \"0.1.0\"\nkind = \"bsp\"",
        "id = \"bsp-rpi-zero2w\"\nversion = \"0.1.0\"\nkind = \"driver\"",
    );
    assert_eq!(
        inspect(&fixture.root, &fixture.config())
            .err()
            .unwrap()
            .code,
        "BOARD_SELECTION_INVALID"
    );
}

#[test]
fn pi_rejects_mixed_board_dependency() {
    let fixture = pi_fixture();
    fixture.edit("catalog/modules.toml", "source_dir = \"bsp/qemu-virt\"\narchitectures = [\"aarch64\"]\ntargets = [\"qemu-virt-a53\"]", "source_dir = \"bsp/qemu-virt\"\narchitectures = [\"aarch64\"]\ntargets = [\"qemu-virt-a53\", \"rpi-zero2w-a53\"]");
    fixture.edit(
        "catalog/modules.toml",
        "requires = [\"hal\", \"console-pl011\"]",
        "requires = [\"hal\", \"console-pl011\", \"bsp-qemu-virt\"]",
    );
    assert_eq!(
        inspect(&fixture.root, &fixture.config())
            .err()
            .unwrap()
            .code,
        "MODULE_CONFLICT"
    );
}

#[test]
fn pi_placeholder_source_does_not_enable_execution() {
    let fixture = pi_fixture();
    let board = fixture.root.join("bsp/rpi-zero2w");
    fs::create_dir_all(board.join("src")).unwrap();
    fs::write(
        board.join("Cargo.toml"),
        "[package]\nname='placeholder'\nversion='0.1.0'\n",
    )
    .unwrap();
    fs::write(board.join("src/lib.rs"), "#![no_std]\n").unwrap();
    let error = inspect(&fixture.root, &fixture.config()).err().unwrap();
    assert_eq!(error.code, "TARGET_BACKEND_PENDING");
    assert!(error
        .message
        .contains("Standalone Pi entry/console is implemented"));
    assert!(!error.message.contains("bsp-rpi-zero2w needs"));
}

#[test]
fn pi_malformed_board_source_is_rejected() {
    let fixture = pi_fixture();
    let board = fixture.root.join("bsp/rpi-zero2w");
    fs::create_dir_all(board.join("src")).unwrap();
    fs::write(board.join("Cargo.toml"), "not valid toml").unwrap();
    fs::write(board.join("src/lib.rs"), "#![no_std]\n").unwrap();
    assert_eq!(
        inspect(&fixture.root, &fixture.config())
            .err()
            .unwrap()
            .code,
        "SOURCE_INVALID"
    );
}

#[test]
fn pi_output_cannot_overlap_assets_or_selected_board_sources() {
    for output in ["assets", "bsp/rpi-zero2w"] {
        let fixture = pi_fixture();
        let mut config: toml::Value = fs::read_to_string(fixture.config())
            .unwrap()
            .parse()
            .unwrap();
        config["output_dir"] = toml::Value::String(output.into());
        fs::write(fixture.config(), toml::to_string(&config).unwrap()).unwrap();
        assert_eq!(
            inspect(&fixture.root, &fixture.config())
                .err()
                .unwrap()
                .code,
            "OUTPUT_UNSAFE"
        );
    }
}

struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        static SEQUENCE: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "rustos-p3-tests-{}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        for name in ["profiles", "catalog", "recipes"] {
            fs::create_dir(root.join(name)).unwrap();
        }
        fs::write(
            root.join("config.toml"),
            include_str!("../../../docs/examples/m1.toml"),
        )
        .unwrap();
        fs::write(
            root.join("profiles/qemu-virt-a53.toml"),
            include_str!("../../../docs/examples/qemu-virt-a53.toml"),
        )
        .unwrap();
        fs::write(
            root.join("catalog/modules.toml"),
            include_str!("../../../docs/examples/modules.toml"),
        )
        .unwrap();
        fs::write(
            root.join("recipes/startup-and-panic-v1.toml"),
            include_str!("../../../recipes/startup-and-panic-v1.toml"),
        )
        .unwrap();
        Self { root }
    }
    fn config(&self) -> PathBuf {
        self.root.join("config.toml")
    }
    fn edit(&self, relative: &str, old: &str, new: &str) {
        let path = self.root.join(relative);
        let text = fs::read_to_string(&path).unwrap().replace("\r\n", "\n");
        assert!(text.contains(old));
        fs::write(path, text.replacen(old, new, 1)).unwrap();
    }
    fn error(&self) -> String {
        inspect(&self.root, &self.config())
            .err()
            .expect("expected failure")
            .code
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        // Only this unique test-owned directory may be recursively removed.
        assert!(self.root.starts_with(std::env::temp_dir()));
        assert!(self
            .root
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("rustos-p3-tests-"));
        fs::remove_dir_all(&self.root).unwrap();
    }
}

#[test]
fn minimal_plan_is_deterministic_and_explains_all_reasons() {
    let f = Fixture::new();
    let result = inspect(&f.root, &f.config()).unwrap();
    assert_eq!(
        result.plan.build_order,
        ["hal", "bsp-qemu-virt", "console-pl011", "kernel"]
    );
    assert!(!result.ready);
    assert_eq!(result.plan.inputs.len(), 4);
    let kernel = result
        .plan
        .resolved_modules
        .iter()
        .find(|m| m.id == "kernel")
        .unwrap();
    assert_eq!(kernel.reasons.len(), 2); // base target plus boot-diagnostics
    assert!(!f.root.join("out").exists());
    assert_eq!(
        serde_json::to_string(&result.plan).unwrap(),
        serde_json::to_string(&inspect(&f.root, &f.config()).unwrap().plan).unwrap()
    );
}

#[test]
fn unknown_fields_and_types_are_rejected() {
    let f = Fixture::new();
    f.edit(
        "config.toml",
        "schema_version = 1",
        "schema_version = 1\narchitecture = \"aarch64\"",
    );
    assert_eq!(f.error(), "CONFIG_UNKNOWN_FIELD");
    fs::write(
        f.config(),
        "schema_version=1\ntarget=42\nfeatures=[]\noutput_dir=\"out\"",
    )
    .unwrap();
    assert_eq!(f.error(), "SCHEMA_INVALID");
}
#[test]
fn malformed_duplicate_and_unsupported_schema_fail() {
    let f = Fixture::new();
    fs::write(f.config(), "features=[").unwrap();
    assert_eq!(f.error(), "CONFIG_PARSE");
    fs::write(f.config(), "schema_version=1\nschema_version=1").unwrap();
    assert_eq!(f.error(), "CONFIG_PARSE");
    fs::write(f.config(), "schema_version=2").unwrap();
    assert_eq!(f.error(), "CONFIG_SCHEMA_VERSION");
}
#[test]
fn unknown_target_and_unsupported_feature_fail() {
    let f = Fixture::new();
    f.edit("config.toml", "qemu-virt-a53", "unknown-board");
    assert_eq!(f.error(), "TARGET_UNKNOWN");
    f.edit("config.toml", "unknown-board", "qemu-virt-a53");
    f.edit("config.toml", "serial-console", "desktop");
    assert_eq!(f.error(), "FEATURE_UNSUPPORTED");
}
#[test]
fn missing_module_has_edge_evidence() {
    let f = Fixture::new();
    f.edit(
        "catalog/modules.toml",
        "id = \"hal\"",
        "id = \"hal-renamed\"",
    );
    let error = inspect(&f.root, &f.config()).err().unwrap();
    assert_eq!(error.code, "MODULE_UNKNOWN");
    assert!(!error.dependency_chain.is_empty());
}
#[test]
fn cycles_and_self_dependencies_fail() {
    let f = Fixture::new();
    f.edit(
        "catalog/modules.toml",
        "requires = []",
        "requires = [\"kernel\"]",
    );
    assert_eq!(f.error(), "DEPENDENCY_CYCLE");
    f.edit(
        "catalog/modules.toml",
        "requires = [\"kernel\"]",
        "requires = [\"hal\"]",
    );
    assert_eq!(f.error(), "DEPENDENCY_CYCLE");
}
#[test]
fn asymmetric_selected_conflict_is_rejected() {
    let f = Fixture::new();
    f.edit(
        "catalog/modules.toml",
        "conflicts = []",
        "conflicts = [\"kernel\"]",
    );
    assert_eq!(f.error(), "MODULE_CONFLICT");
}
#[test]
fn target_and_architecture_constraints_are_enforced() {
    let f = Fixture::new();
    f.edit(
        "catalog/modules.toml",
        "architectures = [\"aarch64\"]",
        "architectures = [\"x86_64\"]",
    );
    assert_eq!(f.error(), "MODULE_INCOMPATIBLE");
    f.edit(
        "catalog/modules.toml",
        "architectures = [\"x86_64\"]",
        "architectures = [\"aarch64\"]",
    );
    f.edit(
        "catalog/modules.toml",
        "targets = [\"qemu-virt-a53\"]",
        "targets = [\"other-board\"]",
    );
    assert_eq!(f.error(), "MODULE_INCOMPATIBLE");
}
#[test]
fn duplicate_module_feature_and_requested_ids_fail() {
    let f = Fixture::new();
    f.edit(
        "catalog/modules.toml",
        "id = \"bsp-qemu-virt\"",
        "id = \"hal\"",
    );
    assert_eq!(f.error(), "MODULE_DUPLICATE");
    fs::write(
        f.root.join("catalog/modules.toml"),
        include_str!("../../../docs/examples/modules.toml"),
    )
    .unwrap();
    f.edit(
        "catalog/modules.toml",
        "id = \"boot-diagnostics\"",
        "id = \"serial-console\"",
    );
    assert_eq!(f.error(), "FEATURE_DUPLICATE");
    fs::write(
        f.root.join("catalog/modules.toml"),
        include_str!("../../../docs/examples/modules.toml"),
    )
    .unwrap();
    f.edit("config.toml", "boot-diagnostics", "serial-console");
    assert_eq!(f.error(), "SCHEMA_INVALID");
}
#[test]
fn unsafe_paths_and_source_overlap_fail() {
    for path in [
        "../outside",
        "C:/outside",
        "/absolute",
        "CON",
        "NUL.txt",
        "out/../bad",
        "hal/out",
    ] {
        let f = Fixture::new();
        f.edit("config.toml", "out/m1", path);
        assert_eq!(f.error(), "OUTPUT_UNSAFE", "{path}");
    }
}
#[test]
fn existing_output_is_not_modified_by_inspection() {
    let f = Fixture::new();
    fs::create_dir_all(f.root.join("out/m1")).unwrap();
    fs::write(f.root.join("out/m1/keep"), b"keep").unwrap();
    inspect(&f.root, &f.config()).unwrap();
    assert_eq!(fs::read(f.root.join("out/m1/keep")).unwrap(), b"keep");
}
#[test]
fn profile_id_and_nested_unknown_keys_fail() {
    let f = Fixture::new();
    f.edit(
        "profiles/qemu-virt-a53.toml",
        "id = \"qemu-virt-a53\"",
        "id = \"other-board\"",
    );
    assert_eq!(f.error(), "PROFILE_INVALID");
    f.edit(
        "profiles/qemu-virt-a53.toml",
        "id = \"other-board\"",
        "id = \"qemu-virt-a53\"",
    );
    f.edit(
        "profiles/qemu-virt-a53.toml",
        "cpu = \"cortex-a53\"",
        "cpu = \"cortex-a53\"\nshell = \"execute\"",
    );
    assert_eq!(f.error(), "CONFIG_UNKNOWN_FIELD");
}
#[test]
fn recipe_identity_is_hashed_and_policy_is_strict() {
    let f = Fixture::new();
    let result = inspect(&f.root, &f.config()).unwrap();
    assert_eq!(result.plan.verification_recipe.sha256.len(), 64);
    f.edit(
        "recipes/startup-and-panic-v1.toml",
        "deadline_ms = 10000",
        "deadline_ms = 20000",
    );
    assert_eq!(f.error(), "RECIPE_INVALID");
}

#[test]
fn approved_instruction_counting_is_required() {
    let f = Fixture::new();
    f.edit(
        "profiles/qemu-virt-a53.toml",
        "instruction_counting = \"auto\"",
        "instruction_counting = \"off\"",
    );
    assert_eq!(f.error(), "PROFILE_INVALID");
    f.edit(
        "profiles/qemu-virt-a53.toml",
        "instruction_counting = \"off\"\n",
        "",
    );
    assert_eq!(f.error(), "SCHEMA_INVALID");
}
#[test]
fn metadata_hash_tracks_exact_parsed_bytes() {
    let f = Fixture::new();
    let before = inspect(&f.root, &f.config()).unwrap();
    f.edit(
        "config.toml",
        "schema_version = 1",
        "schema_version = 1 # changed bytes",
    );
    let after = inspect(&f.root, &f.config()).unwrap();
    assert_ne!(
        before
            .plan
            .inputs
            .iter()
            .find(|i| i.path.ends_with("config.toml"))
            .unwrap()
            .sha256,
        after
            .plan
            .inputs
            .iter()
            .find(|i| i.path.ends_with("config.toml"))
            .unwrap()
            .sha256
    );
}

#[test]
fn cli_json_is_one_record_and_inspection_does_not_spawn_tools() {
    let f = Fixture::new();
    let binary = env!("CARGO_BIN_EXE_rustos");
    // An empty PATH ensures no Rust/QEMU/shell tool can be discovered by this child.
    let output = std::process::Command::new(binary)
        .args(["plan", "--repo"])
        .arg(&f.root)
        .arg("--config")
        .arg(f.config())
        .args(["--format", "json"])
        .env("PATH", "")
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["status"], "passed");
    assert_eq!(value["build_ready"], false);
    assert!(output.stderr.is_empty());
    assert!(!f.root.join("out").exists());
    let error = std::process::Command::new(binary)
        .args(["plan", "--repo"])
        .arg(&f.root)
        .args(["--format", "json"])
        .output()
        .unwrap();
    assert_eq!(error.status.code(), Some(2));
    let value: serde_json::Value = serde_json::from_slice(&error.stdout).unwrap();
    assert_eq!(value["status"], "failed");
}

#[test]
fn output_cannot_overlap_metadata_config_or_host_sources() {
    for path in [
        "profiles",
        "profiles/out",
        "catalog/out",
        "recipes/out",
        "tools/assembler/out",
        "config.toml",
    ] {
        let f = Fixture::new();
        f.edit("config.toml", "out/m1", path);
        assert_eq!(f.error(), "OUTPUT_UNSAFE", "{path}");
    }
    #[cfg(windows)]
    {
        let f = Fixture::new();
        f.edit("config.toml", "out/m1", "HAL/out");
        assert_eq!(f.error(), "OUTPUT_UNSAFE");
    }
}

#[test]
fn recipe_or_profile_cannot_silently_disappear() {
    let f = Fixture::new();
    let path = f.root.join("recipes/startup-and-panic-v1.toml");
    fs::write(&path, "schema_version=1\nid=\"startup-and-panic-v1\"").unwrap();
    assert_eq!(f.error(), "SCHEMA_INVALID");
    f.edit("profiles/qemu-virt-a53.toml", "cores = 1", "cores = 2");
    assert_eq!(f.error(), "PROFILE_INVALID");
}
