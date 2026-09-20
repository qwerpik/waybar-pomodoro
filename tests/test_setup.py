"""
Unit tests for compositor keybinding and setup generator.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from waybar_pomodoro.setup import (
    MARKER_END,
    MARKER_START,
    append_keybindings,
    get_default_config_path,
    get_idle_snippet,
    get_keybinding_snippet,
    get_waybar_module_snippet,
    run_setup,
)


class TestSetup(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_get_default_config_path(self) -> None:
        with patch("pathlib.Path.home", return_value=self.base_dir):
            self.assertEqual(
                get_default_config_path("hyprland"),
                self.base_dir / ".config" / "hypr" / "hyprland.conf",
            )
            self.assertEqual(
                get_default_config_path("sway"),
                self.base_dir / ".config" / "sway" / "config",
            )
            self.assertEqual(
                get_default_config_path("i3"),
                self.base_dir / ".config" / "i3" / "config",
            )
            self.assertIsNone(get_default_config_path("unknown"))

    def test_snippets_validity(self) -> None:
        for comp in ("mangowm", "hyprland", "sway", "i3"):
            snippet = get_keybinding_snippet(comp)
            self.assertIn(MARKER_START, snippet)
            self.assertIn(MARKER_END, snippet)
            self.assertIn("waybar-pomodoro toggle", snippet)

        module = get_waybar_module_snippet()
        self.assertIn('"custom/pomodoro"', module)
        self.assertIn('"exec": "waybar-pomodoro stream"', module)

        idle_hypr = get_idle_snippet("hyprland")
        self.assertIn("waybar-pomodoro idle-pause", idle_hypr)

    def test_append_keybindings_new_file(self) -> None:
        cfg = self.base_dir / "test_config"
        snippet = "SAMPLE_SNIPPET"
        ok, msg = append_keybindings(cfg, snippet, dry_run=False)
        self.assertTrue(ok)
        self.assertTrue(cfg.exists())
        self.assertEqual(cfg.read_text(), "SAMPLE_SNIPPET\n")

    def test_append_keybindings_existing_file_without_marker(self) -> None:
        cfg = self.base_dir / "test_config"
        cfg.write_text("# Initial config\n")
        snippet = f"{MARKER_START}\nbind=SUPER,p,spawn,waybar-pomodoro toggle\n{MARKER_END}"

        ok, msg = append_keybindings(cfg, snippet, dry_run=False)
        self.assertTrue(ok)
        content = cfg.read_text()
        self.assertIn("# Initial config", content)
        self.assertIn(MARKER_START, content)

        # Check backup created
        backups = list(self.base_dir.glob("test_config.bak.*"))
        self.assertEqual(len(backups), 1)

    def test_append_keybindings_idempotent_replace(self) -> None:
        cfg = self.base_dir / "test_config"
        cfg.write_text(f"""# Start
{MARKER_START}
old bindings
{MARKER_END}
# End
""")
        new_snippet = f"""{MARKER_START}
new bindings
{MARKER_END}"""

        ok, msg = append_keybindings(cfg, new_snippet, dry_run=False)
        self.assertTrue(ok)
        content = cfg.read_text()
        self.assertIn("new bindings", content)
        self.assertNotIn("old bindings", content)
        self.assertIn("# Start", content)
        self.assertIn("# End", content)

    def test_append_dry_run(self) -> None:
        cfg = self.base_dir / "test_config"
        cfg.write_text("existing")
        snippet = "snippet"
        ok, msg = append_keybindings(cfg, snippet, dry_run=True)
        self.assertTrue(ok)
        self.assertIn("[dry-run]", msg)
        self.assertEqual(cfg.read_text(), "existing")

    def test_append_creates_unique_backups(self) -> None:
        cfg = self.base_dir / "test_config"
        cfg.write_text("existing")
        append_keybindings(cfg, "snippet-one", dry_run=False)
        append_keybindings(cfg, "snippet-two", dry_run=False)
        backups = sorted(self.base_dir.glob("test_config.bak.*"))
        self.assertEqual(len(backups), 2)
        self.assertIn("snippet-two", cfg.read_text())

    def test_run_setup_invalid_compositor(self) -> None:
        ret = run_setup("nonexistent_wm")
        self.assertEqual(ret, 1)

    def test_run_setup_print(self) -> None:
        f = io.StringIO()
        with patch("sys.stdout", f):
            ret = run_setup("hyprland", print_only=True)
        self.assertEqual(ret, 0)
        output = f.getvalue()
        self.assertIn("Hyprland Keybindings", output)
        self.assertIn("custom/pomodoro", output)


if __name__ == "__main__":
    unittest.main()
