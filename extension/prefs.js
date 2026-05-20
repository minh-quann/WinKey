import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk?version=4.0';
import Adw from 'gi://Adw?version=1';
import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class WinKeyPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        // Create a preferences page
        const page = new Adw.PreferencesPage({
            title: _('General'),
            icon_name: 'dialog-information-symbolic',
        });
        window.add(page);

        // Create a group for settings
        const group = new Adw.PreferencesGroup({
            title: _('Input Switcher Settings'),
            description: _('Configure the WinKey Super key behavior'),
        });
        page.add(group);

        const settings = this.getSettings();

        // Enable Switch
        const enableRow = new Adw.SwitchRow({
            title: _('Enable WinKey'),
            subtitle: _('Turn the input switcher on or off'),
        });
        group.add(enableRow);
        settings.bind('enabled', enableRow, 'active', Gio.SettingsBindFlags.DEFAULT);

        // English Index SpinRow
        const indexRow = new Adw.SpinRow({
            title: _('English Input Index'),
            subtitle: _('The index of the target English input source (0 = first, 1 = second...)'),
            adjustment: new Gtk.Adjustment({
                lower: 0,
                upper: 10,
                step_increment: 1,
            }),
        });
        group.add(indexRow);
        settings.bind('english-index', indexRow, 'value', Gio.SettingsBindFlags.DEFAULT);

        // Version Info Row
        const versionVal = this.metadata.version ? this.metadata.version.toString() : '10';
        const versionRow = new Adw.ActionRow({
            title: _('Extension Version'),
            subtitle: `v${versionVal}`,
        });
        group.add(versionRow);
    }
}
