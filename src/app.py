"""
WinKey GTK Application.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio
from pathlib import Path

from src.ui.window import WinKeyWindow


# Icon directory
ICON_DIR = Path(__file__).parent.parent / "data" / "icons"


class WinKeyApp(Adw.Application):
    """Main GTK Application for WinKey."""

    def __init__(self) -> None:
        super().__init__(
            application_id="com.github.winkey",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window: WinKeyWindow | None = None

    def do_startup(self) -> None:
        """Application startup - load CSS and icons."""
        Adw.Application.do_startup(self)
        self._load_css()
        self._register_icons()

    def do_activate(self) -> None:
        """Application activation - show main window."""
        if not self.window:
            self.window = WinKeyWindow(self)
        self.window.present()

    def _load_css(self) -> None:
        """Load custom CSS stylesheet."""
        css_provider = self.get_style_manager()

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
