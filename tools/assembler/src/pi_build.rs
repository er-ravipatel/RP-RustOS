//! Pi input preparation and internal snapshot compilation; publication stays gated.
use super::{target_profile::PiProfile, Catalog, Diagnostic, Result};
use crate::build::{self, BuildResult, Failure};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::{collections::BTreeSet, fs, path::Path};

fn invalid(message: &str) -> Failure {
    Failure::new("PI_BUILD_CONTRACT", message, 3)
}

fn validate_closure(metadata: &Value, snapshot: &Path) -> BuildResult<()> {
    let expected: BTreeSet<_> = [
        "rustos-pi-kernel",
        "rustos-bsp-rpi-zero2w",
        "rustos-console",
        "rustos-hal",
    ]
    .into_iter()
    .collect();
    let packages = metadata["packages"]
        .as_array()
        .ok_or_else(|| invalid("Cargo packages missing"))?;
    let names: BTreeSet<_> = packages.iter().filter_map(|p| p["name"].as_str()).collect();
    if packages.len() != 4 || names != expected {
        return Err(invalid(
            "Cargo package closure differs from the reviewed four packages",
        ));
    }
    let root = snapshot.canonicalize()?;
    for package in packages {
        let manifest = package["manifest_path"]
            .as_str()
            .ok_or_else(|| invalid("Cargo manifest path missing"))?;
        if package.get("source") != Some(&Value::Null)
            || !Path::new(manifest).canonicalize()?.starts_with(&root)
        {
            return Err(invalid("Cargo dependency escapes the local snapshot"));
        }
    }
    Ok(())
}

#[derive(Debug, Serialize)]
pub(crate) struct PiVariant {
    id: &'static str,
    cargo_features: Vec<&'static str>,
}

#[derive(Debug, Serialize)]
pub(crate) struct PiKernelPlan {
    target: String,
    manifest: &'static str,
    package: &'static str,
    rust_target: &'static str,
    module_sources: BTreeMap<String, String>,
    snapshot_roots: Vec<String>,
    variants: [PiVariant; 2],
    complete_bundle_ready: bool,
}

