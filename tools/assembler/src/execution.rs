//! Atomic local execution index consumed by the read-only dashboard server.
use super::Diagnostic;
use serde_json::{json, Value};
use std::{
    fs::{self, OpenOptions},
    io::{self, Write},
    path::Path,
    time::{SystemTime, UNIX_EPOCH},
};
pub fn record(repo: &Path, input: &Path, cli: &mut Value, exit: &mut i32) {
    let result = (|| -> io::Result<()> {
        let repo = repo.canonicalize()?;
        let index = super::checked_path(&repo, ".rustos/executions", "INDEX_PATH")
            .map_err(|d| io::Error::new(io::ErrorKind::InvalidInput, d.message))?;
        fs::create_dir_all(&index)?;
        let id = format!(
            "e-{:x}-{:x}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let input = if input.is_absolute() {
            input.to_path_buf()
        } else {
            std::env::current_dir()?.join(input)
        };
        let base = if cli["operation"] == "verify" {
            input.parent().and_then(Path::parent)
        } else {
            input.parent()
        };
        let report = if cli["operation"] == "verify" {
            cli["evidence"]
                .as_array()
                .and_then(|e| e.first())
                .and_then(Value::as_str)
                .and_then(|e| base.map(|base| base.join(e)))
        } else {
            None
        };
        let value = json!({"schema_version":1,"id":id,"input_path":input.display().to_string(),"report_path":report.map(|p|p.display().to_string()),"cli":cli});
        let temporary = index.join(format!("{id}.tmp"));
        let final_path = index.join(format!("{id}.json"));
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)?;
        file.write_all(&serde_json::to_vec_pretty(&value)?)?;
        file.sync_all()?;
        drop(file);
        super::native::publish(&temporary, &final_path)
    })();
    if let Err(error) = result {
        cli["status"] = "failed".into();
        cli["diagnostics"].as_array_mut().unwrap().push(
            serde_json::to_value(Diagnostic::error(
                "EXECUTION_INDEX",
                &error.to_string(),
                "report",
            ))
            .unwrap(),
        );
        *exit = 8;
    }
}
