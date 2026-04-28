"""
Settings manager for WinKey.
Handles persistent configuration via JSON file.
"""

import json
from pathlib import Path
from typing import TypedDict


class WinKeyConfig(TypedDict):
    """Configuration structure for WinKey."""
    enabled: bool
    english_index: int
    auto_start: bool
    show_notifications: bool
    language: str


DEFAULT_CONFIG: WinKeyConfig = {
    "enabled": True,
    "english_index": 1,
    "auto_start": False,
    "show_notifications": True,
    "language": "vi",
}

CONFIG_DIR = Path.home() / ".config" / "winkey"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> WinKeyConfig:
    """Load configuration from disk, or return defaults."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            # Merge with defaults to handle missing keys
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except (json.JSONDecodeError, OSError):
        pass
    return DEFAULT_CONFIG.copy()


def save_config(config: WinKeyConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