impl PiKernelPlan {
    // Internal component reserved for complete-bundle orchestration. Keeping the
    // public backend gate avoids exposing successful partial builds as bundles.
    #[cfg_attr(
        not(test),
        expect(
            dead_code,
            reason = "complete Pi bundle orchestrator is not enabled yet"
        )
    )]
    pub(crate) fn compile_snapshot(&self, repo: &Path, output: &Path) -> BuildResult<()> {
        let repo = repo.canonicalize()?;
        let parent = output
            .parent()
            .ok_or_else(|| invalid("Output parent missing"))?
            .canonicalize()?;
        let destination = parent.join(
            output
                .file_name()
                .ok_or_else(|| invalid("Output name missing"))?,
        );
        for root in &self.snapshot_roots {
            let source = repo.join(root).canonicalize()?;
            if destination.starts_with(&source) || source.starts_with(&destination) {
                return Err(invalid("Pi output overlaps selected source"));
            }
        }
        fs::create_dir(output)?; // Never reuse or replace an existing run.
        let output = build::local_path(&output.canonicalize()?);
        let snapshot = output.join("source");
        fs::create_dir(&snapshot)?;
        let mut sources = Vec::new();
        let mut total = 0;
        for root in &self.snapshot_roots {
            build::snapshot_tree(&repo, &snapshot, Path::new(root), &mut sources, &mut total)?;
        }
        let manifest = snapshot.join(self.manifest);
        build::no_ancestor_cargo_config(
            manifest
                .parent()
                .ok_or_else(|| invalid("Manifest parent missing"))?,
        )?;
        build::checked_file(&manifest.with_file_name("Cargo.lock"))?;
        let home = output.join("cargo-home");
        fs::create_dir(&home)?;
        let environment = build::environment(&home);
        let cargo = build::find("cargo")?;
        let mut tools = Vec::new();
        for name in ["cargo", "rustc"] {
            let executable = build::find(name)?;
            let logs = output.join(format!("tool-{name}"));
            fs::create_dir(&logs)?;
            let version = build::run(
                &executable,
                &["--version".into(), "--verbose".into()],
                &snapshot,
                &logs,
                &environment,
            )?;
            tools.push(json!({"executable":executable,"version":version}));
        }
        let mut records = Vec::new();
        for variant in &self.variants {
            let logs = output.join(variant.id);
            fs::create_dir(&logs)?;
            let target = logs.join("target");
            let mut common = vec![
                "--manifest-path".into(),
                manifest.display().to_string(),
                "--locked".into(),
                "--offline".into(),
            ];
            if !variant.cargo_features.is_empty() {
                common.extend(["--features".into(), variant.cargo_features.join(",")]);
            }
            let metadata_logs = logs.join("metadata");
            fs::create_dir(&metadata_logs)?;
            let mut args = vec!["metadata".into(), "--format-version".into(), "1".into()];
            args.extend(common.clone());
            let metadata: Value = serde_json::from_str(&build::run(
                &cargo,
                &args,
                &snapshot,
                &metadata_logs,
                &environment,
            )?)
            .map_err(|_| invalid("Cargo metadata is invalid JSON"))?;
            validate_closure(&metadata, &snapshot)?;
            let build_logs = logs.join("build");
            fs::create_dir(&build_logs)?;
            let mut args = vec![
                "build".into(),
                "--release".into(),
                "--package".into(),
                self.package.into(),
                "--target".into(),
                self.rust_target.into(),
                "--target-dir".into(),
                target.display().to_string(),
            ];
            args.extend(common);
            build::run(&cargo, &args, &snapshot, &build_logs, &environment)?;
            let elf = target
                .join(self.rust_target)
                .join("release")
                .join(self.package);
            let bytes = build::checked_file(&elf)?;
            if bytes.get(..4) != Some(b"\x7fELF") {
                return Err(invalid("Pi compiler did not produce an ELF"));
            }
            records.push(json!({"variant":variant.id,"features":variant.cargo_features,"elf":elf,"sha256":build::hash(&bytes),"metadata":metadata}));
        }
        for source in &sources {
            if build::hash(&build::checked_file(&snapshot.join(&source.path))?) != source.sha256 {
                return Err(invalid("Snapshot source changed during compilation"));
            }
        }
        if records[0]["sha256"] == records[1]["sha256"] {
            return Err(invalid(
                "Normal and panic artifacts have identical identity",
            ));
        }
        let bytes = serde_json::to_vec_pretty(&json!({"kind":"pi-internal-compiler","complete_bundle_ready":false,"plan":self,"sources":sources,"tools":tools,"variants":records}))
            .map_err(|_| invalid("Cannot encode Pi compiler evidence"))?;
        build::write_new(&output.join("report.json"), &bytes)?;
        Ok(())
    }
    // A PiProfile is required; an emulator profile cannot enter this path.
    pub(crate) fn prepare(
        profile: &PiProfile,
        catalog: &Catalog,
        selected: &[String],
    ) -> Result<Self> {
        let target = profile.selection().id;
        let modules: BTreeMap<_, _> = catalog.modules.iter().map(|m| (m.id.as_str(), m)).collect();
        let expected = [
            ("kernel", "bsp/rpi-zero2w/kernel"),
            ("bsp-rpi-zero2w", "bsp/rpi-zero2w"),
            ("hal", "hal"),
            ("console-pl011", "drivers/console"),
        ];
        if target != "rpi-zero2w-a53" || selected.len() != expected.len() {
            return Err(Diagnostic::error(
                "PI_SOURCE_MAPPING",
                "Pi preparation requires the reviewed four-module source closure",
                "modules",
            ));
        }
        let mut module_sources = BTreeMap::new();
        for (id, path) in expected {
            if !selected.iter().any(|name| name == id)
                || modules.get(id).map(|m| m.source_for(&target)) != Some(path)
            {
                return Err(Diagnostic::error(
                    "PI_SOURCE_MAPPING",
                    "Pi source attribution differs from its actual kernel/BSP/driver layout",
                    "source_dir",
                ));
            }
            module_sources.insert(id.to_string(), path.to_string());
        }
        let all: Vec<_> = module_sources.values().cloned().collect();
        // The kernel tree is nested in BSP; copy it once, retaining both owners.
        let snapshot_roots = all
            .iter()
            .filter(|path| {
                !all.iter()
                    .any(|parent| parent != *path && path.starts_with(&(parent.clone() + "/")))
            })
            .cloned()
            .collect();
        Ok(Self {
            target,
            manifest: "bsp/rpi-zero2w/kernel/Cargo.toml",
            package: "rustos-pi-kernel",
            rust_target: "aarch64-unknown-none-softfloat",
            module_sources,
            snapshot_roots,
            variants: [
                PiVariant {
                    id: "normal",
                    cargo_features: vec![],
                },
                PiVariant {
                    id: "panic-test",
                    cargo_features: vec!["panic-test"],
                },
            ],
            complete_bundle_ready: false,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cargo_closure_rejects_malformed_duplicate_remote_and_escaping_packages() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"));
        assert!(validate_closure(&json!({}), root).is_err());
        assert!(validate_closure(&json!({"packages":[]}), root).is_err());
        let names = [
            "rustos-pi-kernel",
            "rustos-bsp-rpi-zero2w",
            "rustos-console",
            "rustos-hal",
        ];
        let packages: Vec<_> = names
            .into_iter()
            .map(|name| json!({"name":name,"source":null,"manifest_path":root.join("Cargo.toml")}))
            .collect();
        let mut metadata = json!({"packages":packages});
        assert!(validate_closure(&metadata, root).is_ok());
        metadata["packages"][0]["source"] = json!("registry+https://example.invalid");
        assert!(validate_closure(&metadata, root).is_err());
        metadata["packages"][0]["source"] = Value::Null;
        metadata["packages"][0]["manifest_path"] =
            json!(root.parent().unwrap().parent().unwrap().join("Cargo.toml"));
        assert!(validate_closure(&metadata, root).is_err());
        metadata["packages"][0]["name"] = json!("rustos-hal");
        assert!(validate_closure(&metadata, root).is_err());
    }
    fn inputs() -> (PiProfile, Catalog, Vec<String>) {
        let value = include_str!("../../../profiles/rpi-zero2w-a53.toml")
            .parse()
            .unwrap();
        let super::super::target_profile::TargetProfile::Pi(profile) =
            super::super::target_profile::TargetProfile::decode(value).unwrap()
        else {
            panic!("wrong target")
        };
        let catalog = toml::from_str(include_str!("../../../catalog/modules.toml")).unwrap();
        (
            profile,
            catalog,
            vec![
                "hal".into(),
                "console-pl011".into(),
                "kernel".into(),
                "bsp-rpi-zero2w".into(),
            ],
        )
    }
    #[test]
    fn actual_pi_sources_are_attributed_and_nested_roots_deduplicated() {
        let (profile, catalog, selected) = inputs();
        let plan = PiKernelPlan::prepare(&profile, &catalog, &selected).unwrap();
        assert_eq!(plan.module_sources["kernel"], "bsp/rpi-zero2w/kernel");
        assert_eq!(
            plan.snapshot_roots,
            vec!["bsp/rpi-zero2w", "drivers/console", "hal"]
        );
        assert!(plan.variants[0].cargo_features.is_empty());
        assert_eq!(plan.variants[1].cargo_features, vec!["panic-test"]);
        assert!(!plan.complete_bundle_ready);
    }
    #[test]
    fn m1_kernel_attribution_and_missing_modules_fail() {
        let (profile, mut catalog, mut selected) = inputs();
        catalog
            .modules
            .iter_mut()
            .find(|m| m.id == "kernel")
            .unwrap()
            .source_overrides
            .clear();
        assert!(PiKernelPlan::prepare(&profile, &catalog, &selected).is_err());
        selected.pop();
        assert!(PiKernelPlan::prepare(&profile, &catalog, &selected).is_err());
    }

    // This invokes the production component without enabling bundle publication.
    #[test]
    #[ignore = "compiles both Pi variants using the installed cross toolchain"]
    fn isolated_offline_pi_variants() {
        let (profile, catalog, selected) = inputs();
        let plan = PiKernelPlan::prepare(&profile, &catalog, &selected).unwrap();
        let repo = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap();
        let id = std::time::SystemTime::now()
            .duration_since(std::time::SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let output = repo.join(format!("target/pi-compiler-{id}"));
        assert!(plan
            .compile_snapshot(repo, &repo.join("bsp/rpi-zero2w/forbidden-output"))
            .is_err());
        plan.compile_snapshot(repo, &output)
            .unwrap_or_else(|e| panic!("{:?}", e.diagnostic));
        assert!(plan.compile_snapshot(repo, &output).is_err());
        println!(
            "Pi compiler evidence: {}",
            output.join("report.json").display()
        );
    }
}
