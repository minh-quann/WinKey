"""
Keyboard monitoring daemon for WinKey.
Reads raw /dev/input events to detect Super key press/release.
Runs in a background thread.
"""

import struct
import os
import select
import threading
from typing import Callable, Protocol

# struct input_event format (64-bit Linux)
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

# Event types
EV_KEY = 0x01

# Super/Meta key codes
KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126

# Key states
KEY_RELEASE = 0
KEY_PRESS = 1


class DaemonCallbacks(Protocol):
    """Protocol for daemon event callbacks."""
    def on_super_pressed(self) -> None: ...
    def on_super_released(self) -> None: ...
    def on_status_changed(self, running: bool) -> None: ...
    def on_error(self, message: str) -> None: ...


def find_keyboard_devices() -> list[str]:
    """Find all keyboard event devices from /proc/bus/input/devices."""
    devices: list[str] = []
    try:
        with open("/proc/bus/input/devices", "r") as f:
            content = f.read()

        blocks = content.split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            handlers = ""
            has_key_capability = False

            for line in lines:
                if line.startswith("H: Handlers="):
                    handlers = line.split("=", 1)[1]
                if line.startswith("B: EV="):
                    ev_bits = int(line.split("=", 1)[1], 16)
                    if ev_bits & (1 << EV_KEY):
                        has_key_capability = True

            if has_key_capability and "kbd" in handlers:
                for handler in handlers.split():
                    if handler.startswith("event"):
                        device_path = f"/dev/input/{handler}"
                        if os.access(device_path, os.R_OK):
                            devices.append(device_path)
    except Exception:
        pass

    return devices


class KeyDaemon:
    """Background daemon that monitors keyboard for Super key events."""

    def __init__(self, callbacks: DaemonCallbacks) -> None:
        self.callbacks = callbacks
        self._running = False
        self._thread: threading.Thread | None = None
        self._fds: list[int] = []
        self._stop_read_fd: int = -1
        self._stop_write_fd: int = -1
        self._super_held = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Start the monitoring daemon. Returns True if successful."""
        if self._running:
            return True

        devices = find_keyboard_devices()
        if not devices:
            self.callbacks.on_error("No keyboard devices found. Is user in 'input' group?")
            return False

        # Open devices
        for path in devices:
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                self._fds.append(fd)
            except OSError:
                pass

        if not self._fds:
            self.callbacks.on_error("Failed to open any keyboard devices.")
            return False

        # Create pipe for stopping the thread
        self._stop_read_fd, self._stop_write_fd = os.pipe()

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.callbacks.on_status_changed(True)
        return True

    def stop(self) -> None:
        """Stop the monitoring daemon."""
        if not self._running:
            return

        self._running = False

        # Signal the poll to wake up
        if self._stop_write_fd >= 0:
            try:
                os.write(self._stop_write_fd, b"x")
            except OSError:
                pass

        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

        # Close stop pipe
        for fd in (self._stop_read_fd, self._stop_write_fd):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._stop_read_fd = -1
        self._stop_write_fd = -1

        # Close device fds
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()

        self._super_held = False
        self.callbacks.on_status_changed(False)

    def _run_loop(self) -> None:
        """Main event reading loop (runs in background thread)."""
        poll = select.poll()
        for fd in self._fds:
            poll.register(fd, select.POLLIN)
        poll.register(self._stop_read_fd, select.POLLIN)

        while self._running:
            try:
                events = poll.poll(1000)
                for fd, event_mask in events:
                    if fd == self._stop_read_fd:
                        return
                    if event_mask & select.POLLIN:
                        self._read_events(fd)
            except Exception:
                if self._running:
                    continue
                break

    def _read_events(self, fd: int) -> None:
        """Read and process input events from a file descriptor."""
        try:
            data = os.read(fd, EVENT_SIZE * 64)
            for i in range(0, len(data), EVENT_SIZE):
                if i + EVENT_SIZE > len(data):
                    break
                _, _, ev_type, ev_code, ev_value = struct.unpack(
                    EVENT_FORMAT, data[i:i + EVENT_SIZE]
                )
                if ev_type == EV_KEY:
                    self._handle_key(ev_code, ev_value)
        except (BlockingIOError, OSError):
            pass

    def _handle_key(self, code: int, value: int) -> None:
        """Handle a key event."""
        is_super = code in (KEY_LEFTMETA, KEY_RIGHTMETA)
        if not is_super:
            return

        if value == KEY_PRESS and not self._super_held:
            self._super_held = True
            self.callbacks.on_super_pressed()
        elif value == KEY_RELEASE and self._super_held:
            self._super_held = False
            self.callbacks.on_super_released()
