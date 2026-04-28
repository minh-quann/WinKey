"""
GNOME Input Source controller.
Uses gsettings to query and switch input sources.
"""

import subprocess
from dataclasses import dataclass


GSETTINGS_SCHEMA = "org.gnome.desktop.input-sources"


@dataclass
class InputSource:
    """Represents a GNOME input source."""
    index: int
    source_type: str  # 'ibus' or 'xkb'
    source_id: str    # e.g. 'Bamboo::Flag' or 'us'
    display_name: str


def get_current_index() -> int:
    """Get the current input source index."""
    try:
        result = subprocess.run(
            ["gsettings", "get", GSETTINGS_SCHEMA, "current"],
            capture_output=True, text=True, timeout=2
        )
        # Output: "uint32 0"
        return int(result.stdout.strip().split()[-1])
    except Exception:
        return 0


def set_current_index(index: int) -> None:
    """Set the current input source by index."""
    try:
        subprocess.run(
            ["gsettings", "set", GSETTINGS_SCHEMA, "current", str(index)],
            capture_output=True, timeout=2
        )
    except Exception:
        pass


def get_all_sources() -> list[InputSource]:
    """Get all configured input sources from GNOME settings."""
    try:
        result = subprocess.run(
            ["gsettings", "get", GSETTINGS_SCHEMA, "sources"],
            capture_output=True, text=True, timeout=2
        )
        raw = result.stdout.strip()
        # Parse: [('ibus', 'Bamboo::Flag'), ('xkb', 'us')]
        sources: list[InputSource] = []
        # Simple parser for the GVariant tuple list
        import ast
        items = ast.literal_eval(raw)
        for i, (src_type, src_id) in enumerate(items):
            # Generate display name
            if src_type == "xkb":
                name = _xkb_display_name(src_id)
            elif src_type == "ibus":
                name = _ibus_display_name(src_id)
            else:
                name = src_id

            sources.append(InputSource(
                index=i,
                source_type=src_type,
                source_id=src_id,
                display_name=name,
            ))
        return sources
    except Exception:
        return []


def _xkb_display_name(layout_id: str) -> str:
    """Convert XKB layout ID to display name."""
    names = {
        "us": "English (US)",
        "gb": "English (UK)",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "it": "Italian",
        "ja": "Japanese",
        "ko": "Korean",
        "vi": "Vietnamese",
        "ru": "Russian",
        "zh": "Chinese",
    }
    return names.get(layout_id, f"XKB: {layout_id}")


def _ibus_display_name(engine_id: str) -> str:
    """Convert IBus engine ID to display name."""
    if "Bamboo" in engine_id:
        return "Tiếng Việt (Bamboo)"
    if "Unikey" in engine_id:
        return "Tiếng Việt (Unikey)"
    if "anthy" in engine_id.lower():
        return "Japanese (Anthy)"
    return f"IBus: {engine_id}"
