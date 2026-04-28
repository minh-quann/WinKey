#!/usr/bin/env python3
"""
WinKey - Super Key Input Source Switcher

Hold the Super (Windows) key to temporarily switch to English input.
Release it to return to your previous input source.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.app import WinKeyApp


def main() -> None:
    app = WinKeyApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()