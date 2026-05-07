"""
Settings card component for WinKey.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from src.i18n import LANGUAGE_DISPLAY_NAMES


def build_settings_card(window) -> Adw.PreferencesGroup:
    """Build the settings card."""
    t = window.t
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
    lang_codes = []
    active_idx = 0
    for i, (code, name) in enumerate(LANGUAGE_DISPLAY_NAMES.items()):
        lang_list.append(name)
        lang_codes.append(code)
        if code == window.config["language"]:
            active_idx = i

    window._lang_codes = lang_codes
    lang_dropdown = Gtk.DropDown(
        model=lang_list,
        valign=Gtk.Align.CENTER,
    )
    lang_dropdown.set_selected(active_idx)
    lang_dropdown.connect("notify::selected", window._on_language_changed)
    lang_row.add_suffix(lang_dropdown)
    group.add(lang_row)

    # Auto-start row
    autostart_row = Adw.ActionRow(
        title=t["start_on_login"],
        subtitle=t["start_on_login_desc"],
    )
    autostart_icon = Gtk.Image.new_from_icon_name("system-run-symbolic")
    autostart_row.add_prefix(autostart_icon)

    window.autostart_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
    window.autostart_switch.set_active(window.config["auto_start"])
    window.autostart_switch.connect("notify::active", window._on_autostart_toggled)
    autostart_row.add_suffix(window.autostart_switch)
    autostart_row.set_activatable_widget(window.autostart_switch)
    group.add(autostart_row)

    # Notifications row
    notif_row = Adw.ActionRow(
        title=t["show_notifications"],
        subtitle=t["show_notifications_desc"],
    )
    notif_icon = Gtk.Image.new_from_icon_name("preferences-system-notifications-symbolic")
    notif_row.add_prefix(notif_icon)

    window.notif_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
    window.notif_switch.set_active(window.config["show_notifications"])
    window.notif_switch.connect("notify::active", window._on_notif_toggled)
    notif_row.add_suffix(window.notif_switch)
    notif_row.set_activatable_widget(window.notif_switch)
    group.add(notif_row)

    # Tray icon row
    tray_row = Adw.ActionRow(
        title=t.get("show_tray_icon", "Show tray icon"),
        subtitle=t.get("show_tray_icon_desc", "Show an icon in the system tray"),
    )
    tray_icon = Gtk.Image.new_from_icon_name("view-pin-symbolic")
    tray_row.add_prefix(tray_icon)

    window.tray_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
    window.tray_switch.set_active(window.config.get("show_tray_icon", True))
    window.tray_switch.connect("notify::active", window._on_tray_toggled)
    tray_row.add_suffix(window.tray_switch)
    tray_row.set_activatable_widget(window.tray_switch)
    group.add(tray_row)

    return group
