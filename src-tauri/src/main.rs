//! Shadow Agent Desktop App — Tauri v2 Main Entry Point
//!
//! This file sets up the Tauri application with:
//! - Python FastAPI backend sidecar management (auto-start on launch)
//! - Custom Tauri commands for frontend integration
//! - Native file dialog support
//! - Proper exit handling
//! - File logging for diagnostics (even in release mode)

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::process::Command;
use std::sync::{Arc, Mutex};
use tauri::Emitter;
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_shell::ShellExt;

const BACKEND_PORT: u16 = 8765;

// ═══════════════════════════════════════════════════════════════
//  File Logger — writes to %APPDATA%/com.shadowagent.desktop/
// ═══════════════════════════════════════════════════════════════

struct FileLogger {
    file: Mutex<Option<File>>,
}

impl FileLogger {
    fn new() -> Self {
        let file = Self::get_log_file();
        Self {
            file: Mutex::new(file.ok()),
        }
    }

    fn get_log_file() -> Result<File, std::io::Error> {
        let log_dir = Self::get_log_dir()?;
        fs::create_dir_all(&log_dir)?;

        // Create a timestamped log file
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let log_path = log_dir.join(format!("shadowagent_{}.log", now));

        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)?;

        // latest.log is now updated on each log write (see log() method)
        Ok(file)
    }

    fn get_log_dir() -> Result<std::path::PathBuf, std::io::Error> {
        #[cfg(target_os = "windows")]
        {
            let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
            Ok(std::path::PathBuf::from(appdata)
                .join("com.shadowagent.desktop")
                .join("logs"))
        }
        #[cfg(not(target_os = "windows"))]
        {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            Ok(std::path::PathBuf::from(home)
                .join(".shadowagent")
                .join("logs"))
        }
    }

    fn log(&self, level: &str, msg: &str) {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let line = format!("[{}] {:10} {}\n", timestamp, level, msg);

        // Write to file
        if let Ok(mut guard) = self.file.lock() {
            if let Some(ref mut f) = *guard {
                let _ = f.write_all(line.as_bytes());
                let _ = f.flush();
            }
        }

        // Also append to latest.log for easy access
        if let Ok(log_dir) = Self::get_log_dir() {
            let latest_path = log_dir.join("latest.log");
            if let Ok(mut latest) = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&latest_path)
            {
                let _ = latest.write_all(line.as_bytes());
            }
        }

        // Also print to stderr (console)
        eprint!("{}", line);
    }
}

unsafe impl Send for FileLogger {}
unsafe impl Sync for FileLogger {}

static LOGGER: std::sync::OnceLock<FileLogger> = std::sync::OnceLock::new();

fn log_info(msg: &str) {
    if let Some(logger) = LOGGER.get() {
        logger.log("INFO", msg);
    }
}

fn log_warn(msg: &str) {
    if let Some(logger) = LOGGER.get() {
        logger.log("WARN", msg);
    }
}

fn log_error(msg: &str) {
    if let Some(logger) = LOGGER.get() {
        logger.log("ERROR", msg);
    }
}

/// Show a Windows message box with an error (fallback when Tauri dialog isn't available)
#[cfg(target_os = "windows")]
fn show_error_box(title: &str, message: &str) {
    // Use PowerShell to show a message box — works even without Tauri
    let _ = std::process::Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            &format!(
                "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('{}', '{}', 'OK', 'Error')",
                message.replace('\'', "''"),
                title.replace('\'', "''")
            ),
        ])
        .spawn();
}

#[cfg(not(target_os = "windows"))]
fn show_error_box(title: &str, message: &str) {
    eprintln!("{}: {}", title, message);
}

// ═══════════════════════════════════════════════════════════════
//  State types
// ═══════════════════════════════════════════════════════════════

/// Tracks the backend sidecar process state
struct BackendState {
    running: bool,
    pid: Option<u32>,
    child_pid: Option<u32>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            running: false,
            pid: None,
            child_pid: None,
        }
    }
}

/// Application state shared across commands
struct AppState {
    backend: Arc<Mutex<BackendState>>,
}

// ═══════════════════════════════════════════════════════════════
//  Command response types
// ═══════════════════════════════════════════════════════════════

#[derive(Serialize, Deserialize)]
struct BackendStatus {
    running: bool,
    pid: Option<u32>,
    port: u16,
}

#[derive(Serialize, Deserialize)]
struct AppVersion {
    version: String,
    name: String,
}

#[derive(Serialize, Deserialize)]
struct FileFilter {
    name: String,
    extensions: Vec<String>,
}

