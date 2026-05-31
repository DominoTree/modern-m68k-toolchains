use std::process::Command;

fn main() {
    let out = Command::new("rustc")
        .args(["-vV"])
        .output()
        .expect("failed to run rustc -vV");
    let stdout = String::from_utf8_lossy(&out.stdout);

    let mut release = String::from("?");
    let mut llvm = String::from("?");
    for line in stdout.lines() {
        if let Some(v) = line.strip_prefix("release: ") {
            release = v.trim().to_string();
        } else if let Some(v) = line.strip_prefix("LLVM version: ") {
            llvm = v.trim().to_string();
        }
    }

    // form_alert lines max 30 chars each.
    let rustc_line = truncate(&format!("rustc {release}"), 30);
    let llvm_line = truncate(&format!("LLVM {llvm}"), 30);

    println!("cargo:rustc-env=BUILD_RUSTC={rustc_line}");
    println!("cargo:rustc-env=BUILD_LLVM={llvm_line}");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=RUSTUP_TOOLCHAIN");
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max { s.to_string() } else { s[..max].to_string() }
}
