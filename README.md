# Shadow Agent 🌙

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![Downloads](https://img.shields.io/badge/downloads-1K%2B-green.svg)

**Shadow Agent** is your personal AI companion that thinks, learns, and evolves with you. A powerful self-evolving desktop application powered by cutting-edge AI technology.

## ✨ Why Shadow Agent?

> *"The AI assistant that doesn't just follow commands — it understands, adapts, and grows with you."*

Shadow Agent combines the intelligence of multiple large language models with a beautiful, intuitive desktop interface. Whether you're automating tasks, researching, writing, or just exploring ideas — Shadow Agent is there, always ready, always learning.

## 🚀 One-Click Installation

### Windows
1. Download the latest `.exe` installer from [Releases](https://github.com/DEVGD-glitch/GenericAgent_Shadow/releases)
2. Run the installer — **done!** Shadow Agent launches automatically
3. Add your API keys or use free providers (no setup required!)

### macOS / Linux
```bash
# Coming soon - App Store & Homebrew
brew install shadow-agent
```

## 🎯 Features

### 🧠 Intelligent Learning
- **Self-Evolving**: Shadow Agent learns from your preferences and work patterns
- **Multi-Model**: Switch between Claude, GPT, Gemini, and more — seamlessly
- **Memory System**: 5-layer memory architecture for persistent context

### 🎤 Voice & Vision
- **Voice Interaction**: Speak to Shadow Agent — hands-free!
- **Text-to-Speech**: Natural, expressive voice responses
- **Avatar Support**: Optional 3D avatar for a more personal experience

### 💻 Desktop Integration
- **Native Performance**: Built with Rust + Tauri for speed and reliability
- **System Tray**: Runs quietly in the background
- **Keyboard Shortcuts**: Power user commands at your fingertips

### 🔌 Extensible
- **Plugin System**: Add new skills and capabilities
- **MCP Support**: Connect to Model Context Protocol servers
- **Custom Tools**: Build your own automation workflows

## 🛠️ Quick Start

### Prerequisites
- [Node.js](https://nodejs.org/) 18+ (for development)
- [Rust](https://rustup.rs/) (for building from source)
- Python 3.10+ (for backend development)

### Download Ready-to-Run App
```
👉 https://github.com/DEVGD-glitch/GenericAgent_Shadow/releases
```

### Build from Source
```bash
# Clone the repository
git clone https://github.com/DEVGD-glitch/GenericAgent_Shadow.git
cd GenericAgent_Shadow

# Install dependencies
bun install

# Start development mode
bun run dev
```

### Run the Desktop App
```bash
# Build the complete desktop app
bun run tauri build

# The installer will be in:
# src-tauri/target/release/bundle/nsis/
```

## ⚙️ Configuration

### Option 1: Use Free Providers (Recommended for Starters)
Shadow Agent works **without API keys** using free providers:
- **Pollinations AI**: Free LLM access
- **Edge TTS**: Free voice synthesis
- **Browser STT**: Free speech recognition

### Option 2: Add Your API Keys
For enhanced capabilities, add API keys in Settings:

| Provider | What It Enables | Get Key At |
|----------|----------------|------------|
| OpenAI | GPT-4, GPT-4o | [platform.openai.com](https://platform.openai.com) |
| Anthropic | Claude 4, Sonnet | [console.anthropic.com](https://console.anthropic.com) |
| Google | Gemini 2.0 | [aistudio.google.com](https://aistudio.google.com) |
| Groq | Fast free inference | [console.groq.com](https://console.groq.com) |

## 📂 Project Structure

```
Shadow Agent/
├── src/                    # Next.js Frontend
│   ├── app/               # Pages (Chat, Settings, Dashboard)
│   ├── components/        # 60+ React components
│   │   ├── chat/          # Chat interface
│   │   ├── avatar/        # 3D avatar viewer
│   │   └── ui/            # shadcn/ui components
│   ├── stores/            # Zustand state management
│   └── lib/               # API integrations
│
├── src-tauri/             # Rust Desktop Shell
│   ├── src/main.rs        # Tauri entry point
│   ├── Cargo.toml         # Rust dependencies
│   ├── tauri.conf.json    # App configuration
│   └── binaries/          # Bundled Python backend
│
├── upload/                # Python Backend
│   ├── server.py          # FastAPI server
│   ├── agentmain/         # Agent core
│   ├── llmcore/           # LLM clients
│   ├── memory/             # 5-layer memory
│   ├── tools/              # Agent tools
│   └── voice/              # Voice pipeline
│
├── scripts/               # Build scripts
├── public/                # Static assets
└── package.json           # Node dependencies
```

## 🏗️ Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 16, React 19, Tailwind CSS | Modern web interface |
| **State** | Zustand | Lightweight state management |
| **Desktop** | Tauri 2, Rust | Native performance |
| **Backend** | Python, FastAPI | AI processing |
| **AI** | Multi-LLM (Claude, GPT, Gemini, Groq) | Intelligence |
| **Voice** | Edge TTS, Whisper, Pollinations | Voice I/O |
| **Database** | Prisma, SQLite | Data persistence |

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Fork and clone
git clone https://github.com/DEVGD-glitch/GenericAgent_Shadow.git

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and commit
git commit -m "Add amazing feature"

# Push and create PR
git push origin feature/amazing-feature
```

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## 💬 Stay Connected

- ⭐ **Star this repo** if Shadow Agent helps you!
- 🐛 **Report bugs** via GitHub Issues
- 💡 **Request features** to shape Shadow Agent's future
- 📖 **Read the docs** for advanced usage

---

*Shadow Agent — Your AI companion that never sleeps.* 🌙
