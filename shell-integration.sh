#!/bin/bash
# WinKey Shell Integration
# Auto-switch to English in Antigravity / VS Code integrated terminals.
# Compatible with both bash and zsh.
#
# Add to your shell config:
#   bash: source ~/Documents/WinKey/shell-integration.sh  (in ~/.bashrc)
#   zsh:  source ~/Documents/WinKey/shell-integration.sh  (in ~/.zshrc)

# Only activate inside VS Code / Antigravity integrated terminal
# Antigravity sets ANTIGRAVITY_AGENT=1, VS Code sets TERM_PROGRAM=vscode
if [[ -n "$ANTIGRAVITY_AGENT" ]] || [[ "$TERM_PROGRAM" == "vscode" ]] || [[ -n "$VSCODE_PID" ]]; then

    __winkey_enter_terminal() {
        # Notify extension that terminal is focused (non-blocking, background)
        if [[ -n "$ZSH_VERSION" ]]; then
            dbus-send --session --type=method_call \
                --dest=org.gnome.Shell \
                /org/gnome/shell/extensions/WinKey \
                org.gnome.shell.extensions.WinKey.SetTerminalMode \
                boolean:true 2>/dev/null &!
        else
            dbus-send --session --type=method_call \
                --dest=org.gnome.Shell \
                /org/gnome/shell/extensions/WinKey \
                org.gnome.shell.extensions.WinKey.SetTerminalMode \
                boolean:true 2>/dev/null & disown &>/dev/null
        fi
    }

    __winkey_leave_terminal() {
        # Notify extension that terminal lost focus
        if [[ -n "$ZSH_VERSION" ]]; then
            dbus-send --session --type=method_call \
                --dest=org.gnome.Shell \
                /org/gnome/shell/extensions/WinKey \
                org.gnome.shell.extensions.WinKey.SetTerminalMode \
                boolean:false 2>/dev/null &!
        else
            dbus-send --session --type=method_call \
                --dest=org.gnome.Shell \
                /org/gnome/shell/extensions/WinKey \
                org.gnome.shell.extensions.WinKey.SetTerminalMode \
                boolean:false 2>/dev/null & disown &>/dev/null
        fi
    }

    # Switch to English on every new prompt (terminal is active)
    if [[ -n "$ZSH_VERSION" ]]; then
        # Zsh: use precmd hook
        __winkey_precmd() {
            __winkey_enter_terminal
        }
        autoload -Uz add-zsh-hook
        add-zsh-hook precmd __winkey_precmd
    else
        # Bash: use PROMPT_COMMAND
        PROMPT_COMMAND="__winkey_enter_terminal;${PROMPT_COMMAND}"
    fi

    # Aliases for manual control
    alias en='__winkey_enter_terminal'
    alias vn='__winkey_leave_terminal'

    # Restore Vietnamese when shell exits (terminal tab closed)
    trap '__winkey_leave_terminal' EXIT
fi