#[derive(Serialize, Deserialize)]
struct FileDialogResult {
    paths: Option<Vec<String>>,
}

// ═══════════════════════════════════════════════════════════════
//  Helper: Kill a process by PID (cross-platform)
// ═══════════════════════════════════════════════════════════════

fn kill_process(pid: u32) {
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string()])
            .output();
    }
    #[cfg(unix)]
    {
        // Try SIGTERM first for graceful shutdown
        let _ = Command::new("kill")
            .args(["-15", &pid.to_string()])
            .output();
        // Wait up to 3 seconds for graceful shutdown
        let mut exited = false;
        for _ in 0..15 {
            std::thread::sleep(std::time::Duration::from_millis(200));
            let check = Command::new("kill")
                .args(["-0", &pid.to_string()])
                .output();
            if check.is_err() || !check.unwrap().status.success() {
                exited = true;
                break;
            }
        }
        if !exited {
            // Force kill as last resort
            let _ = Command::new("kill")
                .args(["-9", &pid.to_string()])
                .output();
        }
    }
}

// ═══════════════════════════════════════════════════════════════
//  Tauri Commands
// ═══════════════════════════════════════════════════════════════

/// Start the Python backend sidecar process
#[tauri::command]
async fn start_backend(app: tauri::AppHandle, state: tauri::State<'_, AppState>) -> Result<bool, String> {
    let mut backend = state.backend.lock().map_err(|e| e.to_string())?;

    if backend.running {
        log_info(&format!("Backend already running (pid: {:?})", backend.pid));
        return Ok(true);
    }

    // Get the path to the backend executable from resources
    let resource_path = app.path().resource_dir().map_err(|e| e.to_string())?;
    let backend_exe = resource_path.join("binaries").join("backend-x86_64-pc-windows-msvc.exe");
    
    log_info(&format!("Looking for backend at: {:?}", backend_exe));

    // Fallback to current directory for development
    let exe_path = if backend_exe.exists() {
        backend_exe
    } else {
        // Try current directory
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|p| p.to_path_buf()))
            .unwrap_or_default()
            .join("binaries")
            .join("backend-x86_64-pc-windows-msvc.exe")
    };

    log_info(&format!("Backend executable path: {:?}", exe_path));

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;

        let child = std::process::Command::new(&exe_path)
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))?;

        let pid = child.id();
        backend.running = true;
        backend.pid = Some(pid);
        backend.child_pid = Some(pid);
        log_info(&format!("Backend started with PID: {}", pid));

        let app_handle = app.clone();
        let backend_arc = state.backend.clone();
        tauri::async_runtime::spawn(async move {
            // Wait for the child to exit
            let result = child.wait();
            log_warn(&format!("Backend process exited: {:?}", result));
            if let Ok(mut b) = backend_arc.lock() {
                b.running = false;
                b.pid = None;
                b.child_pid = None;
            }
            let _ = app_handle.emit("backend-crashed", ());
        });

        Ok(true)
    }

    #[cfg(not(target_os = "windows"))]
    {
        let child = std::process::Command::new(&exe_path)
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))?;

        let pid = child.id();
        backend.running = true;
        backend.pid = Some(pid);
        backend.child_pid = Some(pid);
        log_info(&format!("Backend started with PID: {}", pid));

        let app_handle = app.clone();
        let backend_arc = state.backend.clone();
        tauri::async_runtime::spawn(async move {
            let result = child.wait();
            log_warn(&format!("Backend process exited: {:?}", result));
            if let Ok(mut b) = backend_arc.lock() {
                b.running = false;
                b.pid = None;
                b.child_pid = None;
            }
            let _ = app_handle.emit("backend-crashed", ());
        });

        Ok(true)
    }
}

/// Stop the Python backend sidecar process
#[tauri::command]
async fn stop_backend(state: tauri::State<'_, AppState>) -> Result<bool, String> {
    let mut backend = state.backend.lock().map_err(|e| e.to_string())?;

    if !backend.running {
        return Ok(true);
    }

    if let Some(pid) = backend.child_pid {
        kill_process(pid);
    }

    // Brief sleep to allow the process to actually exit
    // before we report it as not running
    std::thread::sleep(std::time::Duration::from_millis(500));

    backend.running = false;
    backend.pid = None;
    backend.child_pid = None;
    log_info("Backend sidecar stopped");
    Ok(true)
}

/// Check if the backend sidecar is running
#[tauri::command]
async fn get_backend_status(state: tauri::State<'_, AppState>) -> Result<BackendStatus, String> {
    let backend = state.backend.lock().map_err(|e| e.to_string())?;
    Ok(BackendStatus {
        running: backend.running,
        pid: backend.pid,
        port: BACKEND_PORT,
    })
}

