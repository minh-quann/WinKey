import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {getInputSourceManager} from 'resource:///org/gnome/shell/ui/status/keyboard.js';

/**
 * D-Bus interface for exposing focused window info to the WinKey GUI app.
 * This is needed because GNOME Shell.Introspect blocks GetWindows for
 * external processes on Wayland.
 */
const DBUS_IFACE = `
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

/**
 * WinKey Input Switcher Extension v11
 *
 * Combines multiple switching methods for maximum reliability:
 * 1. InputSourceManager.activate() - GNOME internal API
 * 2. GSettings current - affects GNOME's source tracking
 * 3. Gio.Subprocess ibus engine - direct IBus engine switch
 *
 * Terminal detection:
 * - Native terminals: detected by wm_class (Ptyxis, Kitty, etc.)
 *
 * D-Bus helper:
 * - Exposes focused window info for the WinKey GUI app (Wayland support)
 *
 * Uses Overview showing/hidden signals to detect Super key.
 */
export default class WinKeyExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._extSettings = null;
        this._inputSettings = null;
        this._overviewShowingId = 0;
        this._overviewHiddenId = 0;
        this._ismChangedId = 0;
        this._lastSourceIndex = -1;
        this._sourceBeforeOverview = -1;
        this._engineMap = {};
        this._restoreTimeoutId = 0;
        
        // Terminal auto-switch
        this._focusWindowId = 0;
        this._inTerminal = false;

        // D-Bus helper for GUI app
        this._dbusImpl = null;
        this._dbusNameId = 0;
        this._titleChangedId = 0;
        this._titleChangedWindow = null;
        this._sourceBeforeTerminal = -1;

        // Track pending timeout IDs for cleanup in disable()
        this._pendingTimeoutIds = [];

        // Debug flag — set to true for verbose logging
        this._debug = false;
    }

    /**
     * Gated log — only prints when _debug is true.
     */
    _log(msg) {
        if (this._debug)
            console.log(`[WinKey] ${msg}`);
    }

    /**
     * Build a map: source index → ibus engine name
     */
    _buildEngineMap() {
        try {
            const sourcesVariant = this._inputSettings.get_value('sources');
            const nSources = sourcesVariant.n_children();
            this._engineMap = {};

            for (let i = 0; i < nSources; i++) {
                const entry = sourcesVariant.get_child_value(i);
                const srcType = entry.get_child_value(0).get_string()[0];
                const srcId = entry.get_child_value(1).get_string()[0];

                let engine;
                if (srcType === 'ibus') {
                    engine = srcId;
                } else if (srcType === 'xkb') {
                    if (srcId.includes('+')) {
                        const [layout, variant] = srcId.split('+', 2);
                        engine = `xkb:${layout}:${variant}:eng`;
                    } else {
                        engine = `xkb:${srcId}::eng`;
                    }
                }

                if (engine) {
                    this._engineMap[i] = engine;
                    this._log(`Source ${i}: ${srcType}/${srcId} → "${engine}"`);
                }
            }
        } catch (e) {
            console.error('[WinKey] Failed to build engine map:', e);
        }
    }

    /**
     * Switch input source using ALL available methods
     */
    _switchTo(index) {
        const engine = this._engineMap[index];
        this._log(`Switching to index ${index}, engine="${engine}"`);

        // Method 1: InputSourceManager.activate()
        try {
            const ism = getInputSourceManager();
            if (ism && ism._inputSources && ism._inputSources[index]) {
                ism._inputSources[index].activate(true);
            }
        } catch (e) {
            console.error('[WinKey] ISM activate failed:', e);
        }

        // Method 2: Set GSettings current
        try {
            this._inputSettings.set_uint('current', index);
        } catch (e) {
            console.error('[WinKey] GSettings set failed:', e);
        }

        // Method 3: ibus engine CLI (async, non-blocking)
        if (engine) {
            try {
                Gio.Subprocess.new(
                    ['ibus', 'engine', engine],
                    Gio.SubprocessFlags.NONE
                );
            } catch (e) {
                console.error('[WinKey] ibus engine spawn failed:', e);
            }
        }
    }

    /**
     * Track input source changes — only when Overview is NOT visible
     */
    _onSourceChanged() {
        if (Main.overview.visible) return;
        if (this._inTerminal) return;

        try {
            const ism = getInputSourceManager();
            if (ism && ism.currentSource) {
                this._lastSourceIndex = ism.currentSource.index;
            }
        } catch (e) {
            // ignore
        }
    }

    _onOverviewShowing() {
        if (!this._extSettings.get_boolean('enabled')) return;

        // Save what the user was using BEFORE overview opened
        this._sourceBeforeOverview = this._lastSourceIndex;
        const targetIndex = this._extSettings.get_int('english-index');

        this._log(`Overview SHOWING: saved=${this._sourceBeforeOverview}, target=${targetIndex}`);

        // Switch to English immediately
        if (this._sourceBeforeOverview !== targetIndex &&
            this._sourceBeforeOverview !== -1) {
            this._switchTo(targetIndex);
        }
    }

    _onOverviewHidden() {
        if (!this._extSettings.get_boolean('enabled')) return;

        const targetIndex = this._extSettings.get_int('english-index');
        const restoreIndex = this._sourceBeforeOverview;

        this._log(`Overview HIDDEN: restoreIndex=${restoreIndex}`);

        if (restoreIndex === -1 || restoreIndex === targetIndex) {
            this._sourceBeforeOverview = -1;
            return;
        }

        // Clear pending timeouts
        if (this._restoreTimeoutId > 0) {
            GLib.source_remove(this._restoreTimeoutId);
            this._restoreTimeoutId = 0;
        }

        // Restore with multiple attempts at different delays
        // to fight GNOME's own input source restoration
        const delays = [0, 50, 150, 300];
        for (const delay of delays) {
            if (delay === 0) {
                this._switchTo(restoreIndex);
            } else {
                const id = GLib.timeout_add(GLib.PRIORITY_HIGH, delay, () => {
                    this._pendingTimeoutIds = this._pendingTimeoutIds.filter(t => t !== id);
                    this._switchTo(restoreIndex);
                    this._lastSourceIndex = restoreIndex;
                    return GLib.SOURCE_REMOVE;
                });
                this._pendingTimeoutIds.push(id);
            }
        }

        this._sourceBeforeOverview = -1;
    }

    // ─── Terminal Mode Management ─────────────────────────────────────

    /**
     * Enter terminal mode - switch to English
     * @param {string} source - 'wm_class' for native terminals
     */
    _enterTerminalMode(source) {
        if (this._inTerminal) return;
        this._log(`Terminal detected (${source}), switching to English`);
        this._sourceBeforeTerminal = this._lastSourceIndex;
        this._inTerminal = true;

        const targetIndex = this._extSettings.get_int('english-index');
        if (this._sourceBeforeTerminal !== targetIndex && this._sourceBeforeTerminal !== -1) {
            this._switchTo(targetIndex);
        }
    }

    /**
     * Leave terminal mode - restore previous input source
     */
    _leaveTerminalMode(reason) {
        if (!this._inTerminal) return;
        this._log(`Terminal left (${reason}), restoring previous source`);
        this._inTerminal = false;

        const restoreIndex = this._sourceBeforeTerminal;
        const targetIndex = this._extSettings.get_int('english-index');

        if (restoreIndex !== -1 && restoreIndex !== targetIndex) {
            const delays = [0, 50, 150];
            for (const delay of delays) {
                if (delay === 0) {
                    this._switchTo(restoreIndex);
                } else {
                    const id = GLib.timeout_add(GLib.PRIORITY_HIGH, delay, () => {
                        this._pendingTimeoutIds = this._pendingTimeoutIds.filter(t => t !== id);
                        this._switchTo(restoreIndex);
                        this._lastSourceIndex = restoreIndex;
                        return GLib.SOURCE_REMOVE;
                    });
                    this._pendingTimeoutIds.push(id);
                }
            }
        }
        this._sourceBeforeTerminal = -1;
    }

    // ─── Window Focus Tracking ────────────────────────────────────────

    /**
     * Handle active window changes to detect terminals
     */
    _onFocusWindowChanged() {
        // Disconnect previous title tracking
        if (this._titleChangedId > 0 && this._titleChangedWindow) {
            try {
                this._titleChangedWindow.disconnect(this._titleChangedId);
            } catch (e) {
                // window may have been destroyed
            }
            this._titleChangedId = 0;
            this._titleChangedWindow = null;
        }

        // Emit D-Bus signal for the GUI app
        this._emitFocusChanged();

        // Track title changes on the new focused window
        // (needed for detecting IDE terminal panel switches)
        const newWin = global.display.focus_window;
        if (newWin) {
            try {
                this._titleChangedWindow = newWin;
                this._titleChangedId = newWin.connect(
                    'notify::title',
                    () => this._emitFocusChanged()
                );
            } catch (e) {
                // ignore
            }
        }

        if (!this._extSettings.get_boolean('enabled')) return;

        const focusWindow = global.display.focus_window;
        if (!focusWindow) return;

        const wmClass = focusWindow.get_wm_class() ? focusWindow.get_wm_class().toLowerCase() : '';
        const terminalClasses = [
            'gnome-terminal', 'kitty', 'alacritty', 'wezterm', 
            'konsole', 'tilix', 'terminator', 'xterm', 
            'blackbox', 'ptyxis', 'guake', 'yakuake'
        ];

        const isTerminal = terminalClasses.some(c => wmClass.includes(c));

        if (isTerminal) {
            // Native terminal app - always switch to English
            this._enterTerminalMode(wmClass);
        } else {
            // Non-terminal app - leave terminal mode
            this._leaveTerminalMode(wmClass);
        }
    }

    // ─── Enable / Disable ─────────────────────────────────────────────

    // ─── D-Bus Helper for GUI app ────────────────────────────────────

    /**
     * D-Bus method: GetFocusedWindow
     * Called by the WinKey GUI app to get focused window info.
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
     * Emit D-Bus signal when focused window changes.
     */
    _emitFocusChanged() {
        if (!this._dbusImpl) return;
        const win = global.display.focus_window;
        if (!win) return;
        const wmClass = win.get_wm_class() || '';
        const title = win.get_title() || '';
        try {
            this._dbusImpl.emit_signal(
                'FocusedWindowChanged',
                new GLib.Variant('(ss)', [wmClass, title])
            );
        } catch (e) {
            // ignore
        }
    }

    // ─── Enable / Disable ─────────────────────────────────────────────

    enable() {
        this._log('Enabling extension v11 (with D-Bus helper)');
        this._extSettings = this.getSettings();
        this._inputSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.input-sources',
        });

        this._buildEngineMap();

        // Get initial source index
        try {
            const ism = getInputSourceManager();
            if (ism && ism.currentSource) {
                this._lastSourceIndex = ism.currentSource.index;
            }
        } catch (e) {
            this._lastSourceIndex = this._inputSettings.get_uint('current');
        }
        this._log(`Initial source: ${this._lastSourceIndex}`);

        // Track source changes
        try {
            const ism = getInputSourceManager();
            if (ism) {
                this._ismChangedId = ism.connect(
                    'current-source-changed',
                    this._onSourceChanged.bind(this)
                );
            }
        } catch (e) {
            console.error('[WinKey] Failed to connect ISM signal:', e);
        }

        // Overview signals
        this._overviewShowingId = Main.overview.connect(
            'showing', this._onOverviewShowing.bind(this)
        );
        this._overviewHiddenId = Main.overview.connect(
            'hidden', this._onOverviewHidden.bind(this)
        );

        // Terminal focus tracking
        this._focusWindowId = global.display.connect(
            'notify::focus-window',
            this._onFocusWindowChanged.bind(this)
        );

        // ── D-Bus helper service ─────────────────────────────────
        try {
            this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(
                DBUS_IFACE, this
            );
            this._dbusImpl.export(
                Gio.DBus.session,
                '/com/github/winkey/WindowHelper'
            );
            this._dbusNameId = Gio.bus_own_name(
                Gio.BusType.SESSION,
                'com.github.winkey.WindowHelper',
                Gio.BusNameOwnerFlags.NONE,
                null, null, null
            );
            this._log('D-Bus helper service registered');
        } catch (e) {
            console.error('[WinKey] Failed to register D-Bus helper:', e);
        }

        this._log('Extension enabled');
    }

    disable() {
        this._log('Disabling extension');

        // Remove all pending timeout sources
        for (const id of this._pendingTimeoutIds) {
            GLib.source_remove(id);
        }
        this._pendingTimeoutIds = [];

        if (this._restoreTimeoutId > 0) {
            GLib.source_remove(this._restoreTimeoutId);
            this._restoreTimeoutId = 0;
        }

        if (this._overviewShowingId > 0) {
            Main.overview.disconnect(this._overviewShowingId);
            this._overviewShowingId = 0;
        }
        if (this._overviewHiddenId > 0) {
            Main.overview.disconnect(this._overviewHiddenId);
            this._overviewHiddenId = 0;
        }
        if (this._focusWindowId > 0) {
            global.display.disconnect(this._focusWindowId);
            this._focusWindowId = 0;
        }
        // Cleanup title change tracking
        if (this._titleChangedId > 0 && this._titleChangedWindow) {
            try {
                this._titleChangedWindow.disconnect(this._titleChangedId);
            } catch (e) {
                // window may have been destroyed
            }
            this._titleChangedId = 0;
            this._titleChangedWindow = null;
        }

        try {
            const ism = getInputSourceManager();
            if (ism && this._ismChangedId > 0) {
                ism.disconnect(this._ismChangedId);
                this._ismChangedId = 0;
            }
        } catch (e) {
            // ignore
        }

        // ── Cleanup D-Bus helper ─────────────────────────────────
        if (this._dbusImpl) {
            try {
                this._dbusImpl.unexport();
            } catch (e) {
                // ignore
            }
            this._dbusImpl = null;
        }
        if (this._dbusNameId > 0) {
            Gio.bus_unown_name(this._dbusNameId);
            this._dbusNameId = 0;
        }

        this._extSettings = null;
        this._inputSettings = null;
        this._engineMap = {};
    }
}
