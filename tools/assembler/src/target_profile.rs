//! Strict version dispatch. Parsing Pi metadata does not enable a Pi backend.
use serde::Deserialize;

pub(crate) enum TargetProfile {
    Emulator(super::Profile),
    Pi(PiProfile),
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PiProfile {
    schema_version: u32,
    id: String,
    version: String,
    architecture: String,
    rust_target: String,
    base_modules: Vec<String>,
    supported_features: Vec<String>,
    target: PiTarget,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct PiTarget {
    kind: String,
    boot_contract: String,
    load_address: u64,
    reserved_end: u64,
    active_cores: u32,
    firmware_lock: FirmwareLock,
    packaging_recipe: String,
    verification_methods: Vec<String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct FirmwareLock {
    path: String,
    sha256: String,
}

impl TargetProfile {
    pub(crate) fn decode(value: toml::Value) -> Result<Self, String> {
        match value
            .get("schema_version")
            .and_then(toml::Value::as_integer)
        {
            Some(1) => value
                .try_into()
                .map(Self::Emulator)
                .map_err(|e: toml::de::Error| e.to_string()),
            Some(2) => value
                .try_into()
                .map(Self::Pi)
                .map_err(|e: toml::de::Error| e.to_string()),
            _ => Err("Unsupported or invalid profile schema_version".into()),
        }
    }
}

impl PiProfile {
    pub(crate) fn selection(&self) -> super::ModuleSelection {
        super::ModuleSelection {
            id: self.id.clone(),
            architecture: self.architecture.clone(),
            base_modules: self.base_modules.clone(),
            supported_features: self.supported_features.clone(),
        }
    }

    pub(crate) fn validate(&self, requested: &str) -> Result<(), String> {
        let t = &self.target;
        if self.schema_version != 2
            || self.id != requested
            || self.id != "rpi-zero2w-a53"
            || self.version != "0.1.0"
            || self.architecture != "aarch64"
            || self.rust_target != "aarch64-unknown-none-softfloat"
            || self.base_modules != ["kernel", "bsp-rpi-zero2w"]
            || self.supported_features != ["serial-console", "boot-diagnostics"]
            || t.kind != "raspberry-pi-zero2w"
            || t.boot_contract != "zero2w-el2-to-el1-v1"
            || t.load_address != 0x20_0000
            || t.reserved_end != 0x40_0000
            || t.active_cores != 1
            || t.packaging_recipe != "zero2w-mbr-fat32-v1"
            || t.verification_methods != ["image", "hardware"]
            || t.firmware_lock.path != "assets/locks/rpi-zero2w-boot-assets.lock.json"
            || t.firmware_lock.sha256
                != "537d7d3b991369db5ec4bb3475ddf37b41dd2217b56b53e44d69c163b356e850"
        {
            return Err(
                "Pi profile differs from approved M2 contracts and asset-lock identity".into(),
            );
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const PI: &str = include_str!("../../../profiles/rpi-zero2w-a53.toml");

    fn check(text: &str) -> Result<(), String> {
        match TargetProfile::decode(text.parse::<toml::Value>().map_err(|e| e.to_string())?)? {
            TargetProfile::Pi(p) => p.validate("rpi-zero2w-a53"),
            TargetProfile::Emulator(_) => Err("Wrong profile kind".into()),
        }
    }

    #[test]
    fn approved_pi_metadata_parses_without_enabling_execution() {
        check(PI).unwrap();
    }

    #[test]
    fn m1_dispatch_is_preserved() {
        let value = include_str!("../../../profiles/qemu-virt-a53.toml")
            .parse()
            .unwrap();
        let TargetProfile::Emulator(p) = TargetProfile::decode(value).unwrap() else {
            panic!("wrong kind")
        };
        super::super::profile_valid(&p, "qemu-virt-a53").unwrap();
    }

    #[test]
    fn unknown_versions_and_fields_fail_closed() {
        for text in [
            PI.replace("schema_version = 2", "schema_version = 3"),
            PI.replace("schema_version = 2", "schema_version = true"),
            format!("emulator = {{}}\n{PI}"),
            format!("{PI}\ncommand = 'run'"),
        ] {
            assert!(check(&text).is_err());
        }
    }

    #[test]
    fn changed_memory_board_and_asset_identity_are_rejected() {
        for text in [
            PI.replace("2097152", "524288"),
            PI.replace("active_cores = 1", "active_cores = 4"),
            PI.replace("bsp-rpi-zero2w", "bsp-qemu-virt"),
            PI.replace("537d7d3b", "00000000"),
        ] {
            assert!(check(&text).is_err());
        }
    }
}
