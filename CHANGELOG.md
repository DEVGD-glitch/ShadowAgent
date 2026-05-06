# Changelog

All notable changes to **Shadow Agent** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-05-06

### 🚀 Added
- **Shadow Agent Rebrand**: Complete project rename from GenericAgent to Shadow Agent
- **Professional Branding**: New logo, metadata, and documentation
- **One-Click Installation**: Improved NSIS/MSI installers for easy distribution
- **GitHub Release Ready**: Complete release documentation and assets

### ✨ Features
- Multi-LLM orchestration (Claude, GPT, Gemini, Groq, and more)
- Voice interaction with free providers (Edge TTS, Pollinations)
- 3D Avatar support with VRM models
- 5-layer memory system for persistent context
- Plugin system with MCP support
- Desktop integration (system tray, keyboard shortcuts)

### 🛠️ Technical
- **Frontend**: Next.js 16, React 19, Tailwind CSS 4
- **Desktop Shell**: Tauri 2, Rust
- **Backend**: Python, FastAPI
- **AI**: Multi-provider LLM integration

### 🔒 Security
- Rate limiting on API endpoints
- CORS configuration
- WebSocket token validation
- Credential store with OS keyring support
- Ed25519 update signature verification
- API key redaction in logs

---

## [1.0.0] - 2025-01-01

### 🚀 Added
- Initial release
- GenericAgent core architecture
- Basic chat interface
- LLM integration (Claude, OpenAI)
- Tool execution system
- Memory management

---

## [Unreleased] - Future Plans

### Planned Features
- [ ] macOS/Linux native installers
- [ ] App Store distribution
- [ ] Homebrew support
- [ ] Mobile companion app
- [ ] Team collaboration features
- [ ] Cloud sync
- [ ] Custom avatar upload
- [ ] Voice cloning

### Known Issues
- None reported yet

---

## How to Update

1. Download the latest release from [GitHub Releases](https://github.com/DEVGD-glitch/GenericAgent_Shadow/releases)
2. Run the installer — your settings and memory will be preserved
3. Restart Shadow Agent if it was running

---

## Migration Notes

### v1.0.0 → v1.2.0
- Project renamed from GenericAgent to Shadow Agent
- No breaking changes to user data or settings
- API endpoints remain compatible
- Settings file location unchanged

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to Shadow Agent development.
