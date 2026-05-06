# Contributing to GenericAgent

Thank you for your interest in contributing to GenericAgent! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Reporting Issues](#reporting-issues)

## 📜 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/GenericAgent.git
   cd GenericAgent
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/GenericAgent/GenericAgent.git
   ```

## 🛠 Development Setup

### Prerequisites

- Node.js 20+ with Bun or npm
- Rust 1.70+
- Python 3.10+

### Quick Setup

```bash
# Install frontend dependencies
bun install  # or npm install

# Set up Python backend
cd upload/GenericAgent-v1.0.0
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running Development Mode

```bash
# Start frontend (in project root)
bun run dev

# Start backend (in separate terminal)
cd upload/GenericAgent-v1.0.0
python server.py
```

## 🔧 Making Changes

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following the coding standards below

3. **Test your changes**:
   - Test Python backend: `cd upload/GenericAgent-v1.0.0 && python -c "import agentmain; print('OK')"`
   - Test frontend: `bun run lint`

4. **Commit your changes** with clear messages:
   ```bash
   git add .
   git commit -m "Add feature: short description"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

## 📤 Pull Request Process

1. **Update documentation** if your changes affect user-facing features
2. **Ensure tests pass** if applicable
3. **Update CHANGELOG.md** with your changes (if it exists)
4. **Create a Pull Request** on GitHub with:
   - Clear title describing the change
   - Detailed description of what was changed
   - Reference any related issues (e.g., "Closes #123")

## 📏 Coding Standards

### Python

- Use type hints for function signatures
- Follow PEP 8 style guidelines
- Add docstrings to all public functions and classes
- Maximum line length: 120 characters

### TypeScript/JavaScript

- Use TypeScript for new components
- Follow the existing code style in the project
- Use meaningful variable names
- Maximum line length: 100 characters

### Rust

- Follow Rust idioms and best practices
- Use meaningful variable and function names
- Add documentation comments for public APIs

## 🐛 Reporting Issues

When reporting issues, please include:

- **Clear title** describing the problem
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Environment details** (OS, Python version, Node version, etc.)
- **Error messages** or logs if applicable

## 📝 License

By contributing to GenericAgent, you agree that your contributions will be licensed under the MIT License.

---

Thank you for making GenericAgent better! 🙏
