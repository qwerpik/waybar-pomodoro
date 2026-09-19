# Project: waybar-pomodoro v2.0

## Architecture
`waybar-pomodoro` v2.0 transforms the application from a polling CLI script into a high-performance, battery-efficient Linux productivity daemon and universal bar integration with 0% CPU streaming, compositors integrations (MangoWM, Hyprland, Sway, i3), screen lock auto-pause, Focus DND, and lifecycle event hooks.

Zero third-party runtime dependencies are added (`dependencies = []`). The architecture consists of:
- `timer.py`: Core state machine, transactional state mutation with `fcntl.flock`, sleep/suspend drift resilience using `CLOCK_BOOTTIME` vs `CLOCK_MONOTONIC`, lifecycle event dispatch.
- `watcher.py`: Event-driven inotify monitoring of the state file's parent directory via `ctypes` libc, providing sub-millisecond reaction times with zero polling.
- `streaming.py`: Persistent streaming daemon for Waybar (`waybar-pomodoro stream`), outputting newline-delimited JSON flushed immediately to stdout, integer second boundary alignment, 0.00% CPU when idle/paused via kernel `epoll_wait` indefinite blocking.
- `idle.py`: Screen lock and inactivity detection (`idle-pause` and `idle-resume`, alias `lock-hook`), `paused_by_idle` state tracking to prevent resuming manually paused sessions, desktop notifications with action buttons.
- `dnd.py`: Automatic Focus Do Not Disturb control for `swaync`, `dunst`, and `mako` notification daemons, asynchronous execution, `dnd_active` state tracking.
- `hooks.py`: Visual and lifecycle event hooks in `~/.config/waybar-pomodoro/hooks/` and `config.json` callback commands, asynchronous detached execution, comprehensive `POMODORO_*` environment variables.
- `setup.py`: Compositor configuration generator for Hyprland, MangoWM, Sway, and i3 with idempotent marker-bounded keybinding insertion, timestamped backup creation, and drop-in Waybar module JSON generation.
- `cli.py`: Unified CLI parser and dispatcher for all v1 and v2 commands (`status`, `stream`, `setup`, `idle-pause`, `idle-resume`, `lock-hook`, etc.).
- `config.py`: Expanded `PomodoroConfig` schema supporting `auto_dnd`, `dnd_provider`, `hooks`, `hooks_dir`, `idle_resume_mode`, etc.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Continuous Streaming Engine (`stream`) | Single persistent process emitting newline-delimited JSON flushed immediately to stdout | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Integer Second Alignment | Wake up precisely at integer second boundaries ($\lfloor t \rfloor + 1.005$) with $< 10\,\mu\text{s}$ jitter | M1 | ORIGINAL_REQUEST §R1 |
| 3 | 0.00% CPU Overhead | Indefinite kernel blocking via `epoll_wait(timeout=None)` when idle or paused | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Event-Driven State Reaction | Sub-millisecond instant display refresh via parent-directory inotify watch on state file modifications | M1 | ORIGINAL_REQUEST §R1 |
| 5 | POSIX Signal Handling | Instant wakeup on `SIGUSR1` / `SIGRTMIN+8` and clean shutdown on `SIGTERM` / `SIGINT` | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Backward Compatibility | 100% backward compatibility with on-demand `waybar-pomodoro status`, `toggle`, `adjust`, `reset`, `skip`, `menu` | M1 | ORIGINAL_REQUEST §R1 |
| 7 | Sleep / Wake Drift Resilience | Microsecond-accurate suspend detection via `CLOCK_BOOTTIME` vs `CLOCK_MONOTONIC`, eliminating phantom completions and false alarms | M1 | ORIGINAL_REQUEST §R6 |
| 8 | Monotonic Time Tracking & Boot ID | Record `start_monotonic`, `start_boottime`, and kernel `boot_id` in state to protect stats across suspend and reboots | M1 | ORIGINAL_REQUEST §R6 |
| 9 | Strict Mypy Compliance | Fix unused `type: ignore` comments in `menu.py` ensuring `mypy --strict src` passes with 0 errors | M1 | Survey 1 Finding |
| 10 | Screen Lock & Idle Pause (`idle-pause`) | Auto-pause timer when screen locks or inactivity occurs, marking `paused_by_idle: true` | M2 | ORIGINAL_REQUEST §R3 |
| 11 | Screen Lock & Idle Resume (`idle-resume`) | Resume or prompt user on unlock, preserving manual pauses, with CLI alias `lock-hook` | M2 | ORIGINAL_REQUEST §R3 |
| 12 | Idle Daemon Turnkey Configs | Turnkey configuration snippets and documentation for `hypridle.conf` and `swayidle` | M2 | ORIGINAL_REQUEST §R3 |
| 13 | Interactive Resume Notification | Desktop notification with action buttons on session unlock asking whether to resume | M2 | ORIGINAL_REQUEST §R3 |
| 14 | Automatic Focus DND (`auto_dnd`) | Auto-enable DND during work phases and restore normal notification mode during breaks or reset | M2 | ORIGINAL_REQUEST §R4 |
| 15 | Notification Daemon Integrations | Native non-blocking CLI controls for `swaync`, `dunst`, and `mako` with auto-detection | M2 | ORIGINAL_REQUEST §R4 |
| 16 | DND State Tracking | Track `dnd_active` in state to prevent un-muting users who had DND active prior to work session | M2 | ORIGINAL_REQUEST §R4 |
| 17 | Compositor Setup Generator (`setup`) | CLI generator `waybar-pomodoro setup [hyprland|mangowm|sway|i3|all]` | M3 | ORIGINAL_REQUEST §R2 |
| 18 | Compositor Keybinding Generation | Generate idiomatic keybindings for Hyprland, MangoWM, Sway, and i3 | M3 | ORIGINAL_REQUEST §R2 |
| 19 | Safe Idempotent File Appending | Safe `--append` with marker bounds (`# >>> waybar-pomodoro ...`) and timestamped `.bak` backups | M3 | ORIGINAL_REQUEST §R2 |
| 20 | Drop-in Waybar JSON Generation | Emit drop-in Waybar module JSON definitions configured for target compositor | M3 | ORIGINAL_REQUEST §R2 |
| 21 | Executable Hooks Directory | Support executable scripts in `~/.config/waybar-pomodoro/hooks/` (`on_work_start.sh`, `on_break_start.sh`, etc.) | M3 | ORIGINAL_REQUEST §R5 |
| 22 | Config Callback Hooks | Support callback commands configured in `config.json` | M3 | ORIGINAL_REQUEST §R5 |
| 23 | Non-blocking Hook Execution | Asynchronous detached execution (`start_new_session=True`) without delaying ticks or freezing UI | M3 | ORIGINAL_REQUEST §R5 |
| 24 | Hook Environment Variables | Export rich `POMODORO_*` environment variables to hook subprocesses | M3 | ORIGINAL_REQUEST §R5 |
| 25 | Package Version Bump to 2.0.0 | Update version to 2.0.0 in `pyproject.toml`, `__init__.py`, `PKGBUILD`, `default.nix` | M4 | ORIGINAL_REQUEST §R7 |
| 26 | Integrations Guide Documentation | Author `docs/INTEGRATIONS.md` covering compositors, idle daemons, DND daemons, and hooks | M4 | ORIGINAL_REQUEST §R7 |
| 27 | Documentation Updates | Update `README.md`, `docs/CLI.md`, and `docs/CONFIGURATION.md` with all v2.0 features | M4 | ORIGINAL_REQUEST §R7 |
| 28 | Comprehensive E2E Test Suite | Deliver >= 65 tests passing across Tiers 1-4 via E2E Testing Track | M5 | ORIGINAL_REQUEST §R7 |
| 29 | Adversarial Coverage Hardening | White-box adversarial testing (Tier 5) closing coverage gaps and stress-testing edge cases | M5 | Project Pattern §Phase 2 |
| 30 | Quality Gate Verification | Ensure `make check` (`ruff lint`, `ruff format check`, `mypy --strict`, `pytest`) passes with 0 errors | M5 | ORIGINAL_REQUEST §R7 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Timing Engine, Drift Resilience & Streaming Daemon | Features 1–9: `watcher.py`, `streaming.py`, `timer.py` drift resilience & monotonic tracking, `cli.py` (`stream`), `menu.py` mypy cleanup | none | COMPLETED |
| M2 | Screen Lock, Idle Detection & Focus DND | Features 10–16: `idle.py`, `dnd.py`, `config.py` updates, `timer.py` idle/DND state integration, `cli.py` (`idle-pause`, `idle-resume`, `lock-hook`) | M1 | COMPLETED |
| M3 | Compositor Visual / Lifecycle Event Hooks & Setup Generator | Features 17–24: `hooks.py`, `setup.py`, `timer.py` hook triggers, `cli.py` (`setup`) | M1 | COMPLETED |
| M4 | Packaging, Version Bump & Documentation | Features 25–27: `pyproject.toml`, `__init__.py`, `PKGBUILD`, `default.nix`, `docs/INTEGRATIONS.md`, `docs/CLI.md`, `docs/CONFIGURATION.md`, `README.md` | M2, M3 | COMPLETED |
| M5 | Final Milestone: E2E Test Pass & Adversarial Hardening | Features 28–30: Pass 100% of E2E tests (Tiers 1-4) published in `TEST_READY.md`, followed by Phase 2 adversarial coverage hardening (Tier 5) | M4, E2E Track | COMPLETED |

