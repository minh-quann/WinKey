"""
Input sources configuration card component for WinKey.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw
from src.input_source import get_all_sources


def build_sources_card(window) -> Adw.PreferencesGroup:
    """Build the input sources configuration card."""
    t = window.t
    group = Adw.PreferencesGroup(
        title=t["target_source_title"],
        description=t["target_source_desc"],
    )

    window.sources = get_all_sources()
    window._first_radio = None

    if window.sources:
        for source in window.sources:
            row = Adw.ActionRow(
                title=source.display_name,
                subtitle=f"{source.source_type}: {source.source_id}",
            )

            check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            if source.index == window.config["english_index"]:
                check.set_active(True)

            if window._first_radio is None:
                window._first_radio = check
            else:
                check.set_group(window._first_radio)

            check.connect("toggled", window._on_source_selected, source.index)
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

    return group
