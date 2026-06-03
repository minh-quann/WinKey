import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

/**
 * WinKey Window Helper Extension
 *
 * Lightweight GNOME Shell extension that exposes the focused window's
 * WM class and title via a D-Bus interface. This allows the WinKey
 * GUI app (external process) to detect terminal windows on Wayland,
 * where no other window inspection method is available.
 *
 * D-Bus interface: com.github.winkey.WindowHelper
 * Object path: /com/github/winkey/WindowHelper
 * Method: GetFocusedWindow() → (wm_class: s, title: s)
 * Signal: FocusedWindowChanged(wm_class: s, title: s)
 */

const DBUS_INTERFACE = `
<node>
  <interface name="com.github.winkey.WindowHelper">
    <method name="GetFocusedWindow">
      <arg type="s" direction="out" name="wm_class"/>
      <arg type="s" direction="out" name="title"/>
    </method>
    <signal name="FocusedWindowChanged">
      <arg type="s" name="wm_class"/>
      <arg type="s" name="title"/>
    </signal>
  </interface>
</node>`;


export default class WinKeyHelperExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._dbusId = 0;
        this._focusId = 0;
        this._lastWmClass = '';
        this._lastTitle = '';
    }

    enable() {
        // Register D-Bus service
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(
            DBUS_INTERFACE,
            this
        );
        this._dbusImpl.export(
            Gio.DBus.session,
            '/com/github/winkey/WindowHelper'
        );

        // Own the bus name so clients can find us
        this._dbusId = Gio.bus_own_name(
            Gio.BusType.SESSION,
            'com.github.winkey.WindowHelper',
            Gio.BusNameOwnerFlags.NONE,
            null, null, null
        );

        // Listen for focus changes
        this._focusId = global.display.connect(
            'notify::focus-window',
            this._onFocusChanged.bind(this)
        );

        console.log('[WinKey Helper] Extension enabled');
    }

    disable() {
        if (this._focusId > 0) {
            global.display.disconnect(this._focusId);
            this._focusId = 0;
        }

        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }

        if (this._dbusId > 0) {
            Gio.bus_unown_name(this._dbusId);
            this._dbusId = 0;
        }

        console.log('[WinKey Helper] Extension disabled');
    }

    /**
     * D-Bus method: GetFocusedWindow
     * Returns the WM class and title of the currently focused window.
     */
    GetFocusedWindow() {
        const win = global.display.focus_window;
        if (!win) return ['', ''];
        return [
            win.get_wm_class() || '',
            win.get_title() || '',
        ];
    }

    /**
     * Notify GUI app when focused window changes.
     */
    _onFocusChanged() {
        const win = global.display.focus_window;
        if (!win) return;

        const wmClass = win.get_wm_class() || '';
        const title = win.get_title() || '';

        // Only emit if something changed
        if (wmClass !== this._lastWmClass || title !== this._lastTitle) {
            this._lastWmClass = wmClass;
            this._lastTitle = title;

            if (this._dbusImpl) {
                this._dbusImpl.emit_signal(
                    'FocusedWindowChanged',
                    new GLib.Variant('(ss)', [wmClass, title])
                );
            }
        }
    }
}
