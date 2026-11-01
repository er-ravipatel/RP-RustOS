use rustos_assembler::{inspect, Diagnostic, Inspection};
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::PathBuf};

fn parse(args: &[String]) -> Result<(String, PathBuf, PathBuf, String), Diagnostic> {
    let operation = args
        .first()
        .filter(|s| ["validate", "plan", "build", "verify"].contains(&s.as_str()))
        .ok_or_else(|| {
            Diagnostic::error(
                "INVOCATION",
                "Supported operations are validate, plan, build and verify",
                "operation",
            )
        })?
        .clone();
    let mut flags = BTreeMap::new();
    let input_flag = if operation == "verify" {
        "--manifest"
    } else {
        "--config"
    };
    let mut rest = args[1..].iter();
    while let Some(key) = rest.next() {
        if !["--repo", input_flag, "--format"].contains(&key.as_str()) || flags.contains_key(key) {
            return Err(Diagnostic::error(
                "INVOCATION",
                "Unknown or repeated option",
                key,
            ));
        }
        let value = rest
            .next()
            .filter(|v| !v.starts_with("--"))
            .ok_or_else(|| Diagnostic::error("INVOCATION", "Missing option value", key))?;
        flags.insert(key.clone(), value.clone());
    }
    let repo = flags
        .remove("--repo")
        .ok_or_else(|| Diagnostic::error("INVOCATION", "--repo is required", "--repo"))?;
    let config = flags.remove(input_flag).ok_or_else(|| {
        Diagnostic::error(
            "INVOCATION",
            &format!("{input_flag} is required"),
            input_flag,
        )
    })?;
    let format = flags.remove("--format").unwrap_or_else(|| "text".into());
    if !["text", "json"].contains(&format.as_str()) {
        return Err(Diagnostic::error(
            "INVOCATION",
            "Format must be text or json",
            "--format",
        ));
    }
    Ok((operation, repo.into(), config.into(), format))
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args == ["--help"] || args == ["-h"] {
        println!("rustos <validate|plan|build> --repo <directory> --config <file> [--format text|json]\nrustos verify --repo <directory> --manifest <file> [--format text|json]\nM1 execution requires Windows.");
        return;
    }
    let json_requested = args.windows(2).any(|w| w == ["--format", "json"]);
    let parsed = parse(&args);
    if let Ok((operation, repo, config, _)) = &parsed {
        if operation == "build" || operation == "verify" {
            #[cfg(windows)]
            let (mut record, mut exit) = if operation == "build" {
                rustos_assembler::build::execute(repo, config)
            } else {
                rustos_assembler::verify::execute(repo, config)
            };
            #[cfg(windows)]
            rustos_assembler::execution::record(repo, config, &mut record, &mut exit);
            #[cfg(not(windows))]
            let (record, exit) = (
                json!({"schema_version":1,"operation":operation,"status":"failed","target":null,"build_ready":if operation=="verify" {Value::Null} else {json!(false)},"diagnostics":[Diagnostic::error("UNSUPPORTED_HOST","M1 execution currently requires Windows","operation")],"result":null,"evidence":[]}),
                3,
            );
            if json_requested {
                println!("{}", serde_json::to_string_pretty(&record).unwrap());
            } else {
                println!("{}: {}", operation, record["status"].as_str().unwrap());
                if operation == "verify"
                    && record["result"]["diagnostics"]
                        .as_array()
                        .is_some_and(|items| {
                            items
                                .iter()
                                .any(|item| item["code"] == "CONTROL_TIMER_PROPOSAL")
                        })
                {
                    println!("Profile: provisional; -icount shift=auto awaits confirmation.");
                }
                if exit == 0 && operation == "build" {
                    println!(
                        "Manifest: {}",
                        record["result"]["manifest_path"].as_str().unwrap()
                    );
                }
                for diagnostic in record["diagnostics"].as_array().unwrap() {
                    eprintln!(
                        "{}: {}",
                        diagnostic["code"].as_str().unwrap(),
                        diagnostic["message"].as_str().unwrap()
                    );
                }
                for evidence in record["evidence"].as_array().unwrap() {
                    println!("Evidence: {}", evidence.as_str().unwrap());
                }
            }
            std::process::exit(exit);
        }
    }
    let operation = parsed.as_ref().map(|a| a.0.clone()).unwrap_or_else(|_| {
        args.first()
            .filter(|s| ["validate", "plan", "build", "verify"].contains(&s.as_str()))
            .cloned()
            .unwrap_or_else(|| "validate".into())
    });
    let outcome: Result<Inspection, Diagnostic> = parsed
        .as_ref()
        .map_err(Clone::clone)
        .and_then(|(_, repo, config, _)| inspect(repo, config));
    let (envelope, exit) = match outcome {
        Ok(found) => {
            let result = if operation == "plan" {
                serde_json::to_value(&found.plan).unwrap()
            } else {
                json!({"missing_prerequisites": found.plan.missing_prerequisites})
            };
            (
                json!({"schema_version":1,"operation":operation,"status":"passed","target":found.target,"build_ready":found.ready,"diagnostics":found.plan.missing_prerequisites,"result":result,"evidence":[]}),
                0,
            )
        }
        Err(error) => (
            json!({"schema_version":1,"operation":operation,"status":"failed","target":Value::Null,"build_ready":Value::Null,"diagnostics":[error],"result":Value::Null,"evidence":[]}),
            2,
        ),
    };
    if json_requested {
        println!("{}", serde_json::to_string_pretty(&envelope).unwrap());
    } else if exit == 0 {
        println!(
            "{}: passed; target {}; build_ready={}",
            operation,
            envelope["target"].as_str().unwrap(),
            envelope["build_ready"]
        );
        if let Some(order) = envelope["result"]["build_order"].as_array() {
            println!(
                "Build order: {}",
                order
                    .iter()
                    .map(|v| v.as_str().unwrap())
                    .collect::<Vec<_>>()
                    .join(" -> ")
            );
        }
        for diagnostic in envelope["diagnostics"].as_array().unwrap() {
            println!(
                "{}: {}",
                diagnostic["code"].as_str().unwrap(),
                diagnostic["message"].as_str().unwrap()
            );
        }
    } else {
        for diagnostic in envelope["diagnostics"].as_array().unwrap() {
            eprintln!(
                "{}: {}",
                diagnostic["code"].as_str().unwrap(),
                diagnostic["message"].as_str().unwrap()
            );
        }
    }
    std::process::exit(exit);
}
