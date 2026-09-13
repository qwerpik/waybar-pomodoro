# Engineering a Zero-Dependency, Race-Free Pomodoro Module for Waybar

*A Deep Dive into Unix Process Synchronization, Advisory File Locking, Suspend Drift, and Pango Rendering in Linux Status Bars.*

---

## 1. Introduction & The Status Bar Dilemma

In the modern Wayland tiling compositor landscape—dominated by [Hyprland](https://hyprland.org), [Sway](https://swaywm.org), and [MangoWM](https://github.com/mangowm/mango)—the status bar ([Waybar](https://github.com/Alexays/Waybar)) serves as the user's primary interface for ambient system state. 

Building a timer module for Waybar looks deceivingly simple at first glance:
1. Spawn a script on interval.
2. Read a remaining duration counter.
3. Emit a JSON string like `{"text": "25:00"}` to `stdout`.

Yet, under real-world desktop conditions, naive status bar scripts suffer from severe failure modes:
* **JSON Corruption from Scroll-Wheel Bursts**: Rapidly spinning the mouse wheel over the module triggers dozens of concurrent process invocations (`waybar-pomodoro adjust +1m`). Without kernel-level synchronization, concurrent read-modify-write cycles clobber state files, causing half-written JSON files (`{"text": `) and crashing the module.
* **The 00:00 Deadlock Trap**: Clicking or pausing an expired timer before Waybar's periodic poll fires can lock the internal state machine in an invalid loop (`00:00 [paused]`), requiring manual state deletion.
* **Laptop Sleep & Suspend Drift**: When a laptop lid closes, monotonic clocks pause or wall clocks jump forward by hours. Upon waking, naive timers either fire hundreds of missed session alarms in a deafening cascade or log fictitious hours of "deep work".
* **Self-Signal Terminations**: Invoking `pkill -RTMIN+8 waybar` without scoping to the current user or ignoring incoming real-time signals can cause the invoking CLI process itself to be killed by the very signal it dispatched.

Here is how **`waybar-pomodoro`** solved these systems engineering challenges using **zero external dependencies**—relying entirely on POSIX syscalls, atomic filesystem semantics, and the pure Python 3 standard library.

---

## 2. Architecture & Concurrency: Taming the Scroll Wheel

### The Anatomy of a Race Condition
Waybar's custom module protocol allows binding user interactions directly to shell commands:

```jsonc
"custom/pomodoro": {
    "exec": "waybar-pomodoro status",
    "on-click": "waybar-pomodoro toggle",
    "on-scroll-up": "waybar-pomodoro adjust +1m",
    "on-scroll-down": "waybar-pomodoro adjust -1m",
    "interval": 1,
    "signal": 8
}
```

A smooth-scrolling mouse wheel (or a fast flick on a trackpad) dispatches up to **15 to 30 events in under 200 milliseconds**. Each event spawns an independent Python process trying to:
1. Open `~/.config/waybar-pomodoro/state.json`.
2. Parse JSON.
3. Compute `remaining += 60`.
4. Overwrite `state.json`.

```
Process A: Read [time=1500] ───────────────────────► Write [time=1560]
Process B:        Read [time=1500] ──► Write [time=1560] (Lost Update!)
Process C:             Read [TRUNCATED] ──► JSONDecodeError: Expecting value!
```

### The Solution: POSIX Advisory Locking (`fcntl.flock`)
POSIX provides kernel-enforced file locks through the `flock(2)` system call. In `waybar-pomodoro`, every state inspection or mutation is wrapped in an exclusive lock context:

```python
@contextmanager
def _transaction(self) -> Iterator[Dict[str, Any]]:
    self.state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(self.lock_file, "w") as lock_fd:
        # Acquire kernel-level advisory lock (blocks until free)
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            state = self.load_state()
            yield state
            self.save_state(state)
        finally:
            # Safely release lock
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
```

By decoupling the data file (`state.json`) from the lock target (`state.lock`), locking remains reliable even when the JSON file is being atomically renamed.

### PID-Unique Atomic Writes (`fsync` + `replace`)
Even with file locking, power loss, process interruption (`SIGKILL`), or disk caching can leave zero-byte files if written in-place. `waybar-pomodoro` enforces atomic filesystem durability:

```python
def save_state(self, state: Dict[str, Any]) -> None:
    self.state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = self.state_file.with_name(f"{self.state_file.name}.{os.getpid()}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Flush dirty kernel buffers to physical storage
        
        # Atomic rename replacing destination atomically
        tmp_path.replace(self.state_file)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
```

* **PID-Unique Names**: Multiple concurrent threads or sub-processes never collide on a shared `.tmp` path.
* **`os.fsync`**: Guarantees disk blocks are written before the directory inode points to the new file.
* **`Path.replace`**: Atomically updates the directory entry via the `rename(2)` syscall, ensuring readers only ever see a 100% valid JSON document.

---

## 3. Handling System Suspend & Time Drift

### The Monotonic vs. Wall Clock Problem
Timers often rely on `time.monotonic()` because it is immune to NTP adjustments. However, on Linux systems, `CLOCK_MONOTONIC` pauses during system suspend (`S3` / deep sleep), whereas `CLOCK_BOOTTIME` or `time.time()` continues running.

If a user starts a 25-minute Pomodoro, works for 5 minutes, and closes their laptop lid for a 2-hour lunch:
* When the laptop reopens, the wall clock is `T + 120min`.
* A naive timer sees that `end_time < now` and assumes 25 minutes of work took place.
* It logs a session to stats, plays an alarm chime into the user's headphones in a quiet meeting, and transitions to break.

### Drift Detection Algorithm
`waybar-pomodoro` tracks the absolute completion timestamp (`end_time = now + remaining`). When checking timer status:

```python
now = time.time()
overdue = now - state["end_time"]

if overdue > 0:
    # If the timer expired more than 30 minutes ago, the laptop was suspended
    if overdue > 1800:
        was_suspended = True
        state["state"] = "idle"
        # Advance phase cleanly WITHOUT logging phantom stats or triggering audio alarms
```

If the system was suspended:
1. **Phantom stats are rejected**: The user didn't actually focus during a 2-hour suspend.
2. **Audio chimes are suppressed**: No shocking noise upon waking your laptop in a library or coffee shop.
3. **Timer cleanly advances**: Moves to the next natural phase in `idle` mode, ready for the user's next explicit action.

---

## 4. Waybar Protocol & Rich Pango Tooltips

Waybar expects continuous JSON output adhering to its custom module specification:

```json
{
  "text": "25:00",
  "alt": "work",
  "tooltip": "<b>🍅 Focus Session</b>...",
  "class": "work running",
  "percentage": 50
}
```

### 12-Segment Monospace Character Progress Bar
A graphical progress bar embedded in a text dymek (tooltip) must align perfectly regardless of GUI font kerning. `waybar-pomodoro` achieves this using a monospace block `<tt>` and UTF-8 glyphs:

* Filled: `▰` (`U+25B0`)
* Empty: `▱` (`U+25B1`)

```python
def render_progress_bar(percentage: int, accent_color: str, length: int = 12) -> str:
    clamped_pct = max(0, min(100, percentage))
    filled_count = int(round((clamped_pct / 100.0) * length))
    filled = "▰" * filled_count
    empty = "▱" * (length - filled_count)

    if filled_count == 0:
        return f"<span alpha='30%'>{empty}</span>"
    if empty:
        return f"<span foreground='{accent_color}'>{filled}</span><span alpha='30%'>{empty}</span>"
    return f"<span foreground='{accent_color}'>{filled}</span>"
```

### Dynamic Pango Palette & Alpha Channels
Rather than static colors, the tooltip dynamically adapts to the timer's phase:
* **Focus Session**: Coral Red (`#f38ba8`)
* **Short / Long Break**: Spring Green (`#a6e3a1`)
* **Paused**: Warm Gold (`#f9e2af`)
* **Idle**: Muted Sky (`#89b4fa`)

By leveraging Pango's `alpha='30%'` and `alpha='60%'` attributes, secondary labels, empty progress segments, and separator rules recede into the background, providing visual hierarchy without hardcoding opaque contrast values that break between dark and light themes.

```text
🍅 Focus Session [2/4]               Running
▰▰▰▰▰▰▱▱▱▱▱▱  12:30 (50%)
─────────────────────────────
• Left-click:   Toggle / Pause
• Right-click:  Reset Session
• Middle-click: Skip Phase
• Scroll:       ±1 min
─────────────────────────────
Today:  3 session(s) • 90m focus
Streak: 5 day(s) 🔥
```

---

## 5. Realtime Signal Traps: Safe Inter-Process Signaling

To achieve instantaneous feedback when a user clicks or scrolls, waiting for Waybar's 1-second interval is unacceptable. Waybar allows realtime signal triggering via `SIGRTMIN+N`:

```jsonc
"custom/pomodoro": {
    "signal": 8
}
```

Upon mutating the timer, `waybar-pomodoro` notifies Waybar:
```bash
pkill -RTMIN+8 waybar
```

### The Pitfalls of Naive `pkill`
1. **Multi-User Collision**: On multi-seat or shared Linux systems, a global `pkill -RTMIN+8 waybar` sends signals to other users' desktop sessions.
2. **Self-Termination**: If `waybar-pomodoro` is spawned from inside a script or child process of Waybar, the process group might receive the signal. If an unhandled real-time signal arrives at a Python interpreter, Python's default behavior is to terminate the process immediately.

### The Defensive Signaling Implementation
```python
def signal_waybar(self) -> None:
    if not self.config.waybar_signal:
        return
    sig_num = 34 + self.config.waybar_signal  # SIGRTMIN (34) + 8 = 42
    
    # 1. Mask the signal in the Python process to prevent self-termination
    try:
        signal.signal(sig_num, signal.SIG_IGN)
    except (ValueError, OSError):
        pass

    # 2. Scope the kill strictly to the active user ID and exact process name
    cmd = ["pkill", f"-RTMIN+{self.config.waybar_signal}", "-x", "-u", str(os.getuid()), "waybar"]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except FileNotFoundError:
        pass
```

* `-u $(id -u)` guarantees cross-user isolation.
* `-x` guarantees substring processes (like `waybar-custom-script`) are not accidentally signaled.
* `signal.SIG_IGN` guarantees that even if the signal bounces back to the caller, execution finishes cleanly.

---

## 6. Conclusion & Takeaways

Building desktop utilities that "just work" in Linux Wayland environments requires treating local files and inter-process communication with the same rigor as distributed systems:
1. **Never trust single-process assumptions**: Status bars are inherently multi-process, asynchronous environments.
2. **Lock explicitly**: Use kernel advisory locks (`fcntl.flock`) for file-backed state.
3. **Write durably**: Atomic `replace` with `fsync` prevents corruption from power cuts or crashes.
4. **Plan for physical hardware reality**: Sleep, suspend, and clock leaps will happen—detect them mathematically.
5. **Embrace standard protocols**: Waybar's `{alt}`, `{percentage}`, and Pango markup allow rich interfaces without requiring bulky GUI frameworks.

`waybar-pomodoro` is free, open-source software maintained under the [MangoWM](https://github.com/mangowm) organization:
🔗 **GitHub Repository**: [https://github.com/mangowm/waybar-pomodoro](https://github.com/mangowm/waybar-pomodoro)
