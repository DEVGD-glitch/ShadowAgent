# Shadow Agent — Release Guide

This guide walks you through creating a professional release for Shadow Agent.

## 📋 Pre-Release Checklist

### 1. Update Version Numbers
- [ ] Update `package.json` version
- [ ] Update `src-tauri/Cargo.toml` version
- [ ] Update `src-tauri/tauri.conf.json` version
- [ ] Update `CHANGELOG.md` with new features
- [ ] Update README.md version badge

### 2. Build the Application

#### Option A: Full Build (Recommended)
```bash
# From project root
bun install
bun run build
bun run tauri build
```

#### Option B: Build Scripts
```powershell
# Windows
scripts\build-exe.bat

# Linux
bash scripts/build-exe.sh
```

### 3. Locate Build Artifacts

```
src-tauri/target/release/bundle/
├── nsis/
│   └── Shadow_Agent_1.2.0_x64-setup.exe    ← Main installer (NSIS)
├── msi/
│   └── Shadow_Agent_1.2.0_x64_en-US.msi   ← MSI installer
└── app/
    └── Shadow Agent.exe                     ← Portable executable
```

### 4. Create GitHub Release

1. **Go to GitHub Releases**
   ```
   https://github.com/DEVGD-glitch/GenericAgent_Shadow/releases/new
   ```

2. **Draft New Release**
   - Tag: `v1.2.0`
   - Title: `Shadow Agent v1.2.0`
   - Target: `main` branch

3. **Write Release Notes**
   ```markdown
   ## What's New in Shadow Agent v1.2.0

   🆕 **New Features**
   - Feature 1
   - Feature 2

   🐛 **Bug Fixes**
   - Fix 1

   🔒 **Security**
   - Security update 1

   📦 **Assets**
   - Shadow_Agent_1.2.0_x64-setup.exe (Windows Installer)
   - Shadow_Agent_1.2.0_x64_en-US.msi (MSI Package)

   ## Installation

   1. Download the installer above
   2. Run the installer
   3. Launch Shadow Agent!
   ```

4. **Upload Assets**
   - Drag and drop the installers to upload them

5. **Publish Release**
   - Click "Publish release"

---

## 📱 Platform-Specific Instructions

### Windows

#### NSIS Installer (.exe)
- Recommended for most users
- One-click installation
- Creates Start Menu shortcut
- Optional desktop shortcut

#### MSI Package (.msi)
- For enterprise deployment
- Silent install support
- Group Policy compatible

```powershell
# Silent install
msiexec /i Shadow_Agent_1.2.0_x64_en-US.msi /quiet

# With logging
msiexec /i Shadow_Agent_1.2.0_x64_en-US.msi /l*v install.log
```

### macOS (Coming Soon)

```bash
# Homebrew (future)
brew install shadow-agent

# Or DMG download
# Download from Releases page
```

### Linux (Coming Soon)

```bash
# AppImage (future)
chmod +x Shadow_Agent.AppImage
./Shadow_Agent.AppImage

# Or .deb package
sudo dpkg -i shadow-agent_1.2.0_amd64.deb
```

---

## 🔧 Troubleshooting Build Issues

### Rust Not Found
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Verify
rustc --version
```

### Node.js Not Found
```bash
# Install Node.js 18+
# Download from https://nodejs.org/

# Or with nvm
nvm install 18
nvm use 18
```

### Build Fails on Windows

1. Install Visual Studio Build Tools
   ```
   winget install Microsoft.VisualStudio.2022.BuildTools
   ```

2. Select "Desktop development with C++" workload

3. Restart terminal and try again

### Sidecar Not Found

```bash
# Build the Python backend sidecar
scripts\build-sidecar.bat

# Then rebuild
bun run tauri build
```

---

## ✅ Post-Release Checklist

- [ ] Verify installer runs on clean Windows machine
- [ ] Test all major features
- [ ] Check update mechanism works
- [ ] Update documentation
- [ ] Announce on social media
- [ ] Update website (if applicable)
- [ ] Notify beta testers

---

## 📞 Support

If you encounter issues during installation:

1. Check [Troubleshooting Guide](#troubleshooting-build-issues)
2. Search [Existing Issues](https://github.com/DEVGD-glitch/GenericAgent_Shadow/issues)
3. Create [New Issue](https://github.com/DEVGD-glitch/GenericAgent_Shadow/issues/new)

---

## 📝 Versioning

We use [Semantic Versioning](https://semver.org/):

- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes

---

*Last updated: May 2025*
