"""
Main application window for WinKey.
Built with GTK4 + Libadwaita for a modern GNOME experience.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio, Pango
from pathlib import Path

from src.daemon import KeyDaemon
from src.input_source import get_current_index, set_current_index, get_all_sources, InputSource
from src.settings import WinKeyConfig, load_config, save_config
from src.i18n import get_translations, Translations, LANGUAGE_DISPLAY_NAMES

from src.ui.cards.status_card import build_status_card
from src.ui.cards.sources_card import build_sources_card
from src.ui.cards.settings_card import build_settings_card


# Path to icons
ICON_DIR = Path(__file__).parent.parent / "data" / "icons"


class WinKeyWindow(Adw.ApplicationWindow):
    """Main WinKey application window."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="WinKey")
        self.set_default_size(460, -1)
        self.set_resizable(False)

        # Load config and translations
        self.config: WinKeyConfig = load_config()
        self.t: Translations = get_translations(self.config["language"])
        self._saved_source: int | None = None
        self._switch_count: int = 0

        # Create daemon with self as callback handler
        self.daemon = KeyDaemon(self)

        # Build UI
        self._build_ui()

        # Auto-start daemon if enabled
        if self.config["enabled"]:
            GLib.timeout_add(500, self._auto_start)

    def _auto_start(self) -> bool:
        """Start daemon after window is shown."""
        if self.config["enabled"] and not self.daemon.is_running:
            self.daemon.start()
            self._update_status_ui()
        return False

    def _rebuild_ui(self) -> None:
        """Rebuild the entire UI with current translations."""
        self.t = get_translations(self.config["language"])
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the complete UI."""
        t = self.t

        # Header bar
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(
            title=t["app_title"],
            subtitle=t["app_subtitle"],
        ))

        # About button
        about_btn = Gtk.Button(icon_name="help-about-symbolic")
        about_btn.set_tooltip_text("About")
        about_btn.connect("clicked", self._on_about)
        header.pack_end(about_btn)

        # Quit button
        quit_btn = Gtk.Button(icon_name="application-exit-symbolic")
        quit_btn.set_tooltip_text("Quit WinKey")
        quit_btn.connect("clicked", self._on_quit)
        header.pack_start(quit_btn)

        # Main content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(header)

        # Scrollable content area
        clamp = Adw.Clamp(maximum_size=500)
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_top=24,
            margin_bottom=24,
            margin_start=16,
            margin_end=16,
        )

        # ── Status Card ──────────────────────────────────────────────
        main_box.append(build_status_card(self))

        # ── Input Sources Card ───────────────────────────────────────
        main_box.append(build_sources_card(self))

        # ── Settings Card ────────────────────────────────────────────
        main_box.append(build_settings_card(self))

        clamp.set_child(main_box)
        content.append(clamp)
        self.set_content(content)

    # (Card build methods removed and extracted to src/ui/cards/)

    # ── Daemon Callbacks (called from background thread) ─────────────

    def on_super_pressed(self) -> None:
        """Called when Super key is pressed."""
        GLib.idle_add(self._handle_super_pressed)

    def on_super_released(self) -> None:
        """Called when Super key is released."""
        GLib.idle_add(self._handle_super_released)

    def on_status_changed(self, running: bool) -> None:
        """Called when daemon status changes."""
        GLib.idle_add(self._update_status_ui)

    def on_error(self, message: str) -> None:
        """Called when daemon encounters an error."""
        GLib.idle_add(self._show_error, message)

    # ── UI Thread Handlers ───────────────────────────────────────────

    def _handle_super_pressed(self) -> None:
        """Handle Super key press on UI thread."""
        current = get_current_index()
        target = self.config["english_index"]

        if current != target:
            self._saved_source = current
            set_current_index(target)
            self._switch_count += 1
            self.counter_row.set_subtitle(str(self._switch_count))
        else:
            self._saved_source = None

        self._update_current_source_display()

    def _handle_super_released(self) -> None:
        """Handle Super key release on UI thread."""
        if self._saved_source is not None:
            set_current_index(self._saved_source)
            self._saved_source = None

        self._update_current_source_display()

    def _update_status_ui(self) -> None:
        """Update status indicators in the UI."""
        t = self.t
        running = self.daemon.is_running
        if running:
            self.status_row.set_subtitle(t["running"])
            self.status_icon.set_from_icon_name("media-record-symbolic")
            self.status_icon.remove_css_class("error")
            self.status_icon.add_css_class("success")
        else:
            self.status_row.set_subtitle(t["stopped"])
            self.status_icon.set_from_icon_name("media-record-symbolic")
            self.status_icon.remove_css_class("success")
            self.status_icon.add_css_class("error")

    def _update_current_source_display(self) -> bool:
        """Update the current input source display."""
        current = get_current_index()
        sources = self.sources if self.sources else get_all_sources()
        for src in sources:
            if src.index == current:
                self.current_source_row.set_subtitle(src.display_name)
                return False
        self.current_source_row.set_subtitle(f"Source #{current}")
        return False

    def _show_error(self, message: str) -> None:
        """Show an error dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=self.t["error"],
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    # ── Signal Handlers ──────────────────────────────────────────────

    def _on_power_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        """Handle power switch toggle."""
        active = switch.get_active()
        self.config["enabled"] = active
        save_config(self.config)

        if active:
            if not self.daemon.start():
                switch.set_active(False)
                self.config["enabled"] = False
                save_config(self.config)
        else:
            if self._saved_source is not None:
                set_current_index(self._saved_source)
                self._saved_source = None
            self.daemon.stop()

        self._update_status_ui()

    def _on_source_selected(self, check: Gtk.CheckButton, index: int) -> None:
        """Handle target English source selection."""
        if check.get_active():
            self.config["english_index"] = index
            save_config(self.config)

    def _on_language_changed(self, dropdown: Gtk.DropDown, _pspec: object) -> None:
        """Handle language dropdown change."""
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._lang_codes):
            new_lang = self._lang_codes[idx]
            if new_lang != self.config["language"]:
                self.config["language"] = new_lang
                save_config(self.config)
                self._rebuild_ui()

    def _on_autostart_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        """Handle auto-start toggle."""
        active = switch.get_active()
        self.config["auto_start"] = active
        save_config(self.config)
        self._update_autostart_desktop()

    def _on_notif_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        """Handle notifications toggle."""
        self.config["show_notifications"] = switch.get_active()
        save_config(self.config)

    def _on_reset_counter(self, _btn: Gtk.Button) -> None:
        """Reset switch counter."""
        self._switch_count = 0
        self.counter_row.set_subtitle("0")

    def _on_about(self, _btn: Gtk.Button) -> None:
        """Show about dialog."""
        t = self.t
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="WinKey",
            application_icon="winkey",
            developer_name="WinKey",
            version="1.0.0",
            comments=t["about_comments"],
            website="https://github.com/user/winkey",
            license_type=Gtk.License.MIT_X11,
            developers=["WinKey Contributors"],
        )
        about.present()

    def _update_autostart_desktop(self) -> None:
        """Create or remove autostart .desktop file."""
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "winkey.desktop"
        app_path = Path(__file__).parent.parent / "winkey.py"

        if self.config["auto_start"]:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            icon_path = ICON_DIR / "winkey.svg"
            content = f"""[Desktop Entry]
Type=Application
Name=WinKey
Comment=Super Key Input Source Switcher
Exec=python3 {app_path}
Icon={icon_path}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""
            desktop_file.write_text(content)
        else:
            if desktop_file.exists():
                desktop_file.unlink()

    def _on_quit(self, _btn: Gtk.Button) -> None:
        """Completely quit the application."""
        if self._saved_source is not None:
            set_current_index(self._saved_source)
        self.daemon.stop()
        self.get_application().quit()

    def do_close_request(self) -> bool:
        """Handle window close - hide to background instead of quitting."""
        self.set_visible(False)
        return True
