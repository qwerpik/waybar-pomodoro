# Contributing to waybar-pomodoro

Thank you for your interest in improving `waybar-pomodoro`! Contributions of all kinds—bug reports, fixes, documentation improvements, and desktop themes—are welcome.

## Quick Contribution Workflow (3 Steps)

1. **Fork and Branch**
   - Fork the repository on GitHub.
   - Create a feature branch: `git checkout -b feature/my-enhancement`.

2. **Develop and Test**
   - Make your changes.
   - Run the full test and lint suite locally before committing:
     ```bash
     make check
     ```
   - All tests, `ruff` checks, and `mypy` strict typing must pass.

3. **Open a Pull Request**
   - Push your branch to your fork: `git push origin feature/my-enhancement`.
   - Submit a Pull Request against `main` with a clear description of what changed and why.

## Guidelines

- **Zero Runtime Dependencies**: `waybar-pomodoro` relies strictly on Python standard library modules for execution. Do not introduce mandatory third-party pip dependencies.
- **Atomic & Concurrency-Safe**: Any state persistence must maintain POSIX advisory file locks (`fcntl.flock`) and atomic file replacement (`fsync` + replace).
- **Keep Documentation Synchronized**: If adding flags or configuration options, update the corresponding documentation files in `docs/`.
