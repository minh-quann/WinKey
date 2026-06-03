"""
Terminal window detector for WinKey.
Monitors the focused window and auto-switches input source to English
when a terminal is detected. Restores previous input when leaving.

Detection methods (in priority order):
1. WinKey D-Bus Helper (com.github.winkey.WindowHelper) - provided by
   the WinKey GNOME Shell extension. Works on Wayland + X11.
2. xdotool fallback - X11 only.

Supports:
- Native terminal emulators (Kitty, Alacritty, Ptyxis, GNOME Terminal, etc.)
- Embedded terminals in IDEs (VS Code, JetBrains, Sublime, etc.)
"""

import subprocess
from gi.repository import Gio, GLib

from src.input_source import get_current_index, set_current_index


# Known terminal emulator WM classes (lowercase)
TERMINAL_WM_CLASSES: list[str] = [
    "gnome-terminal", "gnome-terminal-server",
    "kitty", "alacritty", "wezterm",
    "konsole", "tilix", "terminator", "xterm", "urxvt", "rxvt",
    "blackbox", "ptyxis", "guake", "yakuake", "tilda",
    "termite", "sakura", "lxterminal", "mate-terminal", "xfce4-terminal",
    "deepin-terminal", "hyper", "tabby", "cool-retro-term", "st",
    "foot", "contour", "rio", "ghostty", "wave", "warp",
]

# Apps that may contain embedded terminal panels
TERMINAL_CAPABLE_APPS: list[str] = [
    "code", "code-oss", "vscodium", "cursor",
    "antigravity-ide", "antigravity",
    "jetbrains", "idea", "pycharm", "webstorm",
    "clion", "goland", "phpstorm", "rubymine",
    "rider", "datagrip", "android-studio",
    "sublime_text", "sublime-text",
    "emacs", "gvim", "neovide",
    "zed", "lapce", "windsurf",
]

# Keywords in window title that indicate an active terminal panel
TERMINAL_TITLE_KEYWORDS: list[str] = [
    # Terminal / shell names
    "terminal", "bash", "zsh", "fish", "dash",
    "csh", "tcsh", "ksh", "mksh", "sh —", "sh -",
    # Multiplexers
    "tmux", "screen", "byobu",
    # Windows shells
    "powershell", "pwsh", "cmd.exe",
    # SSH
    "ssh ", "— ssh",
    "@localhost", "@127.0.0.1",
    # Common CLI tools that indicate a terminal is active
    "node ", "npm ", "yarn ", "pnpm ",
    "python", "python3", "pip ",
    "cargo ", "rustc", "go run", "go build",
    "docker ", "kubectl ",
    "make ", "cmake ",
    "git ",
    # VS Code terminal tab title patterns
    "task -", "tasks:",
    # Process names common in terminal titles
    "htop", "btop", "top —",
    "nvim", "vim ",
    "nano ", "micro ",
]


