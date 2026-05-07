#!/usr/bin/env python3
"""
System tray icon for WinKey.
Runs as a separate process since AppIndicator3 requires Gtk3,
which conflicts with the main app's Gtk4/Adw.

Communicates with the main app via a simple unix socket.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import Gtk, AyatanaAppIndicator3, GLib
from pathlib import Path
import socket
import os
import sys
import threading

# Socket path for IPC with the main app
SOCKET_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "winkey-tray.sock"
ICON_PATH = str(Path(__file__).parent.parent / "data" / "icons" / "winkey.svg")


class WinKeyTray:
    """System tray icon for WinKey."""

    def __init__(self) -> None:
        self._running = True
        self._status = "running"

        # Setup indicator
        self._indicator = AyatanaAppIndicator3.Indicator.new(
            "winkey-indicator",
            ICON_PATH,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_title("WinKey")

        # Build menu
        self._build_menu()

        # Start IPC listener
        self._start_ipc()

    def _build_menu(self) -> None:
        """Build the tray context menu."""
        menu = Gtk.Menu()

        # Status label
        self._status_item = Gtk.MenuItem(label="⌨ WinKey — Đang chạy")
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Open settings
        open_item = Gtk.MenuItem(label="⚙ Mở cài đặt")
        open_item.connect("activate", self._on_open)
        menu.append(open_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="✕ Thoát WinKey")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        self._indicator.set_menu(menu)

    def _start_ipc(self) -> None:
        """Start a unix socket to receive commands from main app."""
        # Clean up old socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._sock.bind(str(SOCKET_PATH))
        self._sock.settimeout(1.0)

        thread = threading.Thread(target=self._ipc_loop, daemon=True)
        thread.start()

    def _ipc_loop(self) -> None:
        """Listen for IPC messages."""
        while self._running:
            try:
                data = self._sock.recv(1024)
                msg = data.decode("utf-8").strip()
                GLib.idle_add(self._handle_message, msg)
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break

    def _handle_message(self, msg: str) -> bool:
        """Handle an IPC message on the main thread."""
        if msg == "status:running":
            self._status_item.set_label("⌨ WinKey — Đang chạy")
        elif msg == "status:stopped":
            self._status_item.set_label("⌨ WinKey — Đã dừng")
        elif msg == "quit":
            self._cleanup()
            Gtk.main_quit()
        return False

    def _on_open(self, _item: Gtk.MenuItem) -> None:
        """Open the main WinKey settings window."""
        import subprocess
        app_path = str(Path(__file__).parent.parent / "winkey.py")
        subprocess.Popen(
            ["python3", app_path],
            start_new_session=True,
        )

    def _on_quit(self, _item: Gtk.MenuItem) -> None:
        """Quit the tray and signal the main app to quit."""
        # Signal main app to quit
        self._send_to_app("quit")
        self._cleanup()
        Gtk.main_quit()

    def _send_to_app(self, msg: str) -> None:
        """Send a message to the main app via its socket."""
        app_sock_path = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "winkey-app.sock"
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.sendto(msg.encode("utf-8"), str(app_sock_path))
            sock.close()
        except Exception:
            pass

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

    def run(self) -> None:
        """Run the tray icon main loop."""
        Gtk.main()


def main() -> None:
    tray = WinKeyTray()
    tray.run()


if __name__ == "__main__":
    main()