## Interface Contracts

### `watcher.py` ↔ `streaming.py`
- `InotifyWatcher(target_path: Path)`:
  - `start() -> None`: Initializes inotify descriptor watching target parent directory for `IN_MOVED_TO | IN_CLOSE_WRITE | IN_CREATE`.
  - `fileno() -> int`: Returns file descriptor for multiplexing in `selectors.DefaultSelector`.
  - `consume_events() -> bool`: Reads events from inotify fd, returns `True` if target file was modified.
  - `close() -> None`: Closes inotify file descriptor.

### `timer.py` ↔ `streaming.py`
- `PomodoroTimer.get_status_payload() -> dict[str, Any]`:
  - Returns Waybar JSON payload dict (`text`, `alt`, `tooltip`, `class`, `percentage`).
  - Does NOT trigger disk write unless state actually changes.
- `PomodoroTimer.check_completion(state: dict[str, Any]) -> bool`:
  - Uses `CLOCK_BOOTTIME` vs `CLOCK_MONOTONIC` to detect sleep/suspend.
  - If suspended without active execution, resets or adjusts end time without phantom stat recording or alarm ringing.
- `PomodoroTimer.state_file: Path`:
  - Absolute path to `state.json`.

### `idle.py` ↔ `timer.py` & `cli.py`
- `handle_idle_pause(timer: PomodoroTimer, config: PomodoroConfig) -> int`:
  - If timer is running, pauses it, marks `paused_by_idle = True` in state, dispatches notifications/Waybar signal, returns 0.
  - If timer is idle/paused, returns 0 without corrupting state.
