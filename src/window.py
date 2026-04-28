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
        self._build_status_card(main_box)

        # ── Input Sources Card ───────────────────────────────────────
        self._build_sources_card(main_box)

        # ── Settings Card ────────────────────────────────────────────
        self._build_settings_card(main_box)

        clamp.set_child(main_box)
        content.append(clamp)
        self.set_content(content)

    def _build_status_card(self, parent: Gtk.Box) -> None:
        """Build the status/control card."""
        t = self.t
        group = Adw.PreferencesGroup(title=t["status_title"])

        # Status row with indicator
        self.status_row = Adw.ActionRow(title=t["service"])
        self.status_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.status_row.add_prefix(self.status_icon)

        # Power toggle switch
        self.power_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.power_switch.set_active(self.config["enabled"])
        self.power_switch.connect("notify::active", self._on_power_toggled)
        self.status_row.add_suffix(self.power_switch)
        self.status_row.set_activatable_widget(self.power_switch)
        group.add(self.status_row)

        # Update status display
        self._update_status_ui()

        # Switch counter row
        self.counter_row = Adw.ActionRow(
            title=t["times_switched"],
            subtitle=str(self._switch_count),
        )
        counter_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        self.counter_row.add_prefix(counter_icon)

        reset_btn = Gtk.Button(
            icon_name="edit-clear-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text=t["reset_counter"],
        )
        reset_btn.add_css_class("flat")
        reset_btn.connect("clicked", self._on_reset_counter)
        self.counter_row.add_suffix(reset_btn)
        group.add(self.counter_row)

        # Current input source indicator
        self.current_source_row = Adw.ActionRow(
            title=t["current_input"],
            subtitle=t["detecting"],
        )
        current_icon = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
        self.current_source_row.add_prefix(current_icon)
        group.add(self.current_source_row)

        parent.append(group)

        # Fetch current source display
        GLib.timeout_add(500, self._update_current_source_display)

    def _build_sources_card(self, parent: Gtk.Box) -> None:
        """Build the input sources configuration card."""
        t = self.t
        group = Adw.PreferencesGroup(
            title=t["target_source_title"],
            description=t["target_source_desc"],
        )

        self.sources = get_all_sources()
        self._first_radio: Gtk.CheckButton | None = None

        if self.sources:
            for source in self.sources:
                row = Adw.ActionRow(
                    title=source.display_name,
                    subtitle=f"{source.source_type}: {source.source_id}",
                )

                check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
                if source.index == self.config["english_index"]:
                    check.set_active(True)

                if self._first_radio is None:
                    self._first_radio = check
                else:
                    check.set_group(self._first_radio)

                check.connect("toggled", self._on_source_selected, source.index)
                row.add_prefix(check)
                row.set_activatable_widget(check)

                type_label = Gtk.Label(
                    label=source.source_type.upper(),
                    valign=Gtk.Align.CENTER,
                )
                type_label.add_css_class("dim-label")
                type_label.add_css_class("caption")
                row.add_suffix(type_label)

                group.add(row)
        else:
            row = Adw.ActionRow(
                title=t["no_sources"],
                subtitle=t["no_sources_hint"],
            )
            row.add_prefix(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))
            group.add(row)

        parent.append(group)

    def _build_settings_card(self, parent: Gtk.Box) -> None:
        """Build the settings card."""
        t = self.t
        group = Adw.PreferencesGroup(title=t["options_title"])

        # Language selector row
        lang_row = Adw.ActionRow(
            title=t["language"],
            subtitle=t["language_desc"],
        )
        lang_icon = Gtk.Image.new_from_icon_name("preferences-desktop-locale-symbolic")
        lang_row.add_prefix(lang_icon)

        # Language dropdown
        lang_list = Gtk.StringList()
        lang_codes: list[str] = []
        active_idx = 0
        for i, (code, name) in enumerate(LANGUAGE_DISPLAY_NAMES.items()):
            lang_list.append(name)
            lang_codes.append(code)
            if code == self.config["language"]:
                active_idx = i

        self._lang_codes = lang_codes
        lang_dropdown = Gtk.DropDown(
            model=lang_list,
            valign=Gtk.Align.CENTER,
        )
        lang_dropdown.set_selected(active_idx)
        lang_dropdown.connect("notify::selected", self._on_language_changed)
        lang_row.add_suffix(lang_dropdown)
        group.add(lang_row)

        # Auto-start row
        autostart_row = Adw.ActionRow(
            title=t["start_on_login"],
            subtitle=t["start_on_login_desc"],
        )
        autostart_icon = Gtk.Image.new_from_icon_name("system-run-symbolic")
        autostart_row.add_prefix(autostart_icon)

        self.autostart_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.autostart_switch.set_active(self.config["auto_start"])
        self.autostart_switch.connect("notify::active", self._on_autostart_toggled)
        autostart_row.add_suffix(self.autostart_switch)
        autostart_row.set_activatable_widget(self.autostart_switch)
        group.add(autostart_row)

        # Notifications row
        notif_row = Adw.ActionRow(
            title=t["show_notifications"],
            subtitle=t["show_notifications_desc"],
        )
        notif_icon = Gtk.Image.new_from_icon_name("preferences-system-notifications-symbolic")
        notif_row.add_prefix(notif_icon)

        self.notif_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.notif_switch.set_active(self.config["show_notifications"])
        self.notif_switch.connect("notify::active", self._on_notif_toggled)
        notif_row.add_suffix(self.notif_switch)
        notif_row.set_activatable_widget(self.notif_switch)
        group.add(notif_row)

        parent.append(group)

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

    def do_close_request(self) -> bool:
        """Handle window close - stop daemon cleanly."""
        if self._saved_source is not None:
            set_current_index(self._saved_source)
        self.daemon.stop()
        return False
