import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {getInputSourceManager} from 'resource:///org/gnome/shell/ui/status/keyboard.js';

/**
 * WinKey Input Switcher Extension v10
 *
 * Combines multiple switching methods for maximum reliability:
 * 1. InputSourceManager.activate() - GNOME internal API
 * 2. GSettings current - affects GNOME's source tracking
 * 3. Gio.Subprocess ibus engine - direct IBus engine switch
 *
 * Terminal detection:
 * - Native terminals: detected by wm_class (Ptyxis, Kitty, etc.)
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
        this._sourceBeforeTerminal = -1;
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
                    console.log(`[WinKey] Source ${i}: ${srcType}/${srcId} → "${engine}"`);
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
        console.log(`[WinKey] Switching to index ${index}, engine="${engine}"`);

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

        console.log(`[WinKey] Overview SHOWING: saved=${this._sourceBeforeOverview}, target=${targetIndex}`);

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

        console.log(`[WinKey] Overview HIDDEN: restoreIndex=${restoreIndex}`);

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
                GLib.timeout_add(GLib.PRIORITY_HIGH, delay, () => {
                    this._switchTo(restoreIndex);
                    this._lastSourceIndex = restoreIndex;
                    return GLib.SOURCE_REMOVE;
                });
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
        console.log(`[WinKey] Terminal detected (${source}), switching to English`);
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
        console.log(`[WinKey] Terminal left (${reason}), restoring previous source`);
        this._inTerminal = false;

        const restoreIndex = this._sourceBeforeTerminal;
        const targetIndex = this._extSettings.get_int('english-index');

        if (restoreIndex !== -1 && restoreIndex !== targetIndex) {
            const delays = [0, 50, 150];
            for (const delay of delays) {
                if (delay === 0) {
                    this._switchTo(restoreIndex);
                } else {
                    GLib.timeout_add(GLib.PRIORITY_HIGH, delay, () => {
                        this._switchTo(restoreIndex);
                        this._lastSourceIndex = restoreIndex;
                        return GLib.SOURCE_REMOVE;
                    });
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

    enable() {
        console.log('[WinKey] Enabling extension v10 (simplified, system terminal only)');
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
        console.log(`[WinKey] Initial source: ${this._lastSourceIndex}`);

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

        console.log('[WinKey] Extension enabled');
    }

    disable() {
        console.log('[WinKey] Disabling extension');

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

        try {
            const ism = getInputSourceManager();
            if (ism && this._ismChangedId > 0) {
                ism.disconnect(this._ismChangedId);
                this._ismChangedId = 0;
            }
        } catch (e) {
            // ignore
        }

        this._extSettings = null;
        this._inputSettings = null;
        this._engineMap = {};
    }
}
