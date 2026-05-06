# GenericAgent Sidecar Backend Binaries

This directory contains the Tauri sidecar backend executables. These are
standalone Python executables built with PyInstaller that the Tauri desktop
app launches as a child process to run the FastAPI backend on port 8765.

## Expected Files

| Platform | File |
|----------|------|
| Windows x86_64 | `backend-x86_64-pc-windows-msvc.exe` |
| Linux x86_64 | `backend-x86_64-unknown-linux-gnu` |
| macOS Intel | `backend-x86_64-apple-darwin` |
| macOS ARM | `backend-aarch64-apple-darwin` |

## Building the Sidecar

The real binaries must be built using the build scripts before the Tauri
desktop app can start the backend. Run the appropriate script for your
platform:

### Linux / macOS
```bash
bash scripts/build-sidecar.sh              # Auto-detect OS
bash scripts/build-sidecar.sh --clean      # Clean build
bash scripts/build-sidecar.sh --skip-deps  # Skip pip install
```

### Windows
```cmd
scripts\build-sidecar.bat                  # Build for Windows
scripts\build-sidecar.bat --clean          # Clean build
scripts\build-sidecar.bat --skip-deps      # Skip pip install
```

## How It Works

1. The build script takes `launch_backend.py` (also in this directory) as
   the PyInstaller entry point.
2. `launch_backend.py` locates the GenericAgent backend directory, adds it
   to `sys.path`, and starts the FastAPI server via `uvicorn`.
3. PyInstaller bundles everything into a single executable with all the
   necessary hidden imports (uvicorn, agentmain, llmcore, etc.).
4. The output is copied here with the Tauri target-triple naming convention
   so the `tauri-plugin-shell` sidecar mechanism finds it correctly.

## Prerequisites

- Python 3.10+
- pip
- The `upload/GenericAgent-v1.2.0/` directory with all backend source files

## Development Without Building

During development, you can start the backend directly:

```bash
cd upload/GenericAgent-v1.2.0
python server.py
```

Or run the launcher script directly:

```bash
python src-tauri/binaries/launch_backend.py
```

This avoids the PyInstaller build step while still testing the same
startup logic that the bundled executable uses.