/// Open a native file picker dialog
#[tauri::command]
async fn open_file_dialog(
    app: tauri::AppHandle,
    title: Option<String>,
    filters: Option<Vec<FileFilter>>,
    multiple: Option<bool>,
) -> Result<FileDialogResult, String> {
    use tokio::sync::oneshot;
    
    let (tx, rx) = oneshot::channel();
    let dialog = app.dialog();
    let title_str = title.unwrap_or_else(|| "Select File".to_string());

    let mut file_dialog = dialog.file();
    file_dialog = file_dialog.set_title(&title_str);

    if let Some(filter_list) = filters {
        for f in filter_list {
            let ext_strs: Vec<&str> = f.extensions.iter().map(|s| s.as_str()).collect();
            file_dialog = file_dialog.add_filter(&f.name, &ext_strs);
        }
    }

    if multiple.unwrap_or(false) {
        file_dialog.pick_files(move |result| {
            let _ = tx.send(result);
        });
    } else {
        file_dialog.pick_file(move |result| {
            let _ = tx.send(result.map(|p| vec![p]));
        });
    }
    
    let result = rx.await.map_err(|e| e.to_string())?;
    Ok(FileDialogResult {
        paths: result.map(|paths| paths.into_iter().map(|p| p.to_string()).collect()),
    })
}

/// Get the application version
#[tauri::command]
async fn get_app_version() -> Result<AppVersion, String> {
    Ok(AppVersion {
        version: env!("CARGO_PKG_VERSION").to_string(),
        name: "GenericAgent".to_string(),
    })
}

/// Check backend health via HTTP request
#[tauri::command]
async fn check_backend_health() -> Result<bool, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .map_err(|e| e.to_string())?;

    match client.get(format!("http://localhost:{}/status", BACKEND_PORT)).send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false),
    }
}

