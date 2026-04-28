"""
Status card component for WinKey.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib


def build_status_card(window) -> Adw.PreferencesGroup:
    """Build the status/control card."""
    t = window.t
    group = Adw.PreferencesGroup(title=t["status_title"])

    # Status row with indicator
    window.status_row = Adw.ActionRow(title=t["service"])
    window.status_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
    window.status_row.add_prefix(window.status_icon)

    # Power toggle switch
    window.power_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
    window.power_switch.set_active(window.config["enabled"])
    window.power_switch.connect("notify::active", window._on_power_toggled)
    window.status_row.add_suffix(window.power_switch)
    window.status_row.set_activatable_widget(window.power_switch)
    group.add(window.status_row)

    # Update status display
    window._update_status_ui()

    # Switch counter row
    window.counter_row = Adw.ActionRow(
        title=t["times_switched"],
        subtitle=str(window._switch_count),
    )
    counter_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
    window.counter_row.add_prefix(counter_icon)

    reset_btn = Gtk.Button(
        icon_name="edit-clear-symbolic",
        valign=Gtk.Align.CENTER,
        tooltip_text=t["reset_counter"],
    )
    reset_btn.add_css_class("flat")
    reset_btn.connect("clicked", window._on_reset_counter)
    window.counter_row.add_suffix(reset_btn)
    group.add(window.counter_row)

    # Current input source indicator
    window.current_source_row = Adw.ActionRow(
        title=t["current_input"],
        subtitle=t["detecting"],
    )
    current_icon = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
    window.current_source_row.add_prefix(current_icon)
    group.add(window.current_source_row)

    # Fetch current source display
    GLib.timeout_add(500, window._update_current_source_display)

    return group
