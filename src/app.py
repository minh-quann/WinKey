"""
WinKey GTK Application with background daemon support.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib
from pathlib import Path
import subprocess
import os
import socket
import threading

# Icon directory
ICON_DIR = Path(__file__).parent.parent / "data" / "icons"

# Socket paths for IPC
_RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
APP_SOCKET_PATH = _RUNTIME_DIR / "winkey-app.sock"
TRAY_SOCKET_PATH = _RUNTIME_DIR / "winkey-tray.sock"


class WinKeyApp(Adw.Application):
    """Main GTK Application for WinKey."""

    def __init__(self) -> None:
        super().__init__(
            application_id="com.github.winkey",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None  # WinKeyWindow | None
        self._background_mode = False
        self._bg_daemon = None  # KeyDaemon | None
        self._bg_callbacks = None
        self._ipc_sock: socket.socket | None = None
        self._ipc_running = False

        # Register --background command line option
        self.add_main_option(
            "background", ord("b"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Start in background mode (no window)", None,
        )

    def do_startup(self) -> None:
        """Application startup - load CSS, icons, tray and IPC."""
        Adw.Application.do_startup(self)
        self._load_css()
        self._register_icons()
        
        from src.settings import load_config
        config = load_config()
        if config.get("show_tray_icon", True):
            self._spawn_tray()
            
        self._start_ipc()

        # Keep app alive even without windows
        self.hold()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        """Handle command line arguments."""
        options = command_line.get_options_dict()

        if options.contains("background"):
            self._background_mode = True

        self.activate()
        return 0

    def do_activate(self) -> None:
        """Application activation - show window or start background daemon."""
        if self._background_mode and self.window is None:
            # Background mode: start daemon without window
            self._start_background_daemon()
            self._background_mode = False
            return

        # Normal mode: show window
        if not self.window:
            from src.ui.window import WinKeyWindow
            self.window = WinKeyWindow(self)

            # If background daemon was running, transfer to window
            if self._bg_daemon and self._bg_daemon.is_running:
                self._bg_daemon.stop()
                self._bg_daemon = None
                self._bg_callbacks = None
            # Stop background terminal detector (window has its own)
            if hasattr(self, '_bg_terminal_detector') and self._bg_terminal_detector:
                self._bg_terminal_detector.stop()
                self._bg_terminal_detector = None

        self.window.present()

    def _start_background_daemon(self) -> None:
        """Start the daemon in background without creating a window."""
        from src.settings import load_config
        from src.daemon import KeyDaemon
        from src.input_source import get_current_index, set_current_index
        from src.terminal_detector import TerminalDetector

        config = load_config()
        if not config["enabled"]:
            return

        # Start terminal detector if enabled
        if config.get("auto_switch_terminal", True):
            self._bg_terminal_detector = TerminalDetector(config["english_index"])
            self._bg_terminal_detector.start()
        else:
            self._bg_terminal_detector = None

        class BackgroundCallbacks:
            """Daemon callbacks for background mode."""
            def __init__(self, app: 'WinKeyApp', cfg: dict,
                         detector: TerminalDetector | None) -> None:
                self.app = app
                self.config = cfg
                self._saved_source: int | None = None
                self._detector = detector

            def on_super_pressed(self) -> None:
                GLib.idle_add(self._handle_pressed)

            def on_super_released(self) -> None:
                GLib.idle_add(self._handle_released)

            def on_status_changed(self, running: bool) -> None:
                GLib.idle_add(self.app._notify_tray_status, running)

            def on_error(self, message: str) -> None:
                pass

            def _handle_pressed(self) -> None:
                # Skip if terminal detector already switched to English
                if self._detector and self._detector.in_terminal:
                    return

                current = get_current_index()
                target = self.config["english_index"]
                if current != target:
                    self._saved_source = current
                    set_current_index(target)
                else:
                    self._saved_source = None

            def _handle_released(self) -> None:
                # Skip if terminal detector is managing the input source
                if self._detector and self._detector.in_terminal:
                    return

                if self._saved_source is not None:
                    set_current_index(self._saved_source)
                    self._saved_source = None

        self._bg_callbacks = BackgroundCallbacks(
            self, config, self._bg_terminal_detector)
        self._bg_daemon = KeyDaemon(self._bg_callbacks)
        self._bg_daemon.start()


    # ── Tray Icon Management ─────────────────────────────────────────

    def _spawn_tray(self) -> None:
        """Spawn the tray icon as a separate Gtk3 process."""
        tray_script = Path(__file__).parent / "tray.py"
        try:
            self._tray_proc = subprocess.Popen(
                ["python3", str(tray_script)],
                start_new_session=True,
            )
        except Exception as e:
            print(f"Warning: Could not start tray icon: {e}")

    def _toggle_tray(self, show: bool) -> None:
        """Toggle the tray icon process on or off."""
        if show:
            if not hasattr(self, '_tray_proc') or self._tray_proc is None or self._tray_proc.poll() is not None:
                self._spawn_tray()
                
                # Resync status if running
                is_running = False
                if self._bg_daemon and self._bg_daemon.is_running:
                    is_running = True
                elif self.window and hasattr(self.window, 'daemon') and self.window.daemon.is_running:
                    is_running = True
                    
                if is_running:
                    from gi.repository import GLib
                    GLib.timeout_add(500, self._notify_tray_status, True)
        else:
            self._send_to_tray("quit")
            if hasattr(self, '_tray_proc'):
                self._tray_proc = None

    def _notify_tray_status(self, running: bool) -> None:
        """Send status update to tray icon via socket."""
        status = "running" if running else "stopped"
        self._send_to_tray(f"status:{status}")

    def _send_to_tray(self, msg: str) -> None:
        """Send a message to the tray process."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.sendto(msg.encode("utf-8"), str(TRAY_SOCKET_PATH))
            sock.close()
        except Exception:
            pass

    # ── IPC Listener ─────────────────────────────────────────────────

    def _start_ipc(self) -> None:
        """Start unix socket to receive commands from tray."""
        if APP_SOCKET_PATH.exists():
            APP_SOCKET_PATH.unlink()

        self._ipc_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._ipc_sock.bind(str(APP_SOCKET_PATH))
        self._ipc_sock.settimeout(1.0)
        self._ipc_running = True

        thread = threading.Thread(target=self._ipc_loop, daemon=True)
        thread.start()

    def _ipc_loop(self) -> None:
        """Listen for IPC messages from tray."""
        while self._ipc_running:
            try:
                data = self._ipc_sock.recv(1024)
                msg = data.decode("utf-8").strip()
                GLib.idle_add(self._handle_ipc, msg)
            except socket.timeout:
                continue
            except Exception:
                if self._ipc_running:
                    continue
                break

    def _handle_ipc(self, msg: str) -> bool:
        """Handle IPC message on main thread."""
        if msg == "quit":
            self._do_full_quit()
        return False

    def _do_full_quit(self) -> None:
        """Fully quit the application and tray."""
        # Stop background terminal detector
        if hasattr(self, '_bg_terminal_detector') and self._bg_terminal_detector:
            self._bg_terminal_detector.stop()
            self._bg_terminal_detector = None

        # Stop background daemon
        if self._bg_daemon:
            self._bg_daemon.stop()

        # Stop window daemon and its terminal detector
        if self.window:
            from src.input_source import set_current_index
            if hasattr(self.window, 'terminal_detector'):
                self.window.terminal_detector.stop()
            if hasattr(self.window, '_saved_source') and self.window._saved_source is not None:
                set_current_index(self.window._saved_source)
            self.window.daemon.stop()

        # Clean up IPC
        self._ipc_running = False
        if self._ipc_sock:
            try:
                self._ipc_sock.close()
            except Exception:
                pass
        if APP_SOCKET_PATH.exists():
            APP_SOCKET_PATH.unlink()

        # Kill tray
        self._send_to_tray("quit")

        # Release hold and quit
        self.release()
        self.quit()

    # ── CSS and Icons ────────────────────────────────────────────────

    def _load_css(self) -> None:
        """Load custom CSS stylesheet."""
        from gi.repository import Gtk, Gdk
        provider = Gtk.CssProvider()
        css = """
        .success {
            color: #2ec27e;
        }
        .error {
            color: #e01b24;
        }
        .caption {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
            background: alpha(@accent_color, 0.15);
            color: @accent_color;
        }
        """
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _register_icons(self) -> None:
        """Register custom icons with the icon theme."""
        from gi.repository import Gtk
        icon_theme = Gtk.IconTheme.get_for_display(
            self.get_active_window().get_display() if self.get_active_window()
            else __import__("gi").repository.Gdk.Display.get_default()
        )
        icon_theme.add_search_path(str(ICON_DIR))