/// Minimize the main window
#[tauri::command]
async fn minimize_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.minimize().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Toggle maximize/restore
#[tauri::command]
async fn toggle_maximize_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_maximized().map_err(|e| e.to_string())? {
            window.unmaximize().map_err(|e| e.to_string())?;
        } else {
            window.maximize().map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

/// Close the main window
#[tauri::command]
async fn close_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

// ═══════════════════════════════════════════════════════════════
//  Main entry point
// ═══════════════════════════════════════════════════════════════

fn main() {
    // Initialize file logger FIRST — even before env_logger
    let file_logger = FileLogger::new();
    let _ = LOGGER.set(file_logger);

    // Also initialize env_logger for any crate that uses it
    let _ = env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp_secs()
        .try_init();

    log_info(&format!("=== GenericAgent Desktop v{} ===", env!("CARGO_PKG_VERSION")));
    log_info("Starting application...");

    // Log the exe location and working directory
    if let Ok(exe) = std::env::current_exe() {
        log_info(&format!("Executable: {}", exe.display()));
    }
    if let Ok(cwd) = std::env::current_dir() {
        log_info(&format!("Working dir: {}", cwd.display()));
    }

    // Log the log file location for the user to find
    if let Ok(log_dir) = FileLogger::get_log_dir() {
        log_info(&format!("Log files location: {}", log_dir.display()));
        eprintln!("\n  Log files: {}\\latest.log\n", log_dir.display());
    }

    let backend_state = Arc::new(Mutex::new(BackendState::default()));

    let result = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .manage(AppState {
            backend: backend_state.clone(),
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            get_backend_status,
            open_file_dialog,
            get_app_version,
            check_backend_health,
            minimize_window,
            toggle_maximize_window,
            close_window,
        ])
        .setup(move |app| {
            log_info("Setup hook running...");

            // ── Auto-start the backend process ──────────────────
            // NOTE: Backend failure should NOT prevent the app from opening!
            // The window will show "backend not available" if backend fails.
            let app_handle = app.handle().clone();
            let backend_arc = backend_state.clone();

            tauri::async_runtime::spawn(async move {
                // Wait for the window to render first
                tokio::time::sleep(std::time::Duration::from_secs(2)).await;

                log_info("Auto-starting backend...");

                // Get the path to the backend executable
                let exe_path = if let Ok(resource_dir) = app_handle.path().resource_dir() {
                    let backend_path = resource_dir.join("binaries").join("backend-x86_64-pc-windows-msvc.exe");
                    if backend_path.exists() {
                        log_info(&format!("Found backend at resource path: {:?}", backend_path));
                        backend_path
                    } else {
                        log_info("Backend not in resource path, trying executable directory");
                        std::env::current_exe()
                            .ok()
                            .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                            .unwrap_or_default()
                            .join("binaries")
                            .join("backend-x86_64-pc-windows-msvc.exe")
                    }
                } else {
                    std::env::current_exe()
                        .ok()
                        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                        .unwrap_or_default()
                        .join("binaries")
                        .join("backend-x86_64-pc-windows-msvc.exe")
                };

                log_info(&format!("Backend executable path: {:?}", exe_path));

                if !exe_path.exists() {
                    log_warn(&format!("Backend executable not found: {:?}", exe_path));
                    log_warn("The app will open but backend features won't work.");
                    let _ = app_handle.emit("backend-error", "Backend executable not found".to_string());
                    return;
                }

                #[cfg(target_os = "windows")]
                {
                    use std::os::windows::process::CommandExt;
                    const CREATE_NO_WINDOW: u32 = 0x08000000;

                    match std::process::Command::new(&exe_path)
                        .creation_flags(CREATE_NO_WINDOW)
                        .spawn()
                    {
                        Ok(child) => {
                            let pid = child.id();
                            if let Ok(mut b) = backend_arc.lock() {
                                b.running = true;
                                b.pid = Some(pid);
                                b.child_pid = Some(pid);
                            }
                            log_info(&format!("Backend started with PID: {}", pid));
                            let _ = app_handle.emit("backend-started", pid.to_string());

                            // Monitor process
                            let app_h = app_handle.clone();
                            let b_arc = backend_arc.clone();
                            tauri::async_runtime::spawn(async move {
                                let result = child.wait();
                                log_warn(&format!("Backend terminated: {:?}", result));
                                if let Ok(mut b) = b_arc.lock() {
                                    b.running = false;
                                    b.pid = None;
                                    b.child_pid = None;
                                }
                                let _ = app_h.emit("backend-crashed", format!("{:?}", result));
                            });
                        }
                        Err(e) => {
                            log_error(&format!("Failed to start backend: {}", e));
                            let _ = app_handle.emit("backend-error", format!("Spawn failed: {}", e));
                        }
                    }
                }

                #[cfg(not(target_os = "windows"))]
                {
                    match std::process::Command::new(&exe_path).spawn() {
                        Ok(child) => {
                            let pid = child.id();
                            if let Ok(mut b) = backend_arc.lock() {
                                b.running = true;
                                b.pid = Some(pid);
                                b.child_pid = Some(pid);
                            }
                            log_info(&format!("Backend started with PID: {}", pid));
                            let _ = app_handle.emit("backend-started", pid.to_string());

                            let app_h = app_handle.clone();
                            let b_arc = backend_arc.clone();
                            tauri::async_runtime::spawn(async move {
                                let result = child.wait();
                                log_warn(&format!("Backend terminated: {:?}", result));
                                if let Ok(mut b) = b_arc.lock() {
                                    b.running = false;
                                    b.pid = None;
                                    b.child_pid = None;
                                }
                                let _ = app_h.emit("backend-crashed", format!("{:?}", result));
                            });
                        }
                        Err(e) => {
                            log_error(&format!("Failed to start backend: {}", e));
                            let _ = app_handle.emit("backend-error", format!("Spawn failed: {}", e));
                        }
                    }
                }
            });

            log_info("Setup complete. Window should appear now.");
            Ok(())
        })
        .build(tauri::generate_context!());

    match result {
        Ok(app) => {
            log_info("App built successfully, running event loop...");
            app.run(|app_handle, event| {
                if let tauri::RunEvent::ExitRequested { api, .. } = event {
                    let state = app_handle.state::<AppState>();
                    if let Ok(mut backend) = state.backend.lock() {
                        if backend.running {
                            log_info("Stopping backend sidecar before exit...");
                            if let Some(pid) = backend.child_pid {
                                kill_process(pid);
                            }
                            backend.running = false;
                            backend.pid = None;
                            backend.child_pid = None;
                        }
                    }
                    // Always allow exit
                    drop(api);
                }
            });
        }
        Err(e) => {
            let error_msg = format!("FATAL: Failed to build Tauri application: {}", e);
            log_error(&error_msg);
            eprintln!("\n{}\n", error_msg);

            // Show a visible error dialog
            show_error_box("GenericAgent - Startup Error", &error_msg);

            // Pause so user can read the console output
            eprintln!("\nPress Enter to close...");
            let mut input = String::new();
            let _ = std::io::stdin().read_line(&mut input);

            std::process::exit(1);
        }
    }
}