class TerminalDetector:
    """Detects focused terminal windows and auto-switches input to English."""

    def __init__(self, english_index: int) -> None:
        self._english_index = english_index
        self._in_terminal = False
        self._saved_source: int | None = None
        self._poll_id: int = 0
        self._helper_proxy: Gio.DBusProxy | None = None
        self._signal_sub_id: int = 0
        self._last_wm_class: str = ""
        self._last_title: str = ""
        self._use_xdotool: bool = False

    @property
    def in_terminal(self) -> bool:
        """Whether the currently focused window is a terminal."""
        return self._in_terminal

    def start(self) -> None:
        """Start monitoring the focused window."""
        if self._poll_id > 0:
            return  # Already running

        self._setup_helper_dbus()

        if self._helper_proxy:
            # Use D-Bus signal for instant detection + polling as backup
            self._subscribe_signal()
            self._poll_id = GLib.timeout_add(1000, self._poll)
            print("[WinKey] Terminal detector started (D-Bus helper)")
        elif self._xdotool_available():
            self._use_xdotool = True
            self._poll_id = GLib.timeout_add(500, self._poll)
            print("[WinKey] Terminal detector started (xdotool)")
        else:
            print("[WinKey] Terminal detector: no detection method available!")
            print("[WinKey]   - Enable the WinKey GNOME extension for Wayland")
            print("[WinKey]   - Or install xdotool for X11")

    def stop(self) -> None:
        """Stop monitoring and restore input source if in terminal mode."""
        if self._poll_id > 0:
            GLib.source_remove(self._poll_id)
            self._poll_id = 0

        self._unsubscribe_signal()

        if self._in_terminal and self._saved_source is not None:
            set_current_index(self._saved_source)
        self._in_terminal = False
        self._saved_source = None
        self._last_wm_class = ""
        self._last_title = ""
        print("[WinKey] Terminal detector stopped")

    def update_english_index(self, index: int) -> None:
        """Update the target English input source index."""
        self._english_index = index

    # ── D-Bus Helper Setup ───────────────────────────────────────────

    def _setup_helper_dbus(self) -> None:
        """Connect to the WinKey D-Bus helper (from GNOME Shell extension)."""
        try:
            self._helper_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "com.github.winkey.WindowHelper",
                "/com/github/winkey/WindowHelper",
                "com.github.winkey.WindowHelper",
                None,
            )
            # Verify it works by calling GetFocusedWindow
            result = self._helper_proxy.call_sync(
                "GetFocusedWindow", None,
                Gio.DBusCallFlags.NONE, 1000, None,
            )
            if result:
                wm_class, title = result.unpack()
                print(f"[WinKey] D-Bus helper connected (focused: {wm_class})")
            else:
                raise Exception("GetFocusedWindow returned None")
        except Exception as e:
            print(f"[WinKey] D-Bus helper not available: {e}")
            self._helper_proxy = None

    def _subscribe_signal(self) -> None:
        """Subscribe to FocusedWindowChanged D-Bus signal for instant detection."""
        if not self._helper_proxy:
            return
        try:
            self._signal_sub_id = Gio.DBusConnection.signal_subscribe(
                self._helper_proxy.get_connection(),
                "com.github.winkey.WindowHelper",
                "com.github.winkey.WindowHelper",
                "FocusedWindowChanged",
                "/com/github/winkey/WindowHelper",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_dbus_signal,
                None,
            )
        except Exception as e:
            print(f"[WinKey] Failed to subscribe to D-Bus signal: {e}")

    def _unsubscribe_signal(self) -> None:
        """Unsubscribe from D-Bus signal."""
        if self._signal_sub_id > 0 and self._helper_proxy:
            try:
                self._helper_proxy.get_connection().signal_unsubscribe(
                    self._signal_sub_id)
            except Exception:
                pass
            self._signal_sub_id = 0

    def _on_dbus_signal(self, connection: Gio.DBusConnection,
                        sender: str, path: str, interface: str,
                        signal_name: str, params: GLib.Variant,
                        user_data: object) -> None:
        """Handle FocusedWindowChanged D-Bus signal."""
        wm_class, title = params.unpack()
        wm_class = wm_class.lower()
        title = title.lower()

        if wm_class == self._last_wm_class and title == self._last_title:
            return
        self._last_wm_class = wm_class
        self._last_title = title

        is_term = self._is_terminal(wm_class, title)
        if is_term and not self._in_terminal:
            self._enter_terminal()
        elif not is_term and self._in_terminal:
            self._leave_terminal()

    # ── xdotool Fallback ─────────────────────────────────────────────

    def _xdotool_available(self) -> bool:
        """Check if xdotool is installed (for X11 fallback)."""
        try:
            result = subprocess.run(
                ["which", "xdotool"],
                capture_output=True, timeout=2,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── Window Info Retrieval ────────────────────────────────────────

    def _get_focused_window(self) -> tuple[str, str]:
        """
        Get (wm_class, title) of the currently focused window.
        Returns lowercase strings. Returns ("", "") on failure.
        """
        # Method 1: WinKey D-Bus Helper
        if self._helper_proxy:
            try:
                result = self._helper_proxy.call_sync(
                    "GetFocusedWindow", None,
                    Gio.DBusCallFlags.NONE, 1000, None,
                )
                if result:
                    wm_class, title = result.unpack()
                    return wm_class.lower(), title.lower()
            except Exception:
                pass

        # Method 2: xdotool fallback (X11 only)
        if self._use_xdotool:
            try:
                cls_result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowclassname"],
                    capture_output=True, text=True, timeout=1,
                )
                title_result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=1,
                )
                wm_class = cls_result.stdout.strip().lower() if cls_result.returncode == 0 else ""
                title = title_result.stdout.strip().lower() if title_result.returncode == 0 else ""
                return wm_class, title
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return "", ""

    # ── Terminal Detection Logic ─────────────────────────────────────

    def _is_terminal(self, wm_class: str, title: str) -> bool:
        """
        Determine if the focused window is a terminal.
        Strategy 1: Direct WM class match for native terminal apps.
        Strategy 2: Title heuristic for IDE embedded terminals.
        """
        if not wm_class:
            return False

        # Strategy 1: Native terminal emulator
        if any(t in wm_class for t in TERMINAL_WM_CLASSES):
            return True

        # Strategy 2: IDE with terminal panel active (check title)
        if any(app in wm_class for app in TERMINAL_CAPABLE_APPS):
            if title and any(kw in title for kw in TERMINAL_TITLE_KEYWORDS):
                return True

        return False

    # ── Polling Loop ─────────────────────────────────────────────────

    def _poll(self) -> bool:
        """Periodic check of the focused window."""
        wm_class, title = self._get_focused_window()

        # Skip if nothing changed
        if wm_class == self._last_wm_class and title == self._last_title:
            return True
        self._last_wm_class = wm_class
        self._last_title = title

        is_term = self._is_terminal(wm_class, title)

        if is_term and not self._in_terminal:
            self._enter_terminal()
        elif not is_term and self._in_terminal:
            self._leave_terminal()

        return True  # Keep polling

    # ── Input Source Switching ────────────────────────────────────────

    def _enter_terminal(self) -> None:
        """Focused window is a terminal → switch to English."""
        current = get_current_index()
        if current != self._english_index:
            self._saved_source = current
            set_current_index(self._english_index)
            print(f"[WinKey] Terminal detected, switched to English "
                  f"(saved source={self._saved_source})")
        else:
            self._saved_source = None
            print("[WinKey] Terminal detected, already English")
        self._in_terminal = True

    def _leave_terminal(self) -> None:
        """Left terminal window → restore previous input source."""
        self._in_terminal = False
        if self._saved_source is not None:
            set_current_index(self._saved_source)
            print(f"[WinKey] Left terminal, restored source {self._saved_source}")
            self._saved_source = None
        else:
            print("[WinKey] Left terminal, no source to restore")