- `handle_idle_resume(timer: PomodoroTimer, config: PomodoroConfig, interactive: bool = True) -> int`:
  - If `paused_by_idle` is True:
    - If interactive and `notify-send` available: prompts user with action buttons (`Resume`, `Reset`, `Keep Paused`).
    - If auto or approved: resumes timer, clears `paused_by_idle`, returns 0.
  - If `paused_by_idle` is False: leaves timer in manual pause, returns 0.

### `dnd.py` ↔ `timer.py`
- `DndManager(config: PomodoroConfig)`:
  - `set_dnd(enabled: bool) -> None`: Asynchronously enables or disables DND via detected daemon (`swaync`, `dunst`, `mako`).
  - `detect_provider() -> Optional[str]`: Probes active notification daemon via `pgrep` or client query.

### `hooks.py` ↔ `timer.py`
- `HookDispatcher(config: PomodoroConfig)`:
  - `trigger_event(event_name: str, state: dict[str, Any], config: PomodoroConfig) -> None`:
    - Dispatches to executable script `~/.config/waybar-pomodoro/hooks/on_<event>.sh` and configured command in `config.json`.
    - Runs asynchronously with `subprocess.Popen(..., start_new_session=True)`.
    - Populates `POMODORO_EVENT`, `POMODORO_PHASE`, `POMODORO_TIME_REMAINING`, `POMODORO_CYCLE`, `POMODORO_STATE`.

### `setup.py` ↔ `cli.py`
- `run_setup(compositor: str, dry_run: bool, print_only: bool, append: bool) -> int`:
  - Supported compositors: `hyprland`, `mangowm`, `sway`, `i3`, `all`.
  - Generates keybindings and Waybar JSON module definitions.
  - Safely modifies config files with marker headers and backup files.

## Code Layout
Existing files modified:
- `src/waybar_pomodoro/timer.py`: Drift resilience, state fields (`paused_by_idle`, `dnd_active`, `start_monotonic`, `start_boottime`, `boot_id`), DND and hook dispatch hooks.
- `src/waybar_pomodoro/config.py`: New settings for DND, idle pause/resume, and hooks.
- `src/waybar_pomodoro/cli.py`: New subcommands (`stream`, `setup`, `idle-pause`, `idle-resume`, `lock-hook`).
- `src/waybar_pomodoro/menu.py`: Cleanup unused `# type: ignore` for `mypy --strict`.
- `pyproject.toml`, `src/waybar_pomodoro/__init__.py`, `packaging/PKGBUILD`, `default.nix`: Version 2.0.0.
- `README.md`, `docs/CLI.md`, `docs/CONFIGURATION.md`: Documentation updates.

New files created:
- `src/waybar_pomodoro/watcher.py`: Inotify event monitoring via `ctypes`.
- `src/waybar_pomodoro/streaming.py`: Waybar continuous streaming daemon.
- `src/waybar_pomodoro/idle.py`: Screen lock and idle pause/resume handler.
- `src/waybar_pomodoro/dnd.py`: Focus Do Not Disturb manager.
- `src/waybar_pomodoro/hooks.py`: Visual and lifecycle event hook dispatcher.
- `src/waybar_pomodoro/setup.py`: Compositor setup generator.
- `docs/INTEGRATIONS.md`: Comprehensive guide for compositors, lock/idle daemons, DND daemons, and hooks.
- `tests/test_streaming.py`, `tests/test_idle.py`, `tests/test_dnd.py`, `tests/test_hooks.py`, `tests/test_setup.py`: Comprehensive test suites.
